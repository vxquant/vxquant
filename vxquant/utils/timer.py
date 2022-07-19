"""量化交易时间计时器"""


import time
from enum import Enum
from typing import Any, Callable, List
from functools import lru_cache
from .convertors import combine_datetime, to_timestamp, to_timestring
from .decorators import singleton

__all__ = ["vxTimer"]


class TimerStatus(Enum):
    """时钟状态"""

    LIVING = 0
    BACKTEST = 1
    OTHER = 00


@singleton
class vxTimer:
    """量化交易时间机器"""

    def __init__(
        self, timefunc: Callable = time.time, delayfunc: Callable = time.sleep
    ) -> None:
        self._timefunc = timefunc
        self._delayfunc = delayfunc
        self._now = None
        self._end_dt = None
        self._holidays = set()
        self._status = TimerStatus.LIVING

    def now(self) -> float:
        """当前时间"""
        return self._now or self._timefunc()

    def sleep(self, seconds: float) -> None:
        """延时等待函数"""
        if self._now:
            self._now += seconds
            if self._now > self._end_dt:
                print(
                    f"当前回测时间{to_timestring(self._now)}已达到回测时间终点，{to_timestring(self._end_dt)},回测模式结束"
                )
                self._now = None
                self._end_dt = None
                self._status = TimerStatus.LIVING
                raise StopIteration
        else:
            self._delayfunc(seconds)

    def backtest(self, start_time: Any, end_time: Any = None) -> None:
        """设置回测时间段"""
        if self.status != "LIVING":
            raise ValueError(f"当前模式为：{self.status}，不可设置backtest时间段.")
        self._now = to_timestamp(start_time)
        self._end_dt = to_timestamp(end_time) if end_time else self._timefunc()
        self._status = TimerStatus.BACKTEST
        print(
            f"设置回测模式{self.status}：回测起始日期{to_timestring(self._now)} 终止日期{to_timestring(self._end_dt)}"
        )

    def is_holiday(self, date_: Any) -> bool:
        """是否假日"""
        date_ = to_timestring(date_, "%Y-%m-%d")
        return date_ in self._holidays

    def set_timefunc(self, timefunc: Callable) -> None:
        """设置timefunc函数"""
        self._timefunc = timefunc

    def set_delayfunc(self, delayfunc: Callable) -> None:
        """设置delayfunc函数"""
        self._delayfunc = delayfunc

    def today(self, time_str: str = "00:00:00") -> float:
        """今天 hh:mm:ss 对应的时间"""

        date_str = to_timestring(self.now(), "%Y-%m-%d")
        return combine_datetime(date_str, time_str)

    @property
    def status(self):
        """时间状态"""
        return self._status.name

    def add_holidays(self, holidays: List):
        """增加假期时间"""
        self._holidays.update(map(lambda d: to_timestring(d, "%Y-%m-%d"), holidays))
