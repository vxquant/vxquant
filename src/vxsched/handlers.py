""" 策略handler模块 """


import time
import inspect
from functools import wraps
from collections import defaultdict
from typing import Any, Callable, Optional
from concurrent.futures import as_completed
from vxutils import logger
from vxsched.event import vxEvent
from vxsched.context import vxContext

__all__ = ["vxEventHandlers", "vxRpcMethods"]


class vxEventHandlers:
    """消息处理函数"""

    def __init__(self, context: Optional[vxContext] = None) -> None:
        self._context = vxContext() if context is None else context
        self._handlers = defaultdict(list)

    @property
    def context(self):
        """获取上下文"""
        return self._context

    @context.setter
    def context(self, context_):
        self._context = context_

    @property
    def handlers(self) -> dict:
        return self._handlers

    def register(self, event_type: str, handler: Callable) -> None:
        """注册事件处理函数

        Arguments:
            event_type {str} -- 消息类型
            handler {Callable} -- 消息处理函数,handler(context, event, tools=None)

        Raises:
            ValueError: handler类型错误
        """

        if not callable(handler):
            raise ValueError(f"{handler.__name__} is not callable.")

        handlers = self._handlers.pop(event_type, [])
        handler_names = [handler.__name__ for handler in handlers]

        if (handler.__name__ not in handler_names) and (handler not in handlers):
            handlers.append(handler)
            logger.info(
                f"{self.__class__.__name__} register event type: {event_type}, handler:"
                f" {handler}"
            )
        self._handlers[event_type] = handlers

    def unregister(self, event_type: str, handler: Optional[Callable] = None) -> None:
        """取消注册事件处理函数

        Arguments:
            event_type {str} -- 消息类型

        Keyword Arguments:
            handler {Optional[Callable]} -- 消息事件处理函数 (default: {None})
        """

        logger.info(
            f"vxScheduler unregister event type: {event_type}, handler: {handler}"
        )
        handlers = self._handlers.pop(event_type, [])
        if handler:
            if handler in handlers:
                handlers.remove(handler)

            if handlers:
                self._handlers[event_type] = handlers

    def unregister_handler(self, handler: Callable) -> None:
        """取消监听特定函数

        Arguments:
            handler {Callable} -- 待取消监听的函数
        """

        handlers = self._handlers

        for event_type, handlers in handlers.items():
            if handler in handlers:
                handlers.remove(handler)
                if handlers:
                    self._handlers[event_type] = handlers
                else:
                    self._handlers.pop(event_type)

                logger.info(
                    f"{self.__class__.__name__} unregister event type: {event_type},"
                    f" handler: {handler}"
                )

    def trigger(self, event: vxEvent, executor=None) -> Any:
        """触发一个消息

        Arguments:
            event {vxEvent} -- 待触发的消息类型

        Returns:
            Any -- 所有handler
        """
        handlers = self._handlers.get(str(event.type), [])
        if not handlers:
            return

        def hdl_event(hdl):
            return hdl(self.context, event)

        try:
            map_func = executor.map if executor else map
            return list(map_func(hdl_event, handlers))
        except Exception as e:
            logger.info(f"error: {e}", exc_info=True)

    def __call__(self, event_type, time_limit=1):
        def deco(func):
            @wraps(func)
            def _event_handler(context, event):
                try:
                    start = time.perf_counter()
                    ret = func(context, event)
                    cost_time = time.perf_counter() - start
                    if cost_time > time_limit:
                        logger.warning(
                            f"{self.__class__.__name__}:{func.__name__} 耗时"
                            f" {cost_time*1000:,.2f}ms 超出预定时间 {time_limit*1000:,.2f}ms."
                            f" event={event.type} -- {event.data}"
                        )

                except Exception as err:
                    logger.error(
                        f"{self.__class__.__name__}:{func.__name__} error:"
                        f" {err},event={event}",
                        exc_info=True,
                    )
                    ret = None

                return ret

            self.register(event_type, _event_handler)
            return func

        return deco

    def merge(self, other_handlers: "vxEventHandlers") -> None:
        if not isinstance(other_handlers, vxEventHandlers):
            raise ValueError(f"other_handlers Type Error: {type(other_handlers)} ")

        for event_type, handlers in other_handlers.handlers.items():
            self.handlers[event_type].extend(handlers)


class vxRpcMethods:
    """消息处理函数"""

    def __init__(self, context: Optional[vxContext] = None) -> None:
        self._context = vxContext() if context is None else context
        self._methods = {}

    @property
    def context(self):
        """获取上下文"""
        return self._context

    @context.setter
    def context(self, context_):
        self._context = context_

    @property
    def methods(self):
        """所有支持得方法"""
        return list(self._methods.keys())

    def register(self, method_name: str, handler: Callable) -> None:
        """注册事件处理函数

        Arguments:
            method_name {str} -- 消息类型
            handler {Callable} -- 消息处理函数,handler(context, event, tools=None)

        Raises:
            ValueError: handler类型错误
        """

        if not callable(handler):
            raise ValueError(f"{handler} is not callable.")

        self.__call__(method_name)(handler)

    def unregister(self, method_name: str) -> None:
        """取消注册RPC处理函数

        Arguments:
            method_name {str} -- 消息类型
            handler {Optional[Callable]} -- 消息事件处理函数 (default: {None})
        """

        logger.info(f"{self.__class__.__name__} unregister rpc_method: {method_name}")
        self._methods.pop(method_name)

    def execute(self, event: vxEvent) -> Any:
        """触发一个消息

        Arguments:
            event {vxEvent} -- 待触发的消息类型

        Returns:
            Any -- 所有handler
        """
        handler = self._methods.get(event.type, None)

        try:
            return (
                handler(self._context, event)
                if handler
                else NotImplementedError(f"调用方法 {event.type} 暂不支持...{event}")
            )
        except Exception as err:
            logger.error(
                f"{self.__class__.__name__}调用 {event.type}({event.data}) 发生错误: {err}",
                exc_info=True,
            )
            return err

    def __call__(self, method_name=None, with_context=True, time_limit=1, func=None):
        def deco(func):
            @wraps(func)
            def _rpc_handler(context, event):
                args, kwargs = event.data
                if with_context:
                    args = (context, *args)
                    ba = inspect.signature(func).bind(*args, **kwargs)
                else:
                    ba = inspect.signature(func).bind(*args, **kwargs)
                ba.apply_defaults()

                start = time.perf_counter()
                ret = func(*ba.args, **ba.kwargs)
                cost_time = time.perf_counter() - start
                if cost_time > time_limit:
                    logger.warning(
                        f"{self.__class__.__name__}:{func.__name__} 耗时"
                        f" {cost_time*1000:,.2f}ms 超出预定时间 {time_limit*1000:,.2f}ms."
                        f" kwargs={event.data}"
                    )

                return ret

            _method_name = method_name or func.__name__
            self._methods[_method_name] = _rpc_handler
            logger.info(
                f"{self.__class__.__name__} register rpc_method: {method_name} =="
                f" {_rpc_handler.__name__}()"
            )
            return func

        if func:
            deco(func)

        return deco

    def merge(self, other_handlers: "vxEventHandlers") -> None:
        if not isinstance(other_handlers, vxEventHandlers):
            raise ValueError(f"other_handlers Type Error: {type(other_handlers)} ")

        for event_type, handlers in other_handlers._handlers.items():
            self._handlers[event_type].extend(handlers)
