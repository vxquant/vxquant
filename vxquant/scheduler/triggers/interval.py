"""间隔特定时间触发器"""

from datetime import datetime
from typing import Optional
from vxquant.scheduler.triggers import vxTrigger, TriggerStatus
from vxquant.utils.convertors import to_timestamp, to_timestring
from vxquant.utils import vxtime


class vxIntervalTrigger(vxTrigger):
    """间隔特定时间触发器"""

    __slots__ = ("_last_trigger_dt", "_interval", "_start_dt", "_end_dt")

    def __init__(
        self,
        interval: float = 1.0,
        start_dt: Optional[str | datetime | float] = None,
        end_dt: Optional[str | datetime | float] = None,
    ) -> None:
        super().__init__()
        if interval <= 0:
            raise ValueError(f"间隔时间{interval}必须>0")

        self._interval = interval
        self._start_dt = to_timestamp(start_dt) if start_dt else vxtime.now()
        self._end_dt = to_timestamp(end_dt) if end_dt else None
        if self._end_dt and self._start_dt > self._end_dt:
            raise ValueError(
                f"开始时间{to_timestring(self._start_dt)}大于{to_timestring(self._end_dt)}"
            )

    def get_next_trigger_dt(self) -> float:
        if self.status == TriggerStatus.Pending:
            return self._start_dt

        if self.status == TriggerStatus.Running:
            next_trigger_dt = self._last_trigger_dt + self._interval
            if self._end_dt is None or next_trigger_dt <= self._end_dt:
                return next_trigger_dt
        return None
