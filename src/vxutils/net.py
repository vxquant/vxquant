# encoding=utf-8
"""网络工具包
    vxFTPConnector : FTP连接器
"""


import contextlib
import ftplib
import os
import time
from multiprocessing import Lock
from ftplib import FTP, all_errors, Error as FTPError
import requests
import vxutils

__all__ = [
    "vxFTPConnector",
    "vxWeChatClient",
]


class vxFTPConnector:
    """FTP网络连接器"""

    def __init__(self, host="", port=21, user="", passwd=""):
        self._host = host
        self._port = port
        self._user = user
        self._passwd = passwd
        self._timeout = 0
        self._lock = Lock()
        self._ftp = None

    @vxutils.retry(3)
    def login(self):
        """登录ftp服务器"""

        if self._ftp:
            self.logout()

        try:
            self._ftp = FTP()
            self._ftp.encoding = "GB2312"
            self._ftp.connect(self._host, self._port)
            self._ftp.login(self._user, self._passwd)
            time.sleep(0.1)
            vxutils.logger.debug(f"ftp login Success.{self._ftp.pwd()}")
            self._timeout = time.time() + 60
            return True
        except all_errors as e:
            vxutils.logger.error(f"ftp login error. {e}")
            return False

    def __str__(self) -> str:
        return f"ftp://{self._user}@{self._host}:{self._port}/"

    __repr__ = __str__

    def logout(self):
        """登出ftp服务器"""
        with contextlib.suppress(all_errors):
            self._ftp.quit()
            self._ftp = None
            self._timeout = 0

    @contextlib.contextmanager
    def autologin(self):
        """自动登录ftp服务器"""
        now = time.time()
        wait_to_retry = 0.3
        with self._lock:
            for i in range(1, 6):
                if self._ftp and now <= self._timeout:
                    break
                elif self._ftp:
                    with contextlib.suppress(all_errors):
                        self._ftp.pwd()
                        self._timeout = now + 60
                        break

                if self.login():
                    break
                wait_to_retry = min(wait_to_retry + i * 0.3, 3)

                if i >= 5:
                    raise FTPError("ftp connect error ...")

                vxutils.logger.info(
                    f"auto login  wait {wait_to_retry}s to retry the {i}th times ..."
                )
                time.sleep(wait_to_retry)

            try:
                yield self._ftp
                self._timeout = time.time() + 60
            except all_errors as err:
                self._timeout = 0
                vxutils.logger.info(f"FTP Error occur: {err}")

    def mkdir(self, remote_dir):
        """创建远程目录"""

        with self.autologin():
            self._ftp.mkd(remote_dir)
            vxutils.logger.debug(f"ftp mkdir Success.{remote_dir}")
        return self._timeout > 0

    def rmdir(self, remote_dir):
        """删除远程目录"""

        with self.autologin():
            self._ftp.rmd(remote_dir)
            vxutils.logger.debug(f"ftp rmdir Success.{remote_dir}")
        return self._timeout > 0

    def list(self, remote_dir):
        """list远程目录"""
        with self.autologin():
            remote_files = self._ftp.nlst(remote_dir)
        return (
            [os.path.join(remote_dir, remote_file) for remote_file in remote_files]
            if self._timeout > 0
            else []
        )

    def download(self, remote_file, local_file):
        """FTP下载文件

        Arguments:
            remote_file -- 远程文件路径
            local_file -- 本地文件目录_

        Returns:
            False -- 下载失败
            True  -- 下载成功
        """

        with self.autologin():
            if isinstance(local_file, str):
                with open(local_file, "wb") as fp:
                    self._ftp.retrbinary(f"RETR {remote_file}", fp.write)
            else:
                fp = local_file
                self._ftp.retrbinary(f"RETR {remote_file}", fp.write)
        return self._timeout > 0

    def upload(self, local_file, remote_file):
        """上传本地文件

        Arguments:
            local_file -- 本地文件
            remote_file -- 远程文件

        Returns:
            True -- 上传成功
            False -- 上传失败
        """

        with self.autologin():
            if isinstance(local_file, str):
                with open(local_file, "rb") as fp:
                    self._ftp.storbinary(f"STOR {remote_file}", fp)
            else:
                fp = local_file
                self._ftp.storbinary(f"STOR {remote_file}", fp)
        return self._timeout > 0

    def delete(self, remote_file):
        """删除ftp文件

        Arguments:
            remote_file -- 远程文件

        Returns:
            True -- 删除成功
            False -- 删除失败
        """

        with self.autologin():
            self._ftp.delete(remote_file)
        return self._timeout > 0

    def __eq__(self, __o: object) -> bool:
        return (
            (
                self._host == __o._host
                and self._port == __o._port
                and self._user == __o._user
                and self._passwd == __o._passwd
            )
            if isinstance(__o, vxFTPConnector)
            else False
        )


class vxWeChatClient:
    """微信消息发送类"""

    def __init__(self, corpid, secret, agentid, timeout=5):
        """
        微信客户端
        """
        self._corpid = corpid
        self._secret = secret
        self._agentid = agentid
        self._timeout = timeout
        self._access_token = None
        self._expire_time = None

    @property
    def token(self):
        """
        获取access_token

        请求方式： GET（HTTPS）
        请求地址： https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=ID&corpsecret=SECRET

        返回结果:
        {
            "errcode": 0,
            "errmsg": "ok",
            "access_token": "accesstoken000001",
            "expires_in": 7200
        }
        """
        if not self._access_token or self._expire_time < time.time():
            resp = requests.get(
                f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self._corpid}&corpsecret={self._secret}",
                timeout=self._timeout,
            )
            resp.raise_for_status()
            ret_mesg = resp.json()
            if ret_mesg.get("errcode") != 0:
                vxutils.logger.info(f"获取access_token失败. {ret_mesg}")
                raise ConnectionError(f"获取access_token失败. {ret_mesg}")

            self._access_token = ret_mesg.get("access_token")
            self._expire_time = time.time() + ret_mesg.get("expires_in", 0) - 10
            vxutils.logger.info(
                f"更新access_token: {self._access_token}， 过期时间: {self._expire_time}"
            )
        return self._access_token

    def send_message(self, markdown_content, users=None, parties=None, tags=None):
        """
        发送企业微信markdown消息

        请求方式：POST（HTTPS）
        请求地址： https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=ACCESS_TOKEN

        body:为消息内容
        {
            "touser" : users or "@all",
            "toparty" : "PartyID1|PartyID2",
            "totag" : "TagID1 | TagID2",
            "msgtype": "markdown",
            "agentid" : 1,
            "markdown": {
                    "content": "您的会议室已经预定，稍后会同步到`邮箱`
                        >**事项详情**
                        >事　项：<font color=\"info\">开会</font>
                        >组织者：@miglioguan
                        >参与者：@miglioguan、@kunliu、@jamdeezhou、@kanexiong、@kisonwang
                        >
                        >会议室：<font color=\"info\">广州TIT 1楼 301</font>
                        >日　期：<font color=\"warning\">2018年5月18日</font>
                        >时　间：<font color=\"comment\">上午9:00-11:00</font>
                        >
                        >请准时参加会议。
                        >
                        >如需修改会议信息，请点击：[修改会议信息](https://work.weixin.qq.com)"
            },
            "enable_duplicate_check": 0,
            "duplicate_check_interval": 1800
        }
        """
        post_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={self.token}"
        msg = {
            "touser": "|".join(users) if users else "@all",
            "toparty": "|".join(parties) if parties else "",
            "totag": "|".join(tags) if tags else "",
            "msgtype": "markdown",
            "agentid": self._agentid,
            "markdown": {"content": markdown_content},
            "enable_duplicate_check": 0,
            "duplicate_check_interval": 1800,
        }
        resp = requests.post(post_url, json=msg, timeout=self._timeout)
        resp.raise_for_status()
        ret_msg = resp.json()
        if ret_msg.get("errcode") != 0:
            vxutils.logger.error(f"发送消息失败. {ret_msg}")
            raise ConnectionError(f"发送消息失败. {ret_msg}")

        return ret_msg.get("msgid")
