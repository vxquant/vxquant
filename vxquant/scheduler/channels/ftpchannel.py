"""ftp消息通道"""

import io
import os
from queue import Empty
import pathlib
from typing import Any, Optional
from vxquant.scheduler.triggers import TriggerStatus, vxTrigger
from vxquant.scheduler.channels import vxChannel
from vxquant.scheduler.event import vxEvent
from vxquant.utils import logger, vxtime
from vxquant.utils.net import vxFTPConnector


def _to_event_rank(filename: str) -> tuple:
    """转换为 (timestamp, filename)的组合"""
    return float(pathlib.Path(filename).name.split("||")[0]), filename


class vxFTPChannel(vxChannel):
    """FTP消息通道"""

    _connections = {}

    def __init__(
        self,
        channel_name,
        host="127.0.0.1",
        port=21,
        user="",
        passwd="",
        basepath="/",
        **kwargs,
    ):
        super(vxFTPChannel, self).__init__(channel_name, **kwargs)

        key = hash(f"ftp://{user}:{passwd}@{host}:{port}")
        if key not in vxFTPChannel._connections:
            vxFTPChannel._connections[key] = vxFTPConnector(host, port, user, passwd)
            logger.info(f"创建FTP连接：{vxFTPChannel._connections[key]}")

        self._ftp_conn = vxFTPChannel._connections[key]
        self._remote_dir = pathlib.PurePath(basepath, channel_name).as_posix()
        channel_names = self._ftp_conn.list(basepath)
        logger.info(f"channel_names: {channel_names}")

        if self._remote_dir not in channel_names:
            self._ftp_conn.mkdir(self._remote_dir)

    def __str__(self):
        return f"< {self.__class__.__name__} on channel({self.name}) with remote_dir: ({self._remote_dir}) >"

    def __repr__(self):
        return f"< {self.__class__.__name__} on channel({self.name}) with remote_dir: ({self._remote_dir}) >"

    @property
    def next_trigger_dt(self):
        remote_files = self._ftp_conn.list(self._remote_dir)
        if not remote_files:
            return None

        next_trigger_dt, _ = min(map(_to_event_rank, remote_files))
        return next_trigger_dt

    def get(self, timestamp_=None, timeout=1):
        try:
            remote_files = self._ftp_conn.list(self._remote_dir)
            if not remote_files:
                raise Empty

            next_trigger_dt, next_event_file = min(map(_to_event_rank, remote_files))
            if timestamp_ is not None and timestamp_ < next_trigger_dt:
                raise Empty

            with io.BytesIO() as bfp:
                is_download = self._ftp_conn.download(next_event_file, bfp)
                if is_download is False:
                    raise ConnectionError(f"下载{next_event_file}发生错误..")
                event = vxEvent.unpack(bfp.getvalue())
                self._ftp_conn.delete(next_event_file)
                return event

        except Empty:
            vxtime.sleep(timeout)

        except Exception as err:
            logger.error(
                f"{self} get file({next_event_file}) error: {err}", exc_info=True
            )
        return None

    def put(
        self,
        event: str | vxEvent,
        data: Any = None,
        trigger: Optional[vxTrigger] = None,
        priority=10,
        **kwargs,
    ) -> None:
        # def put(self, event: str | vxEvent, data: Any = None, trigger:vxTrigger=None, next_trigger_dt:Optional[float]=None):
        """上传消息至FTP服务器

        Arguments:
            event {_type_} -- 消息Event类型或者str类型

        Keyword Arguments:
            event_data {str} -- 消息data (default: {""})
            reply_to {str} -- 回复序列标识 (default: {""})
            channel {str} -- 消息渠道 暂时未启用 (default: {""})

        """
        if isinstance(event, str):
            if trigger.status == TriggerStatus.Completed:
                logger.warning(f"{trigger} is completed.")
                return

            next_trigger_dt = next(trigger, None) if trigger else vxtime.now()
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
            picked_event = vxEvent.pack(send_event)
            remote_file = os.path.join(
                self._remote_dir, f"{send_event.next_trigger_dt}||{send_event.id}.pkl"
            )
            with io.BytesIO(picked_event) as bfp:
                self._ftp_conn.upload(bfp, remote_file)
                logger.debug(
                    f"{self} put event.type({send_event.type}) to remote({remote_file}). {send_event}"
                )

        except Exception as err:
            logger.error(
                f"{self} put event.type({send_event.type}) to remote({remote_file}). error: {err}",
                exc_info=True,
            )

    def clear(self):
        remote_files = self._ftp_conn.list(self._remote_dir)
        return list(map(self._ftp_conn.delete, remote_files))
