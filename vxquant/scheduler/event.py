"""消息类型"""
from typing import Optional, Any
from vxquant.utils.dataclass import (
    vxDataClass,
    vxIntField,
    vxDatetimeField,
    vxField,
    vxUUIDField,
)

from vxquant.scheduler.triggers import vxTrigger


__all__ = ["vxEvent"]


class vxEvent(vxDataClass):
    """消息类型"""

    __sortkeys__ = ("next_trigger_dt", "priority")

    # 消息id
    id: str = vxUUIDField(auto=True)
    # 消息通道
    channel: str = vxField("", str)
    # 消息类型
    type: str = vxField("", str)
    # 消息内容
    data: Any = vxField("")
    # 定时触发器
    trigger: Optional[vxTrigger] = vxField()
    # 下次触发事件
    next_trigger_dt: float = vxDatetimeField()
    # 优先级
    priority: int = vxIntField(10)
