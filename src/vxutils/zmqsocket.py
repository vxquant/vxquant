"""zeromq 相关函数"""

import os
import zmq
import secrets
import pickle
import asyncio
import pathlib
import contextlib
from zmq.auth import CURVE_ALLOW_ANY
from zmq.auth.thread import ThreadAuthenticator
from zmq.asyncio import Context as AsyncContext
from zmq.asyncio import Socket as AsyncSocket
from zmq.auth.asyncio import AsyncioAuthenticator
from queue import Empty, Queue
from multiprocessing import Lock
from multiprocessing.dummy import Process
from typing import Callable
from vxutils import (
    logger,
    to_binary,
)

__all__ = [
    "vxZMQContext",
    "vxSecSocket",
    "vxAsyncSecSocket",
    "vxAsyncZMQContext",
    "vxZMQRequest",
    "vxAsyncServer",
    "vxZMQBackendThread",
]


class vxZMQAuthenticator:
    _auth_thread = None
    _auth_async = None

    def __init__(self, zsocket):
        """启动加密线程

        Arguments:
            zsocket {socket} -- zmq的socket


        Raises:
            FileNotFoundError: 密钥文件不存在
        """

    @classmethod
    def start_auth(cls, is_async=False):
        if cls._auth_thread is None and is_async is False:
            cls._auth_thread = ThreadAuthenticator()
            cls._auth_thread.start()
            cls._auth_thread.configure_curve(domain="*", location=CURVE_ALLOW_ANY)
            cls._auth_thread.allow()

        elif cls._auth_async is None and is_async is True:
            cls._auth_async = AsyncioAuthenticator()
            cls._auth_async.start()
            cls._auth_async.configure_curve(domain="*", location=CURVE_ALLOW_ANY)
            cls._auth_async.allow()


class vxSecSocket(zmq.Socket):
    """构建加密的ZMQ socket链接工具集合"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__dict__["_lock"] = None

    @property
    def lock(self):
        """锁"""
        if self._lock is None:
            self.__dict__["_lock"] = Lock()
        return self.__dict__["_lock"]

    def bind(self, addr: str, secret_key: str = ""):
        if secret_key and pathlib.Path(secret_key).is_file():
            vxZMQAuthenticator.start_auth(is_async=False)
            public_keystr, secret_keystr = zmq.auth.load_certificate(secret_key)
            self.curve_publickey = public_keystr
            self.curve_secretkey = secret_keystr
            self.curve_server = True
            logger.info(f"启动加密模式, server public key: {public_keystr}.")
        logger.info(f"绑定 {addr} 完成.")
        return super().bind(addr)

    def connect(self, addr: str = "", public_key: str = ""):
        """创建连接服务器socket

        Keyword Arguments:
            addr {str} -- 服务器地址 (default: {""})
            public_key {str} -- 服务器公钥 (default: {""})

        """
        if zmq.zmq_version_info() < (4, 0):
            logger.warning(
                "Security is not supported in libzmq version < 4.0. libzmq version"
                f" {zmq.zmq_version()}"
            )
            public_key = None

        if public_key and os.path.exists(public_key):
            server_public, _ = zmq.auth.load_certificate(public_key)
            self.curve_serverkey = server_public
            self.curve_publickey, self.curve_secretkey = zmq.curve_keypair()
            logger.info(f"启动加密模式,public server public key: {server_public}.")

        ret = super().connect(addr)
        logger.info(f"connect to {addr} ...")
        return ret


class vxZMQContext(zmq.Context):
    """ZMQ context"""

    _socket_class = vxSecSocket


class vxAsyncSecSocket(AsyncSocket):
    """构建加密的ZMQ socket链接工具集合"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__["secret_mode"] = False
        self.__dict__["_lock"] = None

    def lock(self):
        """锁"""
        return self._lock

    def bind(self, addr: str, secret_key: str = ""):
        """绑定地址"""
        if secret_key and pathlib.Path(secret_key).is_file():
            vxZMQAuthenticator.start_auth(is_async=True)
            public_keystr, secret_keystr = zmq.auth.load_certificate(secret_key)
            self.curve_publickey = public_keystr
            self.curve_secretkey = secret_keystr
            self.curve_server = True
            self.__dict__["secret_mode"] = True
            logger.info(f"启动加密模式,secret key文件: {secret_key}.")

        logger.info(f"绑定 {addr} 完成.")
        return super().bind(addr)

    def connect(self, addr: str = "", public_key: str = ""):
        """创建连接服务器socket

        Keyword Arguments:
            addr {str} -- 服务器地址 (default: {""})
            public_key {str} -- 服务器公钥 (default: {""})

        """
        if zmq.zmq_version_info() < (4, 0):
            logger.warning(
                "Security is not supported in libzmq version < 4.0. libzmq version"
                f" {zmq.zmq_version()}"
            )
            public_key = None

        if public_key and os.path.exists(public_key):
            server_public, _ = zmq.auth.load_certificate(public_key)
            self.curve_serverkey = server_public
            self.curve_publickey, self.curve_secretkey = zmq.curve_keypair()
            logger.info(f"启动加密模式,server public key文件: {public_key}.")

        logger.info(f"链接 {addr} 完成.")
        return super().connect(addr)


class vxAsyncZMQContext(AsyncContext):
    """ZMQ context"""

    _socket_class = vxAsyncSecSocket


class vxZMQRequest:
    def __init__(
        self,
        url: str,
        public_key: str,
        serializer=None,
        deserializer=None,
        clientid=None,
    ) -> None:
        self._url = url
        self._public_key = public_key
        self._ctx = None
        self._socket = None
        self._serializer = serializer if callable(serializer) else pickle.dumps
        self._deserializer = deserializer if callable(deserializer) else pickle.loads
        self._clientid = (
            to_binary(clientid) if clientid is not None else secrets.token_bytes(16)
        )

    @property
    def socket(self):
        if self._socket is None:
            self._ctx = vxZMQContext()
            self._socket = self._ctx.socket(zmq.REQ)
            self._socket.setsockopt(zmq.IDENTITY, self._clientid)
            self._socket.connect(self._url, self._public_key)

        return self._socket

    def reset(self) -> None:
        """重置连接"""
        if self._socket:
            with self._socket.lock:
                self._socket.setsockopt(zmq.LINGER, 0)
                self._socket.close()
                self._ctx.destroy(0)

        self._ctx = None
        self._socket = None

    def __str__(self) -> str:
        return f"< {self.__class__.__name__} (id-{id(self)}) connect to {self._url}."

    def __call__(self, obj):
        with self.socket.lock:
            packed_obj = self._serializer(obj)
            self.socket.send(packed_obj)
            flags = self.socket.poll(3000, zmq.POLLIN)
            if flags & zmq.POLLIN == 0:
                raise TimeoutError("连接超时")

            packed_obj = self.socket.recv()
            return self._deserializer(packed_obj)


class vxAsyncServer:
    def __init__(
        self, socket_type, url, secret_key=None, send_queue=None, bind_mode=True
    ):
        self._ctx = vxAsyncZMQContext().instance()
        self._socket = self._ctx.socket(socket_type)
        if bind_mode:
            self._socket.bind(url, secret_key)
        else:
            self._socket.connect(url, secret_key)
        self._active = False
        self._queue = send_queue if send_queue is None else Queue()

    @property
    def socket(self):
        """socket"""
        return self._socket

    async def receiver(self, callback) -> None:
        """接收进程

        Arguments:
            callback {Callable} -- 回调函数
        """
        while self._active:
            flags = await self._socket.poll(zmq.POLLIN)
            if flags & zmq.POLLIN != 0:
                msg = await self._socket.recv_multipart()
                callback(msg)

    async def sender(self, serializer=None) -> None:
        """发送

        Arguments:
            serializer {callable} -- 序列化函数
        """
        while self._active:
            try:
                msg = self._queue.get_nowait()
                print(msg)

                if (not isinstance(msg, bytes)) and serializer:
                    msg = serializer(msg)

                await self._socket.send(msg)
            except Empty:
                await asyncio.sleep(0.5)

    async def run(self, callback: callable, serializer: callable) -> None:
        wait_tasks = []
        if callable(callback):
            wait_tasks.append(self.receiver(callback))

        wait_tasks.append(self.sender(serializer))

        if not wait_tasks:
            logger.warning("callback and msg_queue 不满足条件")

        self._active = True
        logger.info(f"开始运行 {self}")
        await asyncio.gather(*wait_tasks)
        self._active = False
        logger.info(f"开始结束 {self}")

    def send(self, msg) -> None:
        self._queue.put(msg)


class vxZMQBackendThread(Process):
    def __init__(
        self, on_send_callback: Callable = None, on_recv_callback: Callable = None
    ) -> None:
        self._zmqctx = None
        self._socket = None
        self._active = False
        self._queue = Queue()
        self._on_send_callback = on_send_callback
        self._on_recv_callback = on_recv_callback

        super().__init__()
        name = self.getName()
        self.setName(name.replace("Thread", self.__class__.__name__))

    def set_on_send_callback(self, callback: Callable = None) -> None:
        self._on_send_callback = callback

    def set_on_recv_callback(self, callback: Callable = None) -> None:
        self._on_recv_callback = callback

    def send(self, *msgs) -> None:
        """发送消息"""
        self._queue.put(msgs)

    def bind(self, socket_type, addr: str, secret_key: str = ""):
        if self._active is True:
            return
        self._active = True
        self._zmqctx = vxZMQContext().instance()
        self._socket = self._zmqctx.socket(socket_type)
        self._socket.bind(addr, secret_key)
        return self

    def connect(self, socket_type, addr: str, public_key: str = ""):
        if self._active is True:
            return
        self._active = True
        self._zmqctx = vxZMQContext().instance()
        self._socket = self._zmqctx.socket(socket_type)
        self._socket.connect(addr, public_key)

    def run(self) -> None:
        if self._active is False:
            logger.info("请先调用 activate(url, public_key=None)进行初始化操作. 后运行")
            return

        logger.info(f"{self.name} (id-{id(self)}) 启动运行...")

        try:
            while self._active:
                flags = self._socket.poll(1000, zmq.POLLIN | zmq.POLLOUT)

                if self._on_recv_callback and flags & zmq.POLLIN != 0:
                    msgs = self._socket.recv_multipart()
                    logger.debug(f"recive msgs: {msgs}")
                    self._on_recv_callback(self, *msgs)

                if flags & zmq.POLLOUT != 0:
                    with contextlib.suppress(Empty):
                        msgs = self._queue.get(timeout=0.1)
                        if self._on_send_callback:
                            msgs = self._on_send_callback(self, *msgs)
                        self._socket.send_multipart(list(map(to_binary, msgs)))
        finally:
            logger.info(f"{self.name} (id-{id(self)}) 停止运行...")
            self.stop()

    def close(self) -> None:
        if self._active is False:
            return
        self.stop()

    def stop(self) -> None:
        self._active = False
        # self.join()
        if self._socket:
            self._socket.setsockopt(zmq.LINGER, 0)
            self._socket.close()
            self._socket = None
            self._zmqctx = None
