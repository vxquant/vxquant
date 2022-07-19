"""一次性触发器"""

from vxquant.scheduler.triggers import vxTrigger, TriggerStatus


class vxOnceTrigger(vxTrigger):
    """一次性触发器

    trigger_dt: 触发时间

    """

    __slots__ = ("_last_trigger_dt", "_target_trigger_dt")

    def __init__(self, trigger_dt):
        super().__init__()
        self._target_trigger_dt = trigger_dt

    def get_next_trigger_dt(self) -> float | None:
        return None if self._last_trigger_dt else self._target_trigger_dt
