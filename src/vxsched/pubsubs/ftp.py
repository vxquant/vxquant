"""ftp消息通道"""


import io
import pathlib
from typing import List, Union, Optional

from vxutils import logger, vxFTPConnector, vxtime
from vxsched.event import vxEvent, vxTrigger
from .base import vxPublisher, vxSubscriber


def _to_event_rank(filename: str) -> tuple:
    """转换为 (timestamp, filename)的组合"""
    return float(pathlib.Path(filename).name.split("||")[0]), filename


__all__ = ["vxFTPPublisher", "vxFTPSubscriber"]


class vxFTPPublisher(vxPublisher):
    """FTP发布器"""

    _connections = {}

    def __init__(
        self,
        channel_name="",
        host: str = "",
        port: int = 21,
        user: str = "",
        passwd: str = "",
        root_dir="/",
    ) -> None:
        super().__init__(channel_name)

        key = hash(f"ftp://{user}:{passwd}@{host}:{port}")
        if key not in self.__class__._connections:
            self.__class__._connections[key] = vxFTPConnector(host, port, user, passwd)
            logger.info(f"创建FTP连接：{self.__class__._connections[key]}")
        self._ftp_conn = self.__class__._connections[key]

        self._remote_dir = pathlib.Path(root_dir, channel_name).as_posix()
        self._root_dir = root_dir
        logger.info(f"远程ftp目录: {self._remote_dir}")

        self._exists_remote_dirs = self._ftp_conn.list(self._root_dir)
        if self._remote_dir not in self._exists_remote_dirs:
            logger.info(f"创建远程ftp目录: {self._remote_dir}")
            self._ftp_conn.mkdir(self._remote_dir)
            self._exists_remote_dirs = self._ftp_conn.list(self._root_dir)

    @property
    def channel_name(self) -> str:
        """消息渠道名称"""
        return self._channel_name

    def __str__(self) -> str:
        return (
            f"< {self.__class__.__name__}({self.channel_name}) with {self._ftp_conn} on"
            f" remote_dir: {self._remote_dir}"
        )

    def __eq__(self, __o: object) -> bool:
        return (
            self._channel_name == __o._channel_name
            and self._ftp_conn == __o._ftp_conn
            and self._remote_dir == __o._remote_dir
            if isinstance(__o, self.__class__)
            else False
        )

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

        if isinstance(event, str):
            send_event = vxEvent(
                type=event,
                data=data,
                trigger=trigger,
                priority=priority,
                **kwargs,
            )

        else:
            send_event = event
        send_event.channel = channel or self.channel_name
        picked_event = vxEvent.pack(send_event)

        remote_dir = pathlib.Path(self._root_dir, send_event.channel).as_posix()

        if remote_dir not in self._exists_remote_dirs:
            self._ftp_conn.mkdir(remote_dir)
            logger.info(f"创建远程ftp目录: {remote_dir}")
            self._exists_remote_dirs = self._ftp_conn.list(self._root_dir)

        remote_file = pathlib.Path(
            remote_dir,
            f"{send_event.next_trigger_dt}____{send_event.id.replace('-','')}.pkl",
        ).as_posix()

        try:
            with io.BytesIO(picked_event) as bfp:
                self._ftp_conn.upload(bfp, remote_file)
                logger.debug(
                    f"{self} put event.type({send_event.type}) to"
                    f" remote({remote_file}). {send_event}"
                )

        except Exception as err:
            logger.error(
                f"{self} put event.type({send_event.type}) to remote({remote_file})."
                f" error: {err}",
                exc_info=True,
            )


class vxFTPSubscriber(vxSubscriber):
    """FTP消息订阅器"""

    _connections = {}

    def __init__(
        self,
        channel_name: str = "",
        host: str = "",
        port: int = 21,
        user: str = "",
        passwd: str = "",
        root_dir="/",
    ) -> None:
        super().__init__(channel_name)

        key = hash(f"ftp://{user}:{passwd}@{host}:{port}")
        if key not in self.__class__._connections:
            self.__class__._connections[key] = vxFTPConnector(host, port, user, passwd)
            logger.info(f"创建FTP连接：{self.__class__._connections[key]}")
        self._ftp_conn = self.__class__._connections[key]
        self._remote_dir = pathlib.Path(root_dir, channel_name).as_posix()
        self._ftp_conn.mkdir(self._remote_dir)
        self._next_fetch_dt = 0
        self._interval = 1

    @property
    def channel_name(self) -> str:
        """消息渠道名称"""
        return self._channel_name

    def __str__(self) -> str:
        return (
            f"< {self.__class__.__name__}({self.channel_name}) with {self._ftp_conn} on"
            f" remote_dir: {self._remote_dir}"
        )

    def __eq__(self, __o: object) -> bool:
        return (
            self._channel_name == __o._channel_name
            and self._ftp_conn == __o._ftp_conn
            and self._remote_dir == __o._remote_dir
            if isinstance(__o, self.__class__)
            else False
        )

    def __call__(self) -> List[vxEvent]:
        now = vxtime.now()
        if now > self._next_fetch_dt:
            event_files = self._ftp_conn.list(self._remote_dir)
            self._next_fetch_dt = now + self._interval
            return [event for event in map(self._fetch_event, event_files) if event]

        return []

    def _fetch_event(self, event_file: str) -> vxEvent:
        """获取单个event

        Arguments:
            event_file {str} -- event_file文件名称

        Raises:
            ConnectionError: 连接出错

        Returns:
            vxEvent -- vxEvent实例
        """
        with io.BytesIO() as bfp:
            ftp_event_file = pathlib.Path(self._remote_dir, event_file).as_posix()

            is_download = self._ftp_conn.download(ftp_event_file, bfp)
            if is_download is False:
                logger.error(f"ConnectionError: 下载{event_file}发生错误")
                return None
            event = vxEvent.unpack(bfp.getvalue())
            self._ftp_conn.delete(ftp_event_file)
            return event
