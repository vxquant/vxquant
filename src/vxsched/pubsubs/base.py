"""publisher/ subscriber 的基类"""
from abc import abstractmethod
from typing import Optional, Union, List
from vxsched.event import vxEvent, vxTrigger


class vxPublisher:
    """发布器"""

    def __init__(self, channel_name: str) -> None:
        self._channel_name = channel_name

    @property
    def channel_name(self) -> str:
        """消息通道名称"""
        return self._channel_name

    def __str__(self) -> str:
        return f"< {self.__class__.__name__}({self.channel_name})"

    __repr__ = __str__

    @abstractmethod
    def __call__(
        self,
        event: Union[str, vxEvent],
        data="",
        trigger: Optional[vxTrigger] = None,
        priority: float = 10,
        channel: str = None,
        **kwargs,
    ) -> None:
        """发布消息

        Arguments:
            event {Union[str, vxEvent]} -- 要推送消息或消息类型
            data {Any} -- 消息数据信息 (default: {None})
            trigger {Optional[vxTrigger]} -- 消息触发器 (default: {None})
            priority {int} -- 优先级，越小优先级越高 (default: {10})
        """


class vxSubscriber:
    """订阅器"""

    def __init__(self, channel_name: str) -> None:
        self._channel_name = channel_name

    @property
    def channel_name(self) -> str:
        """消息通道名称"""
        return self._channel_name

    def __str__(self) -> str:
        return f"< {self.__class__.__name__}({self.channel_name})"

    @abstractmethod
    def __call__(self, callback=None) -> List[vxEvent]:
        pass
