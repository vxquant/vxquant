"""channels类"""
from collections import defaultdict
from queue import PriorityQueue
from typing import Optional, Any
from vxquant.utils import vxtime, logger
from vxquant.scheduler.event import vxEvent
from vxquant.scheduler.triggers import vxTrigger


__all__ = ["vxChannel", "vxFTPChannel"]
# , "vxZMQChannel", "vxZMQChannelServer"]


class vxChannel:
    """消息通道"""

    _queue_pools = defaultdict(PriorityQueue)

    def __init__(self, channel_name: str) -> None:
        self._channel_name = channel_name
        self._queue = self._queue_pools[self._channel_name]

    def __str__(self):
        return f"< {self.__class__.__name__} on channel({self.name}) with local queue: ({self._queue}) >"

    __repr__ = __str__

    def __eq__(self, other: "vxChannel") -> bool:
        return self.name == other.name and self._queue == other._queue

    @property
    def name(self) -> str:
        """通道名称"""
        return self._channel_name

    @property
    def next_trigger_dt(self) -> float | None:
        """队列"""
        return None if self._queue.empty() else self._queue.queue[0].next_trigger_dt

    # def put(self, event: str | vxEvent, data=None, trigger=None, **kwargs):
    @property
    def next_event_runtime(self) -> float | None:
        """队列"""
        return None if self._queue.empty() else self._queue.queue[0].next_trigger_dt

    def put(
        self,
        event: str | vxEvent,
        data: Any = None,
        trigger: Optional[vxTrigger] = None,
        priority=10,
        **kwargs,
    ) -> None:
        """发送消息"""

        if isinstance(event, str):
            next_trigger_dt = next(trigger, None) if trigger else vxtime.now()
            if next_trigger_dt is None:
                logger.warning(f"{trigger} is completed.")
                return

            send_event = vxEvent(
                type=event,
                data=data,
                trigger=trigger,
                next_trigger_dt=next_trigger_dt,
                priority=priority,
                **kwargs,
            )
        else:
            send_event = event
        send_event.channel = self.name
        print(f"{send_event=}")
        self._queue.put_nowait(send_event)

    def get(
        self, timestamp_: Optional[float] = None, timeout: float = 1
    ) -> Optional[vxEvent]:
        """获取消息

        如果最近的event的next_trigger_dt 大于 timestamp_ 则获取下来
        否则 等待timeout时间

        返回 1个event
        """

        if self.next_trigger_dt and (
            timestamp_ is None or timestamp_ > self.next_trigger_dt
        ):
            return self._queue.get_nowait()
        else:
            vxtime.sleep(timeout)
        return None

    def clear(self):
        """清空队列所有消息"""
        while not self._queue.empty():
            self._queue.get_nowait()


from .ftpchannel import vxFTPChannel

# from .zmqchannel import vxZMQChannel, vxZMQChannelServer
