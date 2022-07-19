# encoding=utf-8
"""网络工具包
    vxFTPConnector : FTP连接器
"""


import os
import time
from multiprocessing import Lock
from ftplib import FTP, all_errors
import requests
from vxquant.utils.decorators import retry, threads
from vxquant.utils import logger


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

    @retry(3)
    def login(self):
        """登录ftp服务器"""
        with self._lock:
            self._ftp = FTP()
            self._ftp.encoding = "GB2312"
            self._ftp.connect(self._host, self._port)
            self._ftp.login(self._user, self._passwd)
            time.sleep(0.1)
            logger.debug(f"ftp login Success.{self._ftp.pwd()}")
            self._timeout = time.time() + 60

    def logout(self):
        """登出ftp服务器"""
        with self._lock:
            self._ftp.quit()
            self._ftp = None
            self._timeout = 0

    def autologin(self):
        """自动登录ftp服务器"""
        now = time.time()
        if not self._ftp:
            self.login()
        elif now > self._timeout:
            try:
                with self._lock:
                    self._ftp.pwd()
                    self._timeout = now + 60
            except all_errors as err:
                self._ftp = None
                self._timeout = 0
                logger.debug(f"ftp autologin Error. {err}")
                self.login()

        return True

    def mkdir(self, remote_dir):
        """创建远程目录"""
        try:
            if not self.autologin():
                return False

            with self._lock:
                self._ftp.mkd(remote_dir)
                logger.debug(f"ftp mkdir Success.{remote_dir}")
                return True
        except all_errors as err:
            logger.error(f"ftp autologin Error. {err}", exc_info=True)
            self._ftp = None
            return False

    def rmdir(self, remote_dir):
        """删除远程目录"""
        try:
            if not self.autologin():
                return False

            with self._lock:
                self._ftp.rmd(remote_dir)
                logger.debug(f"ftp rmdir Success.{remote_dir}")
                return True
        except all_errors as err:
            logger.error(f"ftp autologin Error. {err}", exc_info=True)
            self._ftp = None
            return False

    def list(self, remote_dir):
        """list远程目录"""
        try:
            if not self.autologin():
                return []

            with self._lock:
                remote_files = self._ftp.nlst(remote_dir)
            remote_files = [
                os.path.join(remote_dir, remote_file) for remote_file in remote_files
            ]
        except all_errors as err:
            logger.error(f"ftp autologin Error. {err}", exc_info=True)
            self._ftp = None
            return []
        return remote_files

    def download(self, remote_file, local_file):
        """FTP下载文件

        Arguments:
            remote_file -- 远程文件路径
            local_file -- 本地文件目录_

        Returns:
            False -- 下载失败
            True  -- 下载成功
        """

        try:
            if not self.autologin():
                return False
            with self._lock:
                if isinstance(local_file, str):
                    with open(local_file, "wb") as fp:
                        self._ftp.retrbinary(f"RETR {remote_file}", fp.write)
                else:
                    fp = local_file
                    self._ftp.retrbinary(f"RETR {remote_file}", fp.write)
                return True
        except all_errors as err:
            logger.error(
                f"ftp download file({remote_file}) error: {err}", exc_info=True
            )
            return False

    def upload(self, local_file, remote_file):
        """上传本地文件

        Arguments:
            local_file -- 本地文件
            remote_file -- 远程文件

        Returns:
            True -- 上传成功
            False -- 上传失败
        """
        try:
            if not self.autologin():
                return False

            with self._lock:
                if isinstance(local_file, str):
                    with open(local_file, "rb") as fp:
                        self._ftp.storbinary(f"STOR {remote_file}", fp)
                else:
                    fp = local_file
                    self._ftp.storbinary(f"STOR {remote_file}", fp)
                return True
        except all_errors as err:
            logger.error(f"ftp upload {remote_file} error. {err}.", exc_info=True)
            return False

    def delete(self, remote_file):
        """删除ftp文件

        Arguments:
            remote_file -- 远程文件

        Returns:
            True -- 删除成功
            False -- 删除失败
        """
        try:
            if not self.autologin():
                return False

            with self._lock:
                self._ftp.delete(remote_file)
                return True
        except all_errors as err:
            logger.error(f"ftp delete {remote_file} error. {err}", exc_info=True)
            return False

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
                logger.info(f"获取access_token失败. {ret_mesg}")
                raise ConnectionError(f"获取access_token失败. {ret_mesg}")

            self._access_token = ret_mesg.get("access_token")
            self._expire_time = time.time() + ret_mesg.get("expires_in", 0) - 10
            logger.info(
                f"更新access_token: {self._access_token}， 过期时间: {self._expire_time}"
            )
        return self._access_token

    @threads(5)
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
            logger.error(f"发送消息失败. {ret_msg}")
            raise ConnectionError(f"发送消息失败. {ret_msg}")

        return ret_msg.get("msgid")
