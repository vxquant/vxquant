"""异常类"""

from enum import Enum
import importlib
import sys


class vxException(Exception):
    """Exception 基类，带error no"""

    error_no = 0

    def __init__(self, *args):
        if self.error_no:
            msg = f"ErrorNo.{self.error_no} === {args}"
            super(vxException, self).__init__(msg)
        else:
            super(vxException, self).__init__(*args)


def importlib_exceptions(enum_cls, error_no_prefix=None, mod=None):
    """根据枚举类，自动创建exception类

    class ValueError(Enum):
        TooBigError = 3
        TooSmallError = 4
        EqualZero = 99

    exceptions = build_exections(ValueError, "100")

    相当于创建了:
    class ValueErrorException(vxException):
        error_no = 100-000

    class TooBigError(ValueErrorException):
        error_no = 100-003

    class TooSmallError(ValueErrorException):
        error_no = 100-004

    class EqualZero(ValueErrorException):
        error_no = 100-099

    """
    cls_name = f"{enum_cls.__name__}Exception"

    if error_no_prefix is None:
        error_no_prefix = 0

    if mod is None:
        mod = sys.modules.get(__name__, None)

    ret_cls_names = [cls_name]
    base_exception = type(
        cls_name, (vxException,), {"error_no": f"{error_no_prefix:03}-000"}
    )
    setattr(mod, cls_name, base_exception)

    for enum_name in enum_cls.__members__:
        ret_cls_names.append(enum_name)
        exception_cls = type(
            enum_name,
            (base_exception,),
            {"error_no": f"{error_no_prefix:03}-{enum_cls[enum_name].value:03}"},
        )
        setattr(
            mod,
            enum_name,
            exception_cls,
        )

    return ret_cls_names
