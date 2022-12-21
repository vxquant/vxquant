"""间隔特定时间触发器"""


from typing import Any

from vxsched.event import vxTrigger


class vxIntervalTrigger(vxTrigger):
    """间隔特定时间触发器"""

    def __init__(
        self,
        interval: float = 1,
        start_dt: Any = None,
        end_dt: Any = None,
        skip_holiday: bool = False,
    ):
        """间隔触发器

        Keyword Arguments:
            interval {float} -- 间隔秒数 (default: {1})
            start_dt {Any} -- 开始时间，缺省为：当前时间 (default: {None})
            end_dt {Any} -- 结束时间，缺省为：无限 (default: {None})
            skip_holiday {bool} -- 是否跳过假期 (default: {False})
        """
        super(vxIntervalTrigger, self).__init__(
            interval=interval,
            start_dt=start_dt,
            end_dt=end_dt,
            skip_holiday=skip_holiday,
        )
