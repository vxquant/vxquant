# encoding=utf-8
"""转换器
    将各种类型的数据转换为各种类型的数据
"""

from typing import Any, Optional, Union
from functools import lru_cache, singledispatch, wraps
from enum import Enum
import time
import datetime
from dateutil import parser


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
    "combine_datetime",
    "vxJSONEncoder",
]

ZERO = datetime.timedelta(0)
HOUR = datetime.timedelta(hours=1)
SECOND = datetime.timedelta(seconds=1)


STDOFFSET = datetime.timedelta(seconds=-time.timezone)
if time.localtime(time.time()).tm_isdst and time.daylight:
    DSTOFFSET = datetime.timedelta(seconds=-time.altzone)
else:
    DSTOFFSET = STDOFFSET

DSTDIFF = DSTOFFSET - STDOFFSET


class LocalTimezone(datetime.tzinfo):
    """本地时区"""

    def fromutc(self, dt):
        assert dt.tzinfo is self
        stamp = (dt - datetime.datetime(1970, 1, 1, tzinfo=self)) // SECOND
        args = time.localtime(stamp)[:6]
        dst_diff = DSTDIFF // SECOND
        fold = args == time.localtime(stamp - dst_diff)
        return datetime.datetime(
            *args, microsecond=dt.microsecond, tzinfo=self, fold=fold
        )

    def utcoffset(self, dt):
        return DSTOFFSET if self._isdst(dt) else STDOFFSET

    def _utcoffset(self, dt):
        return DSTOFFSET if self._isdst(dt) else STDOFFSET

    def dst(self, dt):
        return DSTDIFF if self._isdst(dt) else ZERO

    def tzname(self, dt):
        return time.tzname[self._isdst(dt)]

    def _isdst(self, dt):
        local_time = (
            dt.year,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second,
            dt.weekday(),
            0,
            0,
        )
        stamp = time.mktime(local_time)
        local_time = time.localtime(stamp)
        return local_time.tm_isdst > 0

    def __repr__(self) -> str:
        return "Local_TZ"


local_tzinfo = LocalTimezone()


_ENT_TIME = "2199-12-31 23:59:59"
_ENT_DATETIME = datetime.datetime(2199, 12, 31, 23, 59, 59, 0, tzinfo=local_tzinfo)
_ENT_TIMESTAMP = datetime.datetime(
    2199, 12, 31, 23, 59, 59, 0, tzinfo=local_tzinfo
).timestamp()


@singledispatch
def to_timestring(date_time: Any, fmt: str = "%Y-%m-%d %H:%M:%S.%f") -> str:
    """
    将事件转换为格式化的日期字符串
    :param date_time:
    :return: time string
    """
    raise TypeError(f"Unsupported type: {type(date_time)}")


@to_timestring.register(float)
@to_timestring.register(int)
def _(date_time: Union[float, int], fmt: str = "%Y-%m-%d %H:%M:%S.%f") -> str:
    """处理timestamp类型"""
    if date_time == float("inf"):
        return _ENT_TIME

    date_time = datetime.datetime.fromtimestamp(date_time).astimezone(local_tzinfo)
    return date_time.strftime(fmt)


@to_timestring.register(datetime.time)
def _(date_time: datetime.time, fmt: str = "%Y-%m-%d %H:%M:%S.%f") -> str:
    """处理time类型"""
    return date_time.strftime("%H:%M:%S")


@to_timestring.register(datetime.date)
def _(date_time: datetime.date, fmt: str = "%Y-%m-%d %H:%M:%S.%f") -> str:
    """处理date类型"""
    return date_time.strftime("%Y-%m-%d")


@to_timestring.register(datetime.datetime)
def _(date_time: datetime.datetime, fmt: str = "%Y-%m-%d %H:%M:%S.%f") -> str:
    """处理datetime"""

    date_time = date_time.astimezone(local_tzinfo)

    return date_time.strftime(fmt)


@to_timestring.register(time.struct_time)
def _(date_time: time.struct_time, fmt: str = "%Y-%m-%d %H:%M:%S.%f") -> str:
    """处理struct_time类型"""
    date_time = datetime.datetime(*date_time[:6]).astimezone(local_tzinfo)
    return date_time.strftime(fmt)


@to_timestring.register(str)
def _(date_time: str, fmt: str = "%Y-%m-%d %H:%M:%S.%f") -> str:
    """处理str类型"""
    return parser.parse(date_time).strftime(fmt)


@to_timestring.register(type(None))
def _(date_time, fmt: str = "%Y-%m-%d %H:%M:%S.%f") -> str:
    return ""


@singledispatch
def to_datetime(date_time: Any, tz=local_tzinfo) -> datetime.datetime:
    """
    将date_time转换为datetime对象
    :param date_time:
    :param fmt:
    :return:
    """
    raise TypeError(f"Unsupported type: {type(date_time)}")


@to_datetime.register(str)
def _(date_time: str, tz=local_tzinfo) -> datetime.datetime:
    """处理str类型"""

    return parser.parse(date_time).astimezone(tz) if tz else parser.parse(date_time)


@to_datetime.register(float)
@to_datetime.register(int)
def _(date_time: Union[float, int], tz=local_tzinfo) -> datetime.datetime:
    """处理int类型"""
    if date_time == float("inf"):
        return _ENT_DATETIME

    return (
        datetime.datetime.fromtimestamp(date_time).astimezone(tz)
        if tz
        else datetime.datetime.fromtimestamp(date_time)
    )


@to_datetime.register(time.struct_time)
def _(date_time: time.struct_time, tz=local_tzinfo) -> datetime.datetime:
    """处理struct_time类型"""
    return (
        datetime.datetime(*date_time[:6]).astimezone(tz)
        if tz
        else datetime.datetime(*date_time[:6])
    )


@to_datetime.register(datetime.date)
def _(date_time: datetime.date, tz=local_tzinfo) -> datetime.datetime:
    """处理date类型"""
    return (
        datetime.datetime(
            date_time.year,
            date_time.month,
            date_time.day,
        ).astimezone(tz)
        if tz
        else datetime.datetime(
            date_time.year,
            date_time.month,
            date_time.day,
        )
    )


@to_datetime.register(datetime.datetime)
def _(date_time: datetime.datetime, tz=local_tzinfo) -> datetime.datetime:
    if date_time.tzinfo is None:
        date_time.astimezone(datetime.timezone.utc)
    return date_time.astimezone(local_tzinfo) if tz else date_time


@singledispatch
def to_timestamp(date_time: Any) -> float:
    """
    将date_time转换为timestamp
    :param date_time:
    :param fmt:
    :return: timestamp
    """
    raise TypeError(f"Unsupported type: {type(date_time)}")


@to_timestamp.register(datetime.datetime)
def _(date_time: Any) -> float:
    """处理datetime类型"""
    return date_time.timestamp()


@to_timestamp.register(time.struct_time)
def _(date_time: time.struct_time) -> float:
    """处理struct_time类型"""
    return time.mktime(date_time)


@to_timestamp.register(datetime.date)
def _(date_time: datetime.date) -> float:
    """处理date类型"""
    return time.mktime(date_time.timetuple())


@to_timestamp.register(str)
def _(date_time: str) -> float:
    """处理str类型"""
    pasered_dt = parser.parse(date_time)
    pasered_dt.astimezone(local_tzinfo)
    return pasered_dt.timestamp()


@to_timestamp.register(float)
@to_timestamp.register(int)
def _(date_time: Union[float, int], fmt: str = "") -> float:
    """处理float类型"""
    return _ENT_TIMESTAMP if date_time == float("inf") else date_time


@lru_cache(100)
def to_enum(obj: Any, enum_cls, default: Optional[Enum] = None) -> Enum:
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
        elif (
            isinstance(obj, str)
            and obj.replace(f"{enum_cls.__name__}.", "") in enum_cls.__members__
        ):
            return enum_cls[obj.replace(f"{enum_cls.__name__}.", "")]
        else:
            return enum_cls(obj)
    except ValueError as err:
        if default:
            return default
        else:
            raise ValueError(f"{obj} is not in {enum_cls}.") from err


@singledispatch
def _type_jsonencoder(obj: Any) -> str:
    """
    将obj转换为json字符串
    :param obj:
    :return:
    """
    try:
        return str(obj)
    except TypeError as err:
        raise TypeError(f"Unsupported type: {type(obj)}") from err


_type_jsonencoder.register(Enum, lambda obj: obj.name)
_type_jsonencoder.register(datetime.datetime, to_timestring)
_type_jsonencoder.register(datetime.date, lambda obj: to_timestring(obj, "%Y-%m-%d"))
_type_jsonencoder.register(datetime.time, lambda obj: obj.strftime("%H:%M:%S"))
_type_jsonencoder.register(datetime.timedelta, lambda obj: obj.total_seconds())
_type_jsonencoder.register(time.struct_time, to_timestring)


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


def to_json(obj: Any, indent: int = 4, ensure_ascii=True, **kwargs) -> str:
    """转化为json格式"""
    return json.dumps(
        obj,
        cls=vxJSONEncoder,
        ensure_ascii=ensure_ascii,
        indent=indent,
        **kwargs,
    )


@lru_cache(100)
def combine_datetime(date_: Any, time_: str = "00:00:00") -> float:
    """组合日期和时间"""
    date_ = to_timestring(date_, "%Y-%m-%d")
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

    def byte2int(char_, index=0):
        """Get the ASCII int value of a character in a string.
        :param s: a string
        :param index: the position of desired character
        :return: ASCII int value
        """
        return ord(char_[index]) if six.PY2 else char_[index]


class Serializer:
    _potocols = {}

    def __init__(self, name):
        pass

    def dumps(self, pyobj):
        pass
