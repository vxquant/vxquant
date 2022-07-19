"""zeromq 相关函数"""


__all__ = [
    "ZMQClient",
    "create_server",
    "create_client",
]

import os
import zmq
import zmq.auth
from zmq.auth import CURVE_ALLOW_ANY
from zmq.auth.thread import ThreadAuthenticator
import contextlib
from vxquant.utils import logger


@contextlib.contextmanager
def create_server(url, socket_type=None, secret_key=None):
    """
    获取server对象

    with self.get_server(socket_type=zmq.REP) as server:
        server.recv_pyobj()

    """

    if not socket_type:
        socket_type = zmq.REP

    ctx = zmq.Context().instance()
    server = ctx.socket(socket_type)
    if zmq.zmq_version_info() < (4, 0):
        logger.warning(
            f"Security is not supported in libzmq version < 4.0. libzmq version {zmq.zmq_version()}"
        )
        secret_key = None

    if secret_key and secret_key.endswith(".key_secret"):
        if not os.path.exists(secret_key):
            server_name = os.path.basename(secret_key).replace(".key_secret", "")
            key_dir = os.path.dirname(secret_key)
            zmq.auth.create_certificates(key_dir, server_name)
            logger.info(f"私钥文件:{secret_key} 创建完成.")

        auth = ThreadAuthenticator(ctx)
        auth.start()
        auth.configure_curve(domain="*", location=CURVE_ALLOW_ANY)
        auth.allow()

        server_public, server_secret = zmq.auth.load_certificate(secret_key)
        server.curve_publickey = server_public
        server.curve_secretkey = server_secret
        server.curve_server = True
        logger.info(f"启动加密模式,secret key文件: {secret_key}.")

    server.bind(url)
    logger.info(f"绑定 {url} 完成.")

    try:
        yield server
    except Exception as e:
        logger.error(f"{e}", exc_info=True)
        raise e from e
    finally:
        server.close()
        if secret_key and secret_key.endswith(".key_secret"):
            auth.stop()


def create_client(url, socket_type=None, public_key=None):
    """
    创建client对象
    """

    if zmq.zmq_version_info() < (4, 0):
        logger.warning(
            f"Security is not supported in libzmq version < 4.0. libzmq version {zmq.zmq_version()}"
        )

    if not socket_type:
        socket_type = zmq.REQ

    ctx = zmq.Context().instance()
    client = ctx.socket(socket_type)

    if public_key and os.path.exists(public_key):
        server_public, _ = zmq.auth.load_certificate(public_key)
        client.curve_serverkey = server_public
        client_name = f"client_{id(client)}"
        zmq.auth.create_certificates("./", client_name)
        client_public, client_secret = zmq.auth.load_certificate(
            f"{client_name}.key_secret"
        )
        client.curve_secretkey = client_secret
        client.curve_publickey = client_public
        os.remove(f"{client_name}.key")
        os.remove(f"{client_name}.key_secret")
        logger.info(f"启动加密模式,public key文件: {public_key}.")
    client.connect(url)
    return client


class ZMQClient(object):
    """可靠的zmq客户端"""

    def __init__(self, url, public_key=None):
        self._url = url
        self._ctx = zmq.Context().instance()

        self._client = None
        if zmq.zmq_version_info() > (4, 0) and public_key:
            self._public_key = public_key
            logger.info(f"启动加密模式,public key文件: {public_key}.")
        else:
            logger.warning("不启动加密模式.")
            self._public_key = None

        self._connect()

    def _connect(self):
        """链接远程服务器"""

        self._client = self._ctx.socket(zmq.REQ)
        if self._public_key and os.path.exists(self._public_key):
            server_public, _ = zmq.auth.load_certificate(self._public_key)
            self._client.curve_serverkey = server_public
            client_name = f"client_{id(self._client)}"
            zmq.auth.create_certificates("./", client_name)
            client_public, client_secret = zmq.auth.load_certificate(
                f"{client_name}.key_secret"
            )
            self._client.curve_secretkey = client_secret
            self._client.curve_publickey = client_public
            os.remove(f"{client_name}.key")
            os.remove(f"{client_name}.key_secret")
            logger.info(f"启动加密模式,public key文件: {self._public_key}.")

        self._client.connect(self._url)
        logger.info(f"链接 {self._url} 完成.")
        return self._client

    def send(self, pyobj):
        """发送数据"""
        # 重试5次以后，抛出异常
        for i in range(5):
            if not self._client:
                self._connect()

            self._client.send_pyobj(pyobj)
            if self._client.poll(2500) & zmq.POLLIN != 0:
                return self._client.recv_pyobj()

            self._client.setsockopt(zmq.LINGER, 0)
            self._client.close()
            self._client = None
            if i < 4:
                logger.info(f"{i+1}次发送失败，准备重试...")

        raise TimeoutError("接收超时.")
