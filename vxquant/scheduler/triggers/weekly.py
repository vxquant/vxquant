"""每周触发器

    params:
        weekday: 0->星期日,1->星期一,2->星期二...
        start_time: 开始时间
        end_time: 结束时间
        interval: 间隔时间
"""

from vxquant.scheduler.triggers import vxTrigger, TriggerStatus
from vxquant.utils.convertors import to_timestring, combine_datetime
from vxquant.utils import vxtime


_weekfreq = {
    1: "W-MON",
    2: "W-TUE",
    3: "W-WED",
    4: "W-THU",
    5: "W-FRI",
    6: "W-SAT",
    0: "W-SUN",
}


class vxWeeklyTrigger(vxTrigger):
    """每周触发器

    params:
        weekday: 0->星期日,1->星期一,2->星期二...
        start_time: 开始时间
        end_time: 结束时间
        interval: 间隔时间
    """

    __slots__ = (
        "_last_trigger_dt",
        "_freq",
        "_interval",
        "_run_time",
        "_skip_holiday",
    )

    def __init__(
        self,
        weekday: int,
        run_time: str = "00:00:00",
        interval: int = 1,
        skip_holiday: bool = True,
    ):

        super().__init__()
        if weekday not in _weekfreq:
            raise ValueError(f"weekday{weekday} Error.")

        if interval < 0:
            raise ValueError(f"interval{interval} Error.")

        self._freq = _weekfreq[weekday]
        self._interval = interval * 60 * 60 * 24 * 7
        self._run_time = run_time
        self._skip_holiday = skip_holiday

    def get_next_trigger_dt(self) -> float | None:
        import pandas as pd

        if self.status == TriggerStatus.Pending:
            daterange = pd.date_range(
                start=to_timestring(vxtime.now(), "%Y-%m-%d"),
                periods=10,
                freq=self._freq,
            ).strftime("%Y-%m-%d")
            print(daterange[0], type(daterange[0]))
            trigger_dt = combine_datetime(daterange[0], self._run_time)
        else:
            trigger_dt = self._last_trigger_dt + self._interval

        while self._skip_holiday is False or vxtime.is_holiday(
            to_timestring(trigger_dt, "%Y-%m-%d")
        ):
            trigger_dt += self._interval

        return trigger_dt
