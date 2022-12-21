"""一次性触发器"""

from vxsched.event import vxTrigger


class vxOnceTrigger(vxTrigger):
    """一次性触发器

    trigger_dt: 触发时间

    """

    def __init__(self, trigger_dt):
        super(vxOnceTrigger, self).__init__(
            start_dt=trigger_dt, end_dt=trigger_dt, interval=1, skip_holiday=False
        )
