"""python 工具箱"""

import logging
import builtins
from vxutils.cache import (
    cache,
    Timer,
    EndlessTimer,
    TTLTimer,
    MemoryCacheStorage,
    MongoDBCacheStorage,
    CacheExpiredException,
    NotCacheException,
)
from vxutils.convertors import (
    to_timestring,
    to_datetime,
    to_timestamp,
    to_enum,
    to_json,
    combine_datetime,
    vxJSONEncoder,
    to_text,
    to_binary,
    is_string,
    byte2int,
)

from vxutils.decorators import (
    retry,
    timeit,
    singleton,
    threads,
    lazy_property,
    timeout,
    storage,
)

from vxutils.log import vxLoggerFactory
from vxutils.time import vxtime
from vxutils.net import vxFTPConnector, vxWeChatClient
from vxutils.toolbox import vxToolBox, import_tools, vxWrapper
from vxutils.dataclass import (
    vxField,
    vxUUIDField,
    vxEnumField,
    vxIntField,
    vxFloatField,
    vxPropertyField,
    vxDatetimeField,
    vxBoolField,
    vxDataMeta,
    vxDataClass,
    vxDataConvertor,
    vxDict,
)
from vxutils.debug import debug_log


_old_factory = logging.getLogRecordFactory()


def _record_factory(*args, **kwargs):
    """记录工厂"""
    record = _old_factory(*args, **kwargs)
    record.asctime = to_timestring(vxtime.now(), "%F %T.%f")
    return record


logging.setLogRecordFactory(_record_factory)

vxLogging = vxLoggerFactory()
logger = vxLogging.getLogger("vxquant.log")


setattr(builtins, "debug_log", debug_log)
setattr(builtins, "logger", logger)
setattr(builtins, "vxtime", vxtime)


__all__ = [
    "cache",
    "Timer",
    "EndlessTimer",
    "TTLTimer",
    "MemoryCacheStorage",
    "MongoDBCacheStorage",
    "CacheExpiredException",
    "NotCacheException",
    "to_timestring",
    "to_datetime",
    "to_timestamp",
    "to_enum",
    "to_json",
    "combine_datetime",
    "vxJSONEncoder",
    "retry",
    "timeit",
    "singleton",
    "threads",
    "lazy_property",
    "timeout",
    "storage",
    "to_text",
    "to_binary",
    "is_string",
    "byte2int",
    "vxField",
    "vxUUIDField",
    "vxEnumField",
    "vxIntField",
    "vxFloatField",
    "vxPropertyField",
    "vxDatetimeField",
    "vxBoolField",
    "vxDataMeta",
    "vxDataClass",
    "vxDataConvertor",
    "vxDict",
    "vxFTPConnector",
    "vxWeChatClient",
    "vxToolBox",
    "import_tools",
    "vxWrapper",
]

try:
    from vxutils.zmqsocket import (
        vxZMQContext,
        vxSecSocket,
        vxAsyncSecSocket,
        vxAsyncZMQContext,
        vxZMQRequest,
        vxAsyncServer,
        vxZMQBackendThread,
    )

    __all__ += [
        "vxZMQContext",
        "vxSecSocket",
        "vxAsyncSecSocket",
        "vxAsyncZMQContext",
        "vxZMQRequest",
        "vxAsyncServer",
        "vxZMQBackendThread",
    ]
except ImportError:
    logger.warning("zeromq包导入失败，请安装pyzmq: pip install -U pyzmq.")
