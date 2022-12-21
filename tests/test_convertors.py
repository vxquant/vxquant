"""测试各种转换器"""

import time
from enum import Enum
import json
from vxutils.convertors import (
    to_binary,
    to_datetime,
    to_timestring,
    to_timestamp,
    to_enum,
    to_json,
    to_text,
)


def test_datetime():
    """测试时间相关函数"""
    timestamp = int(time.time())
    t_struct = time.localtime(timestamp)
    timestring = to_timestring(timestamp)
    _datetime = to_datetime(timestamp)

    assert _datetime == to_datetime(timestring)
    assert _datetime == to_datetime(t_struct)
    assert _datetime == to_datetime(_datetime)

    assert timestring == to_timestring(_datetime)
    assert timestring == to_timestring(t_struct)
    assert timestring == to_timestring(timestring)

    assert timestamp == to_timestamp(_datetime)
    assert timestamp == to_timestamp(t_struct)
    assert timestamp == to_timestamp(timestamp)


def test_enum():
    """测试to_enum"""

    class tenum(Enum):
        """测试枚举类"""

        test1 = 1
        test2 = 2
        test3 = 3

    a = tenum(1)
    assert a == to_enum(1, tenum)
    assert a == to_enum("test1", tenum)
    assert a == to_enum(tenum["test1"], tenum)

    try:
        to_enum(99, tenum)
    except ValueError as e:
        assert isinstance(e, ValueError)

    assert a == to_enum(99, tenum, tenum(1))


def test_json():
    """测试json格式转换"""

    timestring = "2022-10-11 10:30:30.000000"

    assert timestring == json.loads(to_json(to_datetime(timestring)))

    timestring = "2022-10-11 00:00:00.000000"
    assert timestring == json.loads(to_json(to_datetime(timestring)))


def test_text_convert_to_binary():
    """测试text和binary转换"""
    txt = "text"
    btxt = b"text"

    assert txt == to_text(txt)
    assert txt == to_text(btxt)
    assert btxt == to_binary(txt)
    assert btxt == to_binary(btxt)
