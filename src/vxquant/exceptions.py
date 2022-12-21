"""账户异常类"""


import sys

from enum import Enum
from vxutils.exceptions import vxException, importlib_exceptions
from vxquant.model.contants import OrderRejectReason


class RuntimeError(Enum):
    RiskManaget = 1


__all__ = []

__all__.extend(importlib_exceptions(OrderRejectReason, 300, sys.modules[__name__]))
