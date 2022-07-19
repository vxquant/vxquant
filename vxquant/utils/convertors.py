# encoding=utf-8
"""转换器
    将各种类型的数据转换为各种类型的数据
"""


from functools import lru_cache, singledispatch, wraps
from enum import Enum
import time
import datetime
from typing import Optional


try:
    import six
except ImportError:
    six = None


try:
    import simplejson as json
except ImportError:
    import json


__all__ = [
    "to_timestring",
    "to_datetime",
    "to_timestamp",
    "to_enum",
    "to_json",
]


if time.localtime(time.time()).tm_isdst and time.daylight:
    local_tzinfo = datetime.timezone(datetime.timedelta(seconds=-time.altzone), "LTZ")
else:
    local_tzinfo = datetime.timezone(datetime.timedelta(seconds=-time.timezone), "LTZ")


@singledispatch
def to_timestring(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """
    将事件转换为格式化的日期字符串
    :param date_time:
    :return: time string
    """
    raise TypeError(f"Unsupported type: {type(date_time)}")


@to_timestring.register(float)
@to_timestring.register(int)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理timestamp类型"""
    return time.strftime(fmt, time.localtime(date_time))


@to_timestring.register(datetime.time)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理time类型"""
    return date_time.strftime("%H:%M:%S")


@to_timestring.register(datetime.date)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理date类型"""
    return date_time.strftime("%Y-%m-%d")


@to_timestring.register(datetime.datetime)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理datetime"""
    if date_time.tzinfo:
        date_time = date_time.astimezone(local_tzinfo)

    return date_time.strftime(fmt)


@to_timestring.register(time.struct_time)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理struct_time类型"""
    return time.strftime(fmt, date_time)


@to_timestring.register(str)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理str类型"""
    # todo 自动识别日期格式
    return date_time
    # *if fmt == "%Y-%m-%d %H:%M:%S":
    # *    return date_time
    # *
    # *date_time = to_timestamp(date_time)
    # *return default_tz.localize(datetime.datetime.fromtimestamp(date_time)).strftime(fmt)


@singledispatch
def to_datetime(date_time, fmt: str = "%Y-%m-%d %H:%M:%S"):
    """
    将date_time转换为datetime对象
    :param date_time:
    :param fmt:
    :return:
    """
    raise TypeError(f"Unsupported type: {type(date_time)}")


@to_datetime.register(str)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理str类型"""
    # todo 自动识别日期格式
    return datetime.datetime.strptime(date_time, fmt).astimezone(local_tzinfo)


@to_datetime.register(float)
@to_datetime.register(int)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理int类型"""

    return datetime.datetime.fromtimestamp(date_time).astimezone(local_tzinfo)


@to_datetime.register(time.struct_time)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理struct_time类型"""
    return datetime.datetime.fromtimestamp(time.mktime(date_time)).astimezone(
        local_tzinfo
    )


@to_datetime.register(datetime.date)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理date类型"""
    return datetime.datetime(
        date_time.year,
        date_time.month,
        date_time.day,
    ).astimezone(local_tzinfo)


@to_datetime.register(datetime.datetime)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    return date_time.astimezone(local_tzinfo)


@singledispatch
def to_timestamp(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """
    将date_time转换为timestamp
    :param date_time:
    :param fmt:
    :return: timestamp
    """
    raise TypeError(f"Unsupported type: {type(date_time)}")


@to_timestamp.register(datetime.datetime)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理datetime类型"""
    return date_time.timestamp()


@to_timestamp.register(time.struct_time)
def _(date_time, fofmtrmat="%Y-%m-%d %H:%M:%S"):
    """处理struct_time类型"""
    return time.mktime(date_time)


@to_timestamp.register(datetime.date)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理date类型"""
    return time.mktime(date_time.timetuple())


@to_timestamp.register(str)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理str类型"""
    # todo 自动识别日期格式
    return time.mktime(time.strptime(date_time, fmt))


@to_timestamp.register(float)
@to_timestamp.register(int)
def _(date_time, fmt="%Y-%m-%d %H:%M:%S"):
    """处理float类型"""
    return date_time


@lru_cache(100)
def to_enum(obj, enum_cls, default=None):
    """
    将obj转换为enum_cls的枚举对象
    :param obj: 待转换的对象
    :param enum_cls: 枚举类型
    :param default: 默认值
    :return: 枚举对象
    """
    try:

        if isinstance(obj, enum_cls):
            return obj
        elif obj in enum_cls.__members__:
            return enum_cls[obj]
        else:
            return enum_cls(obj)
    except ValueError as err:
        if default:
            return default
        else:
            raise ValueError(f"{obj} is not in {enum_cls}.") from err


@singledispatch
def _type_jsonencoder(obj):
    """
    将obj转换为json字符串
    :param obj:
    :return:
    """
    try:
        return str(obj)
    except TypeError as err:

        raise TypeError(f"Unsupported type: {type(obj)}") from err


_type_jsonencoder.register(Enum)(lambda obj: obj.name)
_type_jsonencoder.register(
    datetime.datetime, lambda obj: obj.strftime("%Y-%m-%d %H:%M:%S")
)
_type_jsonencoder.register(datetime.date, lambda obj: obj.strftime("%Y-%m-%d"))
_type_jsonencoder.register(datetime.time, lambda obj: obj.strftime("%H:%M:%S"))
_type_jsonencoder.register(datetime.timedelta, lambda obj: obj.total_seconds())


class vxJSONEncoder(json.JSONEncoder):
    """json编码器"""

    def default(self, o):
        try:
            return _type_jsonencoder(o)
        except TypeError:
            return json.JSONEncoder.default(self, o)

    @staticmethod
    def register(data_type):
        """注册一个类型

        Arguments:
            data_type -- 数据格式
        @vxJSONEncoder.register(datetime.datetime)
        def _(obj):
            return xxx_obj
        """

        def decorator(func):
            _type_jsonencoder.register(data_type, func)

            @wraps
            def wapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wapper

        return decorator


def to_json(obj, indent: int = 4, ensure_ascii=True, **kwargs):
    """转化为json格式"""
    return json.dumps(
        obj,
        cls=vxJSONEncoder,
        ensure_ascii=ensure_ascii,
        indent=indent,
        **kwargs,
    )


@lru_cache(100)
def combine_datetime(date_: str, time_: str = "00:00:00") -> float:
    """组合日期和时间"""
    return to_timestamp(f"{date_} {time_}")


if six:
    __all__ += [
        "to_text",
        "to_binary",
        "is_string",
        "byte2int",
    ]

    string_types = (six.string_types, six.text_type, six.binary_type)

    def to_text(value, encoding="utf-8"):
        """转化为文本格式

        Arguments:
            value {_type_} -- 待转化的对象

        Keyword Arguments:
            encoding {str} -- 编码格式 (default: {"utf-8"})

        Returns:
            six.text_type -- 文件格式
        """ """ """
        if isinstance(value, six.text_type):
            return value
        if isinstance(value, six.binary_type):
            return value.decode(encoding)
        return six.text_type(value)

    def to_binary(value, encoding="utf-8"):
        """转换成二进制格式

        Arguments:
            value -- 待转化的对象

        Keyword Arguments:
            encoding -- 编码格式 (default: {"utf-8"})

        Returns:
            转换后二进制格式
        """
        if isinstance(value, six.binary_type):
            return value
        if isinstance(value, six.text_type):
            return value.encode(encoding)
        return six.binary_type(value)

    def is_string(value):
        """转换成sttring'格式

        Arguments:
            value -- 待转换的对象

        Returns:
            转换后string格式
        """
        return isinstance(value, string_types)

    def byte2int(s, index=0):
        """Get the ASCII int value of a character in a string.
        :param s: a string
        :param index: the position of desired character
        :return: ASCII int value
        """
        return ord(s[index]) if six.PY2 else s[index]
