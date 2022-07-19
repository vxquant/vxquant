"""每日触发器"""
from vxquant.scheduler.triggers import vxTrigger, TriggerStatus
from vxquant.utils.convertors import to_timestring
from vxquant.utils import vxtime


class vxDailyTrigger(vxTrigger):
    """每日触发器"""

    __slots__ = (
        "_last_trigger_dt",
        "_interval",
        "_run_time",
        "_skip_holiday",
    )

    def __init__(
        self,
        run_time: str = "00:00:00",
        interval: int = 1,
        skip_holiday: bool = True,
    ) -> None:
        super().__init__()
        if interval <= 0:
            raise ValueError(f"时间间隔{interval} 必须>=1.")

        self._interval = interval * 60 * 60 * 24
        self._run_time = run_time
        self._skip_holiday = skip_holiday

    def get_next_trigger_dt(self):
        trigger_dt = (
            vxtime.today(self._run_time)
            if self.status == TriggerStatus.Pending
            else self._last_trigger_dt + self._interval
        )
        while self._skip_holiday is False or vxtime.is_holiday(
            to_timestring(trigger_dt, "%Y-%m-%d")
        ):
            trigger_dt += self._interval

        return trigger_dt
