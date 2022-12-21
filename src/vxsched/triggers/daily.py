"""每日触发器"""

from typing import Any
from vxutils import vxtime
from vxsched.event import vxTrigger


class vxDailyTrigger(vxTrigger):
    """每日触发器"""

    def __init__(
        self,
        run_time: str = "00:00:00",
        freq: int = 1,
        end_dt: Any = None,
        skip_holiday: bool = False,
    ):
        """每日触发器

        Keyword Arguments:
            run_time {str} -- 运行时间 (default: {"00:00:00"})
            freq {int} -- 间隔多少天 (default: {1})
            end_dt {Any} -- 结束时间 (default: {None})
            skip_holiday {bool} -- 是否跳过假期 (default: {False})
        """
        start_dt = vxtime.today(run_time)

        if start_dt < vxtime.now():
            start_dt += 24 * 60 * 60

        super(vxDailyTrigger, self).__init__(
            start_dt=start_dt,
            end_dt=end_dt,
            interval=freq * 24 * 60 * 60,
            skip_holiday=skip_holiday,
        )
