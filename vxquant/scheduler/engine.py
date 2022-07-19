# encoding=utf-8
""" 策略handler模块 """

import os
import time
import importlib
from functools import wraps


from typing import Any, Callable, Optional


from vxquant.scheduler.triggers import vxIntervalTrigger, TriggerStatus
from vxquant.scheduler.channels import vxChannel
from vxquant.utils import vxtime, logger

from vxquant.scheduler.event import vxEvent
from vxquant.scheduler.context import vxContext
from vxquant.utils.convertors import to_timestring, to_timestamp
from vxquant.utils.dataclass import vxDict

__all__ = ["vxEventHandlers", "vxhandlers"]


class vxEventHandlers:
    """事件处理器"""

    def __init__(self, context: Optional[vxContext] = None) -> None:
        """初始化"""

        # 执行handlers
        self._handlers = {}

        # 上下文
        self._context = context or vxContext()

        # 是否激活
        self._active = False

        # 各类外部接口
        self._apis = vxDict()

    @property
    def context(self):
        """获取上下文"""
        return self._context

    @property
    def apis(self):
        """获取各类接口"""
        return self._apis

    def register(self, event_type: str, handler: Callable) -> None:
        """注册事件处理函数
        注意: def handler(context, event),其中handler参数context为全局上下文,event为事件对象
        """

        if not callable(handler):
            raise ValueError(f"{handler.__name__} is not callable.")

        handlers = self._handlers.pop(event_type, [])
        handler_names = [handler.__name__ for handler in handlers]

        if (handler.__name__ not in handler_names) and (handler not in handlers):
            handlers.append(handler)
            logger.info(
                f"vxHandlers register event type: {event_type}, handler: {handler}"
            )
        self._handlers[event_type] = handlers

    def unregister(self, event_type: str, handler: Optional[Callable] = None) -> None:
        """取消注册事件处理函数"""
        logger.info(
            f"vxHandlers unregister event type: {event_type}, handler: {handler}"
        )
        handlers = self._handlers.pop(event_type, [])
        if handler:
            if handler in handlers:
                handlers.remove(handler)

            if handlers:
                self._handlers[event_type] = handlers

    def unregister_handler(self, handler: Callable) -> None:
        """
        取消监听特定函数
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
                    f"vxHandlers unregister event type: {event_type}, handler: {handler}"
                )

    def trigger(self, event: vxEvent) -> Any:
        """触发一个消息"""

        handlers = self._handlers.get(str(event.type), [])

        def _trigger_handler(handler):
            try:
                return handler(self.context, event)
            except Exception as err:
                logger.error(
                    f"vxHandlers({handler.__name__}) 触发事件: {event.type} error: {err}",
                    exc_info=True,
                )

        return list(map(_trigger_handler, handlers))

    def __call__(self, event_type, time_limit=1):
        def deco(func):
            @wraps(func)
            def event_handler(context, event):
                try:
                    start = time.perf_counter()
                    ret = func(context, event)
                    cost_time = time.perf_counter() - start
                    if cost_time > time_limit:
                        logger.warning(
                            f"vxHandlers:{func.__name__}(context,{event}) 耗时 {cost_time*1000:,.2f}ms 超出预定时间 {time_limit*1000:,.2f}ms."
                        )

                except Exception as e:
                    logger.error(
                        f"vxHandlers:{func.__name__}(context,{event}) error: {e}",
                        exc_info=True,
                    )

                return ret

            self.register(event_type, event_handler)
            return func

        return deco

    def load_handlers(self, handlers_dir):
        """加载策略目录"""
        if not os.path.exists(handlers_dir):
            logger.warning(msg=f"{handlers_dir} is not exists")
            return

        modules = os.listdir(handlers_dir)
        logger.info(f"loading strategy dir: {handlers_dir}.")
        logger.info("=" * 80)
        for mod in modules:
            if (not mod.startswith("__")) and mod.endswith(".py"):
                try:
                    loader = importlib.machinery.SourceFileLoader(
                        mod, os.path.join(handlers_dir, mod)
                    )
                    spec = importlib.util.spec_from_loader(loader.name, loader)
                    strategy_mod = importlib.util.module_from_spec(spec)
                    loader.exec_module(strategy_mod)
                    logger.info(f"Load Module: {strategy_mod} Sucess.")
                    logger.info("+" * 80)
                except Exception as err:
                    logger.error(f"Load Module: {mod} Failed. {err}", exc_info=True)
                    logger.error("-" * 80)


vxhandlers = vxEventHandlers()


class vxEventEngine:
    """消息处理引擎"""

    def __init__(self, handlers: vxEventHandlers, channel: vxChannel) -> None:
        self._handlers = handlers
        self._channel = channel
        self._active = False

    def _run_backtest(self, start_dt, end_dt):
        vxtime.backtest(start_dt, end_dt)
        logger.info("=" * 80)
        logger.info(
            f"========  回测开始:{to_timestring(start_dt)} 至 {to_timestring(end_dt)}  ========"
        )
        logger.info("=" * 80)
        while self._active and self._channel.next_trigger_dt is not None:
            sleep_time = self._channel.next_trigger_dt - vxtime.now()
            if sleep_time > 0:
                try:
                    vxtime.sleep(sleep_time)
                except StopIteration:
                    break

            event = self._channel.get(vxtime.now())

            if not event:
                continue

            if event.trigger and event.trigger.status != TriggerStatus.Completed:
                event.next_trigger_dt = next(event.trigger, None)
                self._channel.put(event)

            self._handlers.trigger(event)

        on_backtest_finished_event = vxEvent(type="on_backtest_finished")
        self._handlers.trigger(on_backtest_finished_event)
        logger.info("=" * 80)
        logger.info("========  回测结束  ========")
        logger.info("=" * 80)

    def _run_util_end_dt(self, end_dt: float) -> None:
        while self._active:
            now = vxtime.now()
            if now > end_dt:
                logger.info(f"已到达终止时间{to_timestring(end_dt)},退出运行...")
                break

            event = self._channel.get(now)
            if not event:
                continue

            if event.trigger and event.trigger.status != TriggerStatus.Completed:
                event.next_trigger_dt = next(event.trigger, None)
                self._channel.put(event)

            self._handlers.trigger(event)

    def _run_forever(self):
        print("=" * 30)
        while self._active:

            event = self._channel.get(vxtime.now())
            if not event:
                continue

            if event.trigger and event.trigger.status != TriggerStatus.Completed:
                event.next_trigger_dt = next(event.trigger, None)
                self._channel.put(event)

            self._handlers.trigger(event)

    def start(self, start_dt=None, end_dt=None) -> None:
        """开始执行"""
        self._active = True
        logger.info(f"开始运行...监听通道{self._channel}")

        try:
            if start_dt is None and end_dt is None:
                self._run_forever()
            elif start_dt is None:
                end_dt = to_timestamp(end_dt)
                self._run_util_end_dt(end_dt)
            else:
                start_dt = to_timestamp(start_dt)
                end_dt = to_timestamp(end_dt)
                self._run_backtest(start_dt, end_dt)
        finally:
            self.stop()

    def stop(self) -> None:
        """停止执行"""
        self._active = False
        logger.info(f"运行结束...{self._channel}")
