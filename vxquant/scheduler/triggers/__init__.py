"""触发器"""


from enum import Enum
from datetime import datetime
from abc import ABCMeta, abstractmethod
from vxquant.utils.convertors import to_timestring
from vxquant import vxtime
from typing import Iterator

__all__ = [
    "vxTrigger",
    "TriggerStatus",
    "vxOnceTrigger",
    "vxIntervalTrigger",
    "vxDailyTrigger",
    "vxWeeklyTrigger",
]


class TriggerStatus(Enum):
    """触发器状态

    Pending : 未开始
    Running : 已开始
    Completed: 已完成
    """

    Pending = 1
    Running = 2
    Completed = 3


class vxTrigger(Iterator[float], metaclass=ABCMeta):
    """触发器"""

    __slots__ = ("_last_trigger_dt",)

    def __init__(self):
        self._last_trigger_dt = None

    @abstractmethod
    def get_next_trigger_dt(self) -> float | None:
        """
        返回下一次执行timestamp，如果没有下次执行时间，则返回 'None'
        """

    def __getstate__(self) -> dict:
        """序列化函数"""
        return {key: getattr(self, key) for key in self.__slots__}

    def __setstate__(self, state: dict) -> None:
        """反序列化函数"""
        for key in self.__slots__:
            setattr(self, key, state[key])

    def __str__(self) -> str:
        if self.status == TriggerStatus.Completed:
            return f"< {self.__class__.__name__} (id-{id(self)}): last_trigger_dt: {to_timestring(self._last_trigger_dt)} status: {self.status.name} >"
        else:
            return f"< {self.__class__.__name__} (id-{id(self)}): next_trigger_dt: {to_timestring(self.get_next_trigger_dt())} status: {self.status.name} >"

    __repr__ = __str__

    def __iter__(self) -> Iterator:
        return self

    def __next__(self) -> float:
        if self.status == TriggerStatus.Pending:
            self._last_trigger_dt = self.get_next_trigger_dt()
            return self._last_trigger_dt

        while self.status == TriggerStatus.Running:
            self._last_trigger_dt = self.get_next_trigger_dt()
            if self._last_trigger_dt > vxtime.now():
                return self._last_trigger_dt

        raise StopIteration

    @property
    def status(self) -> TriggerStatus:
        """是否已完成"""
        if self.get_next_trigger_dt() is None:
            return TriggerStatus.Completed
        elif self._last_trigger_dt is None:
            return TriggerStatus.Pending
        return TriggerStatus.Running


from .daily import vxDailyTrigger
from .interval import vxIntervalTrigger
from .once import vxOnceTrigger
from .weekly import vxWeeklyTrigger
