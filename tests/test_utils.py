"""测试时间机器功能"""

import json
import time
import datetime
import pytz
from vxquant.utils import vxtime, logger
from vxquant.utils.convertors import (
    to_timestamp,
    to_timestring,
    to_datetime,
    to_json,
    to_enum,
)


_1DAY_INTERVAL = 60 * 60 * 24
_1WEEK_INTERVAL = 60 * 60 * 24 * 7


def test_vxtime():
    """vxtime测试用例"""
    now = vxtime.now()
    assert 0.1 >= time.time() - now >= 0

    fortime = to_timestamp("2020-01-01 00:00:00")
    vxtime.backtest(start_time=fortime, end_time=fortime + _1DAY_INTERVAL)
    assert vxtime.status == "BACKTEST"
    assert fortime == vxtime.now()
    vxtime.sleep(10)
    assert fortime + 10 == vxtime.now()

    start_time = vxtime.now()
    for _ in range(10):
        logger.info(to_timestring(vxtime.now()))
        vxtime.sleep(10)
        start_time += 10
        assert start_time == vxtime.now()
    try:
        vxtime.sleep(_1DAY_INTERVAL)
        raise AssertionError("no raise stopiteration exception.")
    except Exception as e:
        assert isinstance(e, StopIteration)


def test_convertors():
    """测试转换器"""
    now_datetime = datetime.datetime.now(tz=datetime.timezone.utc)
    now_datetime = now_datetime.replace(microsecond=0)

    # 测试timezone 转换
    now_datetime2 = to_datetime(now_datetime)
    assert now_datetime.tzinfo != now_datetime2.tzinfo
    assert now_datetime == now_datetime2

    now_timestamp = to_timestamp(now_datetime)
    now_timestring = to_timestring(now_datetime)
    assert to_datetime(now_timestamp) == to_datetime(now_timestring)
    assert to_timestamp(now_timestring) == now_timestamp
    assert to_timestring(now_timestamp) == now_timestring
    assert to_datetime(now_timestring) == now_datetime
    assert to_timestamp(now_datetime) == to_timestamp(now_datetime2)
    assert to_timestring(now_datetime) == to_timestring(now_datetime2)

    now_datetime = datetime.datetime.now()
    now_datetime2 = to_datetime(now_datetime)
    assert now_datetime.tzinfo != now_datetime2.tzinfo
    assert to_timestamp(now_datetime) == to_timestamp(now_datetime2)
    assert to_timestring(now_datetime) == to_timestring(now_datetime2)

    now_json = to_json(now_datetime)
    assert json.loads(now_json) == to_timestring(now_datetime)


if __name__ == "__main__":
    test_convertors()
    test_vxtime()
