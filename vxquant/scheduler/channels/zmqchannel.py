"""ZMQ 消息通道"""


from multiprocessing.dummy import Pool
from typing import Optional, Any
import zmq
from vxquant.scheduler.event import vxEvent
from vxquant.scheduler.channels import vxChannel
from vxquant.scheduler.triggers import vxTrigger
from vxquant.utils.zmq import ZMQClient, create_server
from vxquant.utils import logger, vxtime


ZMQCHANNEL = "__zmqchannel__"


class vxZMQChannel(vxChannel):
    """ZMQ消息通道"""

    def __init__(
        self,
        channel_name: str,
        url: str = "tcp://127.0.0.1:5555",
        server_key: Optional[str] = None,
    ):
        super(vxZMQChannel, self).__init__(channel_name)
        self._client = ZMQClient(url, server_key)

    def get(
        self, timestamp_: Optional[float] = None, timeout: float = 0.1
    ) -> Optional[vxEvent]:
        """从ZMQ服务器获取消息

        Keyword Arguments:
            timeout {float} -- 超时时间 (default: {0.5})

        Returns:
            [vxEvent] -- 消息列表
        """
        event = vxEvent(
            type=f"{ZMQCHANNEL}.__get__", data=timestamp_, channel=self.name
        )
        event = self._client.send(event)
        return event

    def put(
        self,
        event: str | vxEvent,
        data: Any = None,
        trigger: Optional[vxTrigger] = None,
        priority=10,
        **kwargs,
    ) -> None:
        """推送ZMQ服务器消息"""
        if isinstance(event, str):
            next_trigger_dt = next(trigger, None) if trigger else vxtime.now()
            if next_trigger_dt is None:
                logger.warning(f"{trigger} is completed.")
                return

            send_event = vxEvent(
                type=event,
                data=data,
                trigger=trigger,
                next_trigger_dt=next_trigger_dt,
                priority=priority,
                **kwargs,
            )
        else:
            send_event = event
        send_event.channel = self.name

        try:
            self._client.send(
                vxEvent(
                    type=f"{ZMQCHANNEL}.__put__",
                    channel=self.name,
                    data=vxEvent.pack(send_event),
                )
            )
            return True
        except Exception as e:
            logger.error(f"发送消息错误：{e}", exc_info=True)
            return False

    def __str__(self):
        return f"< {self.__class__.__name__} on channel({self.name}) with url: ({self._url}) >"

    def __repr__(self):
        return f"< {self.__class__.__name__} on channel({self.name}) with url: ({self._url}) >"


class vxZMQChannelServer:
    """消息服务总线

    vxhandlers : 事件处理器
    url : 事件总线地址
    secret_key : 加密密钥
    """

    def __init__(
        self, url: str = "tcp://*:5555", secret_key: Optional[str] = None
    ) -> None:
        self._url: str = url
        self._secret_key: str = secret_key
        self._channels: dict = {}
        self._active: bool = False
        self._pool: Pool = Pool(10)

    def _run(self) -> None:

        with create_server(self._url, zmq.REP, self._secret_key) as server:
            while self._active:
                if not server.poll(100):
                    continue

                event = server.recv_pyobj()
                ret = None
                try:
                    if not isinstance(event, vxEvent):
                        logger.warning(f"收到一个非vxEvent对象: {event}")
                        continue

                    if event.type == f"{ZMQCHANNEL}.__put__":
                        recive_event = vxEvent.unpack(event.data)
                        if recive_event.channel not in self._channels:
                            self._channels[recive_event.channel] = vxChannel(
                                recive_event.channel
                            )
                        self._channels[recive_event.channel].put(recive_event)

                    elif event.type == f"{ZMQCHANNEL}.__get__":
                        channel_name, timestamp_ = event.channel, event.data
                        if channel_name in self._channels:
                            ret = self._channels[channel_name].get(timestamp_)
                    else:
                        raise ValueError("未知事件,无法处理")
                except Exception as e:
                    logger.error(f"发生运行错误: {e}", exc_info=True)
                    ret = e
                finally:
                    server.send_pyobj(ret)

    def start(self) -> None:
        """启动事件总线"""
        if self._active:
            logger.warning(f"{self._url} 已经激活，不能再次激活.")
            return

        self._active = True
        try:
            self._run()
        finally:
            self.stop()

    def stop(self):
        """暂停zmqchannel server服务"""
        self._active = False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="""zmq channel 服务器""")
    parser.add_argument(
        "--host",
        help="bind ip address,default: any ip address on the server",
        default="*",
        type=str,
    )
    parser.add_argument(
        "-p",
        "--port",
        help="bind ports,default: 5555",
        default=5555,
        type=int,
    )
    parser.add_argument(
        "-k", "--keyfile", help="private key file path", default="", type=str
    )
    args = parser.parse_args()
    url = f"tcp://{args.host}:{args.port}"
    server = vxZMQChannelServer(url, args.keyfile)
    server.start()
