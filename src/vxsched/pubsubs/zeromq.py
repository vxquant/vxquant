"""ZMQ 消息通道"""


import zmq
from collections import defaultdict

from typing import Optional, Union, List, Any
from vxutils import vxtime, to_binary, vxZMQRequest, logger
from vxutils.zmqsocket import vxZMQContext
from vxsched.event import vxEvent, vxTrigger
from vxsched.pubsubs.base import vxPublisher, vxSubscriber


__INTERNAL_ZMQFORMAT__ = "ipc://vxquant.internal.ipc"

__all__ = ["vxZMQPublisher", "vxZMQSubscriber", "vxZMQRpcClient"]


class vxZMQPublisher(vxPublisher):
    """Zero MQ的发布器"""

    def __init__(self, channel_name: str, endpoint: str = "", key_file="") -> None:
        super().__init__(channel_name)
        endpoint = endpoint or __INTERNAL_ZMQFORMAT__
        self._request = vxZMQRequest(endpoint, key_file, vxEvent.pack, vxEvent.unpack)
        self._last_request_dt = 0

    def __str__(self) -> str:
        return f"< {self.__class__.__name__}({self.channel_name}) with {self._request}"

    def __eq__(self, __o: object) -> bool:
        return (
            self._channel_name == __o._channel_name and self._request == __o._request
            if isinstance(__o, self.__class__)
            else False
        )

    def ping(self):
        """测试链接情况"""
        if vxtime.now() - 180 < self._last_request_dt:
            return

        try:
            reply_event = self._request(vxEvent(type="__READY__", channel="__BROKER__"))
            if (
                reply_event
                and reply_event.type == "__ACK__"
                and reply_event.data == "OK"
            ):
                self._last_request_dt = vxtime.now()
                return
        except TimeoutError as e:
            logger.warning(f"连接超时. {e}", exc_info=True)

        self._last_request_dt = 0
        raise ConnectionError(f"连接报文错误，回复报文: {reply_event}")

    def __call__(
        self,
        event: Union[str, vxEvent],
        data="",
        trigger: Optional[vxTrigger] = None,
        priority: float = 10,
        channel: str = None,
        **kwargs,
    ) -> None:
        if isinstance(event, str):
            send_event = vxEvent(
                type=event,
                data=data,
                trigger=trigger,
                priority=priority,
                channel=channel or self._channel_name,
                **kwargs,
            )

        else:
            send_event = event
            send_event.channel = channel or send_event.channel or self._channel_name

        self.ping()
        reply_event = self._request(send_event)

        if reply_event.type != "__ACK__" or reply_event.data != "OK":
            self._last_request_dt = 0
            raise ConnectionError(
                f"wrong reply event: ({reply_event.type},{reply_event.data})"
            )

        self._last_request_dt = vxtime.now()
        return


class vxZMQSubscriber(vxSubscriber):
    """Zero MQ的订阅器"""

    def __init__(
        self,
        channel_name,
        endpoint: str = "",
        key_file: str = "",
        timeout=0.01,
    ) -> None:
        super().__init__(channel_name)
        self._endpoint = endpoint or __INTERNAL_ZMQFORMAT__
        self._key_file = key_file
        self._ctx = vxZMQContext().instance()
        self._socket = self._ctx.socket(zmq.XSUB)
        self._socket.connect(self._endpoint, self._key_file)
        self._socket.send(b"\x01" + to_binary(self.channel_name))
        self._socket.send(b"\x01" + b"__BROKER__")

        self._connect_dt = vxtime.now() + 0.3
        self._timeout = timeout * 1000

    def __str__(self) -> str:
        return f"< {self.__class__.__name__}({self.channel_name}) with {self._socket}"

    def __eq__(self, __o: object) -> bool:
        return (
            self._channel_name == __o._channel_name and self._socket == __o._socket
            if isinstance(__o, self.__class__)
            else False
        )

    def __call__(self) -> List[vxEvent]:
        events = defaultdict(list)
        if self._connect_dt > vxtime.now():
            vxtime.sleep(0.3)

        with self._socket.lock:
            while self._socket.poll(self._timeout, zmq.POLLIN) != 0:
                msg = self._socket.recv_multipart()
                event = vxEvent.unpack(msg[1])
                events[event.type].append(event)

        # 值返回同一event
        return list(map(max, events.values()))


class vxZMQRpcClient:
    def __init__(
        self, url: str = "tcp://127.0.0.1:5555", publick_key: str = None
    ) -> None:
        self._request = vxZMQRequest(url, publick_key, vxEvent.pack, vxEvent.unpack)
        self._methods = {}
        self._last_updated_dt = 0
        self._update_rpc_methods()

    def _update_rpc_methods(self) -> None:
        try:
            reply_event = self._request(
                vxEvent(
                    type="__GET_RPCMETHODS__",
                    channel="__BROKER__",
                )
            )
            if reply_event.type != "__GET_RPCMETHODS__":
                raise ValueError(f"错误的回复类型: {reply_event.type}")
            self._methods = dict(**reply_event.data)
        except TimeoutError:
            logger.error("更新methods超时")
            self._methods = {}

        return

    @property
    def methods(self) -> dict:
        """远程调用方法"""
        now = vxtime.now()
        if not self._methods or now > self._last_updated_dt + 60:
            self._update_rpc_methods()
            self._last_updated_dt = now
        return self._methods

    def __getattr__(self, method: str) -> Any:
        if method in self.methods:
            return lambda *args, **kwargs: self.__call__(method, *args, **kwargs)
        raise AttributeError(f"no method: {method}")

    def __call__(self, method: str, *args, **kwargs):
        reply_event = self._request(
            vxEvent(type=method, channel="__RPC__", data=(args, kwargs))
        )
        self._last_updated_dt = vxtime.now()

        if isinstance(reply_event.data, Exception):
            raise reply_event.data

        return reply_event.data


if __name__ == "__main__":
    publisher = vxZMQPublisher(
        "test",
        "tcp://127.0.0.1:5555",
        "/Users/libao/src/git/vxquantlib/etc/frontend.key",
    )

    s = vxZMQSubscriber(
        "test",
        "tcp://127.0.0.1:6666",
        "/Users/libao/src/git/vxquantlib/etc/backend.key",
    )
    start = vxtime.now()
    publisher("test")
    logger.info(f"发布消息需要: {(vxtime.now()-start)*1000:,.2f}s.")
    for _ in range(3):
        start = vxtime.now()
        events = s()
        logger.info(f"接受消息需要: {(vxtime.now()-start)*1000:,.2f}s.")
        print(events)
        vxtime.sleep(1)
