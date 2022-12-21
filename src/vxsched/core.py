import os
import importlib
import contextlib
from pathlib import Path

from queue import Empty

from functools import wraps
from collections import defaultdict
from typing import Any, Optional, Union, Callable
from concurrent.futures import ThreadPoolExecutor as Executor, as_completed
from vxutils import logger
from vxsched.event import vxEvent, vxTrigger, vxEventQueue
from vxsched.context import vxContext
from vxsched.handlers import vxEventHandlers

__all__ = [
    "vxEngine",
    "vxengine",
]


class vxEngine:
    """驱动引擎"""

    def __init__(self, context=None, event_queue=None) -> None:
        if context is None:
            context = vxContext()
        self._event_handlers = vxEventHandlers(context=context)

        self._event_queue = event_queue if event_queue is not None else vxEventQueue()
        self._active = False
        self._executor = None
        self._backends = []
        self._futures = []
        self._is_initialized = False

    @property
    def event_handler(self) -> vxEventHandlers:
        """vxEventHandler"""
        return self._event_handlers

    @property
    def context(self) -> vxContext:
        """上下文"""
        return self._event_handlers.context

    @context.setter
    def context(self, other_context) -> None:
        self._event_handlers.context = other_context

    def is_alive(self):
        return self._active

    def initialize(self, **kwargs) -> None:
        if self._is_initialized is True:
            logger.warning("已经初始化，请勿重复初始化")
            return

        executor = kwargs.pop("executor", None)
        if executor is not None:
            self._executor = executor

        context = kwargs.pop("context", None)
        if context:
            self.context = context
            logger.debug(f"更新context内容: {self.context}")

        event_handlers = kwargs.pop("event_handlers", None)
        if event_handlers:
            self._event_handlers = kwargs.pop("event_handlers")

        event_queue = kwargs.pop("event_queue", None)
        if event_queue:
            self._event_queue = kwargs.pop("event_queue")

        self._active = True
        self.submit_event("__init__")
        logger.info(f"{self.__class__.__name__} 触发初始化时间 (__init__) ... ")
        self.trigger_events()
        self._is_initialized = True

    def submit_event(
        self,
        event: Union[str, vxEvent],
        data: Any = "",
        trigger: Optional[vxTrigger] = None,
        priority: float = 10,
        **kwargs,
    ) -> None:
        """发布消息

        Arguments:
            event {Union[str, vxEvent]} -- 要推送消息或消息类型
            data {Any} -- 消息数据信息 (default: {None})
            trigger {Optional[vxTrigger]} -- 消息触发器 (default: {None})
            priority {int} -- 优先级，越小优先级越高 (default: {10})
        """

        if isinstance(event, str):
            send_event = vxEvent(
                type=event,
                data=data,
                trigger=trigger,
                priority=priority,
                **kwargs,
            )

        elif isinstance(event, vxEvent):
            send_event = event
        else:
            raise ValueError(f"event 类型{type(event)}错误，请检查: {event}")

        logger.debug(f"提交消息: {send_event}")
        self._event_queue.put_nowait(send_event)
        if not self._active:
            logger.warning(
                f"{self.__class__.__name__}(id-{id(self)})"
                f" 未激活，event({send_event.type})将在激活后运行。"
            )

    def trigger_events(self) -> None:
        events = defaultdict(list)
        with contextlib.suppress(Empty):
            while not self._event_queue.empty():
                event = self._event_queue.get_nowait()
                events[event.type].append(event)
        list(map(self.event_handler.trigger, map(max, events.values())))

    def run(self) -> None:
        logger.info(f"{self.__class__.__name__} worker 启动...")
        try:
            while self.is_alive():
                try:
                    event = self._event_queue.get(timeout=1)
                    logger.debug(f"{self.__class__.__name__} 触发 {event.type} 事件...")
                    self.event_handler.trigger(event)
                except Empty:
                    pass
                except Exception as e:
                    logger.info(f"trigger event{event} error: {e}", exc_info=True)

        finally:
            logger.info(f"{self.__class__.__name__} worker 结束...")
            self.stop()

    def serve_forever(self) -> None:
        """运行"""

        self.start()
        list(as_completed(self._futures))
        self.stop()

    def start(self) -> None:
        """开始运行vxScheduler

        Keyword Arguments:
            worker_cnt {int} -- worker个数 (default: {5})
        """

        # if not self.is_alive():
        #    self.initialize()

        logger.info("=" * 60)
        logger.info("=" * 60)
        logger.info("=" * 60)

        if self._executor is None:
            self._executor = Executor(
                thread_name_prefix=f"{self.__class__.__name__}",
            )
            logger.info(
                f"executor 初始化{self._executor},max_workers ="
                f" {self._executor._max_workers}"
            )

        if self._is_initialized is False:
            self.initialize()

        self._futures.extend([self._executor.submit(self.run) for _ in range(5)])
        if self._backends:
            self._futures.extend(
                [
                    self._executor.submit(target, engine=self)
                    for target in self._backends
                ]
            )

    def stop(self) -> None:
        if self._active is False:
            return

        self._active = False
        while self._futures:
            f = self._futures.pop()
            if f is None:
                continue
            err = f.exception()
            if err:
                logger.warning(f"{f} raise Exception: {err}")
        self._executor.shutdown()
        logger.info("=" * 60)
        logger.info(f" {'stopped':=^60} ")
        logger.info("=" * 60)

    @classmethod
    def load_modules(cls, mod_path: Union[str, Path]) -> Any:
        """加载策略目录"""
        if not os.path.exists(mod_path):
            logger.warning(msg=f"{mod_path} is not exists")
            return

        modules = os.listdir(mod_path)
        logger.info(f"loading strategy dir: {mod_path}.")
        logger.info("=" * 80)
        for mod in modules:
            if (not mod.startswith("__")) and mod.endswith(".py"):
                try:
                    loader = importlib.machinery.SourceFileLoader(
                        mod, os.path.join(mod_path, mod)
                    )
                    spec = importlib.util.spec_from_loader(loader.name, loader)
                    strategy_mod = importlib.util.module_from_spec(spec)
                    loader.exec_module(strategy_mod)
                    logger.info(f"Load Module: {strategy_mod} Sucess.")
                    logger.info("+" * 80)
                except Exception as err:
                    logger.error(f"Load Module: {mod} Failed. {err}", exc_info=True)
                    logger.error("-" * 80)

    def backend(self, target: Callable):
        """添加backend 函数
        @engine.backend
        def run_backend(engine):
            pass

        """

        @wraps(target)
        def wrapper_target(engine: vxEngine):
            if not engine.is_alive():
                logger.warning(f"{engine}未进行初始化...")
                return

            logger.info(f"{self.__class__.__name__} backend( {target.__name__} ) 开始运行")
            try:
                return target(engine)
            except Exception as err:
                logger.info(f"{target} 运行错误: {err}", exc_info=True)
            finally:
                logger.info(
                    f"{self.__class__.__name__} backend( {target.__name__} ) 停止运行....",
                    exc_info=True,
                )

        self._backends.append(wrapper_target)
        return target


vxengine = vxEngine()
