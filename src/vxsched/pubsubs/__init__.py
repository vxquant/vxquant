"""各种eventbrokers"""

from vxutils import logger
from .base import vxPublisher, vxSubscriber
from .ftp import vxFTPPublisher, vxFTPSubscriber

try:
    from .zeromq import vxZMQPublisher, vxZMQSubscriber, vxZMQRpcClient
except ImportError as e:
    logger.error(
        f"Import zmq ERROR: {e},please use command to fix it :  pip install -U pyzmq "
    )
    vxZMQPublisher = None
    vxZMQSubscriber = None
    vxZMQRpcClient = None

__all__ = [
    "vxPublisher",
    "vxSubscriber",
    "vxZMQPublisher",
    "vxZMQSubscriber",
    "vxFTPPublisher",
    "vxFTPSubscriber",
    "vxZMQRpcClient",
]
