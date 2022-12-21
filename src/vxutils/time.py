"""量化交易时间计时器"""


import time
import contextlib
from enum import Enum
from typing import Any, Callable, List
from vxutils.convertors import (
    combine_datetime,
    to_timestamp,
    to_timestring,
    to_datetime,
)


__all__ = ["vxtime"]


class vxtime:
    """量化交易时间机器"""

    _timefunc = time.time
    _delayfunc = time.sleep
    __time_marks__ = []
    __holidays__ = set()

    @classmethod
    def now(cls) -> float:
        """当前时间"""
        return cls._timefunc()

    @classmethod
    def sleep(cls, seconds: float) -> None:
        """延时等待函数"""
        cls._delayfunc(seconds)

    @classmethod
    @contextlib.contextmanager
    def timeit(cls, prefix=None, show_title=False) -> None:
        """计时器"""
        from vxutils import logger

        if show_title:
            logger.info(f"====== 计时器({prefix}) 开始计时 ======")

        prefix = prefix or "default"

        cls.__time_marks__.append(time.perf_counter())
        try:
            yield
        finally:
            cost_time = (time.perf_counter() - cls.__time_marks__.pop()) * 1000
            logger.info(f"====== 计时器({prefix}) 耗时: {cost_time:,.2f}ms ======")

    @classmethod
    def is_holiday(cls, date_: Any = None) -> bool:
        """是否假日"""
        date_ = date_ if date_ is not None else cls.now()
        if to_datetime(date_).weekday in [0, 1]:
            # 星期六日 均为休息日
            return True

        date_ = to_timestring(date_, "%Y-%m-%d")
        return date_ in cls.__holidays__

    @classmethod
    def set_timefunc(cls, timefunc: Callable) -> None:
        """设置timefunc函数"""
        if not callable(timefunc):
            raise ValueError(f"{timefunc} is not callable.")
        cls._timefunc = timefunc

    @classmethod
    def set_delayfunc(cls, delayfunc: Callable) -> None:
        """设置delayfunc函数"""
        if not callable(delayfunc):
            raise ValueError(f"{delayfunc} is not callable.")
        cls._delayfunc = delayfunc

    @classmethod
    def today(cls, time_str: str = "00:00:00") -> float:
        """今天 hh:mm:ss 对应的时间"""

        date_str = to_timestring(cls.now(), "%Y-%m-%d")
        return combine_datetime(date_str, time_str)

    @classmethod
    def add_holidays(cls, *holidays: List):
        """增加假期时间"""
        if len(holidays) == 1 and isinstance(holidays[0], list):
            holidays = holidays[0]
        cls.__holidays__.update(map(lambda d: to_timestring(d, "%Y-%m-%d"), holidays))


if __name__ == "__main__":
    t1 = vxtime.today()
    print(to_datetime(t1))
    vxtime.add_holidays("2022-10-30", t1)
    print(vxtime.is_holiday("2022-10-30"))
