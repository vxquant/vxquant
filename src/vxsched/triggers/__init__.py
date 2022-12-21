"""触发器"""


from .daily import vxDailyTrigger
from .interval import vxIntervalTrigger
from .once import vxOnceTrigger
from .weekly import vxWeeklyTrigger


__all__ = [
    "vxOnceTrigger",
    "vxIntervalTrigger",
    "vxDailyTrigger",
    "vxWeeklyTrigger",
]
