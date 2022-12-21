"""消息类型"""

from heapq import heappush, heappop
from enum import Enum
from queue import Queue, Empty
from typing import Optional, Any
from vxutils import (
    vxDataClass,
    vxIntField,
    vxDatetimeField,
    vxField,
    vxFloatField,
    vxUUIDField,
    vxBoolField,
    vxPropertyField,
    vxtime,
    combine_datetime,
)


__all__ = ["vxEvent", "vxEventQueue", "vxTrigger", "TriggerStatus"]


class TriggerStatus(Enum):
    """触发器状态

    Pending : 未开始
    Running : 已开始
    Completed: 已完成
    """

    #  未开始
    Pending = 1
    #  已开始
    Running = 2
    #  已完成
    Completed = 3


def _trigger_status(trigger):
    if trigger.trigger_dt is None:
        return TriggerStatus.Pending
    elif trigger.next() is None:
        return TriggerStatus.Completed
    return TriggerStatus.Running


class vxTrigger(vxDataClass):
    __sortkeys__ = ("trigger_dt",)

    # 触发时间
    trigger_dt = vxDatetimeField(None)
    # 间隔 (单位：秒)
    interval = vxFloatField(1, 3, 0.01, float("inf"))
    # 是否跳过假期
    skip_holiday = vxBoolField(True)
    # 触发器状态
    status = vxPropertyField(property_factory=_trigger_status)
    # 开始时间
    start_dt = vxDatetimeField()
    # 结束时间
    end_dt = vxDatetimeField(default_factory=float("inf"))

    def next(self):
        if self.trigger_dt is None:
            now = vxtime.now()
            trigger_dt = self.start_dt
            if now > self.start_dt:
                trigger_dt = (
                    self.start_dt
                    + (now - self.start_dt) // self.interval * self.interval
                    + self.interval
                )

        else:
            trigger_dt = self.trigger_dt + self.interval

        while (
            self.skip_holiday
            and vxtime.is_holiday(trigger_dt)
            and trigger_dt <= self.end_dt
        ):
            trigger_dt = (
                trigger_dt
                + (combine_datetime(trigger_dt, "23:59:59") - trigger_dt)
                // self.interval
                * self.interval
                + self.interval
            )

        return trigger_dt if trigger_dt <= self.end_dt else None

    def __iter__(self):
        return self

    def __next__(self) -> float:
        if self.next() is not None:
            self.trigger_dt = self.next()
            return self.trigger_dt

        raise StopIteration

    @staticmethod
    def once(trigger_dt):
        return vxTrigger(
            start_dt=trigger_dt, end_dt=trigger_dt, interval=1, skip_holiday=False
        )

    @staticmethod
    def daily(run_time="00:00:00", freq=1, end_dt=None, skip_holiday=False):
        start_dt = vxtime.today(run_time)
        if start_dt < vxtime.now():
            start_dt += 24 * 60 * 60

        return vxTrigger(
            start_dt=start_dt,
            end_dt=end_dt,
            interval=int(freq) * 24 * 60 * 60,
            skip_holiday=skip_holiday,
        )

    @staticmethod
    def every(interval=1, start_dt=None, end_dt=None, skip_holiday=False):
        return vxTrigger(
            start_dt=start_dt,
            end_dt=end_dt,
            interval=interval,
            skip_holiday=skip_holiday,
        )


class vxEvent(vxDataClass):
    """消息类型"""

    __sortkeys__ = ("trigger_dt", "priority")

    # 消息id
    id: str = vxUUIDField(auto=True)
    # 消息通道
    channel: str = vxField("")
    # 消息类型
    type: str = vxField("", str)
    # 消息内容
    data: Any = vxField("")
    # 定时触发器
    trigger: Optional[vxTrigger] = vxField(default_factory="")
    # 触发时间
    trigger_dt: float = vxDatetimeField()
    # 优先级
    priority: int = vxIntField(10)
    # rpc消息回复地址
    reply_to: str = vxUUIDField(auto=False)


class vxEventQueue(Queue):
    def _init(self, maxsize=0):
        self.queue = []
        self._event_ids = set()

    def _qsize(self):
        now = vxtime.now()
        return len([event for event in self.queue if event.trigger_dt <= now])

    def _put(self, event):
        if isinstance(event, str):
            event = vxEvent(type=event)
        elif not isinstance(event, vxEvent):
            raise ValueError(f"Not support type(event) : {type(event)}.")

        if event.id in self._event_ids:
            raise ValueError(f"event({event.id})重复入库. {event}")

        if event.trigger and event.trigger.status.name == "Pending":
            event.trigger_dt = next(event.trigger, vxtime.now())

        heappush(self.queue, event)
        self._event_ids.add(event.id)

    def get(self, block=True, timeout=None):
        with self.not_empty:
            if not block:
                if not self._qsize():
                    raise Empty
            elif timeout is None:
                while not self._qsize():
                    remaining = 10
                    if len(self.queue) > 0:
                        remaining = self.queue[0].trigger_dt - vxtime.now()

                    if remaining > 0:
                        self.not_empty.wait(remaining)

            elif timeout < 0:
                raise ValueError("'timeout' must be a non-negative number")
            else:
                endtime = vxtime.now() + timeout
                while not self._qsize():
                    if len(self.queue) > 0:
                        min_endtime = min(endtime, self.queue[0].trigger_dt)
                    else:
                        min_endtime = endtime

                    remaining = min_endtime - vxtime.now()

                    if remaining <= 0.0:
                        raise Empty
                    self.not_empty.wait(remaining)
            event = self._get()
            self.not_full.notify()
            return event

    def _get(self):
        event = heappop(self.queue)
        # 获取的event都将trigger给去掉，以免trigger在其他地方再进行传递
        if not event.trigger or event.trigger.status.name == "Completed":
            self.unfinished_tasks -= 1
            self._event_ids.remove(event.id)
            event.trigger = ""
            return event

        reply_event = vxEvent(**event.message)
        reply_event.trigger = ""

        event.trigger_dt = next(event.trigger, None)
        heappush(self.queue, event)
        self.not_empty.notify()
        return reply_event
