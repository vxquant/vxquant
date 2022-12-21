"""每周触发器

    params:
        weekday: 0->星期日,1->星期一,2->星期二...
        start_time: 开始时间
        end_time: 结束时间
        interval: 间隔时间
"""
import datetime
from typing import Optional, Any

from vxutils import to_timestamp, to_timestring, to_datetime, vxtime

from vxsched.event import vxTrigger


class vxWeeklyTrigger(vxTrigger):
    """每周触发器

    params:
        start_time: 开始时间
        end_time: 结束时间
        interval: 间隔时间
        weekday: 0->星期日,1->星期一,2->星期二... isoweekday方式
        end_dt: 结束时间
    """

    __slots__ = (
        "_last_trigger_dt",
        "_weekday",
        "_interval",
        "_run_time",
        "_skip_holiday",
    )

    def __init__(
        self,
        run_time: str = "00:00:00",
        interval: int = 1,
        weekday: int = 1,
        skip_holiday: bool = True,
        end_dt: Any = None,
    ):
        super().__init__(end_dt=end_dt)
        if not 1 <= weekday <= 7:
            raise ValueError(f"weekday{weekday} Error.")

        if interval < 0:
            raise ValueError(f"interval{interval} must >= 1 .")

        self._weekday = weekday
        self._interval = interval * 60 * 60 * 24 * 7
        self._run_time = run_time
        self._skip_holiday = skip_holiday

    def get_next_trigger_dt(self) -> Optional[float]:
        if self._last_trigger_dt is None:
            # * 获取首次运行时间
            trigger_dt = vxtime.today(self._run_time)
            if trigger_dt <= vxtime.now():
                trigger_dt += 60 * 60 * 24
            trigger_dt = to_datetime(trigger_dt)
            while trigger_dt.isoweekday() != self._weekday:
                trigger_dt += datetime.timedelta(days=1)
            trigger_dt = to_timestamp(trigger_dt)
        else:
            trigger_dt = self._last_trigger_dt + self._interval

        while self._skip_holiday is False or vxtime.is_holiday(
            to_timestring(trigger_dt, "%Y-%m-%d")
        ):
            trigger_dt += self._interval

        return trigger_dt
