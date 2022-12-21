# encoding=utf8
""" 通达信数据转换 """
import datetime
from enum import Enum
from pytdx.hq import TDXParams
from vxutils.dataclass import vxDataConvertor

from vxquant.model.exchange import vxTick, vxBar


class TdxExchange(Enum):
    """通达信交易所代码"""

    SHSE = TDXParams.MARKET_SH
    SZSE = TDXParams.MARKET_SZ


# * #####################################################################
# * tdxTick的转换器
# * #####################################################################
TICK_TRANS = {
    "volume": "vol",
}


def tdx_to_timestamp(tdx_timestamp, trade_day=None):
    """通达信时间戳转换为时间戳"""
    if trade_day is None:
        trade_day = datetime.datetime.now()

    tdx_timestamp = f"{tdx_timestamp:0>8}"
    hour = int(tdx_timestamp[:2])
    if hour < 0 or hour > 23:
        tdx_timestamp = f"0{tdx_timestamp}"
        hour = int(tdx_timestamp[:2])

    minute = int(tdx_timestamp[2:4])
    percent = float(f"0.{tdx_timestamp[2:]}")
    if minute < 60:
        second = int(percent * 60)
        microsecond = int((percent * 60 - second) * 1000)
    else:
        minute = int(percent * 60)
        second = int((percent * 60 - minute) * 60)
        microsecond = int(((percent * 60 - minute) * 60 - second) * 1000)
    return datetime.datetime(
        trade_day.year,
        trade_day.month,
        trade_day.day,
        hour,
        minute,
        second,
        microsecond,
    ).timestamp()


# 非可转债转化
tdxStockTickConvter = vxDataConvertor(vxTick, TICK_TRANS)
tdxStockTickConvter.add_convertors(
    "symbol", lambda x: f"{TdxExchange(x['market']).name}.{x['code']}"
)
tdxStockTickConvter.add_convertors("yclose", lambda x: round(x["last_close"], 4))
tdxStockTickConvter.add_convertors(
    "lasttrade", lambda x: round(x["price"], 4) or round(x["last_close"], 4)
)


def _quote_convter(cnt, volunit, price_unit=None):
    if price_unit is None:
        price_unit = volunit
    return {
        f"bid{cnt}_v": lambda x: x[f"bid_vol{cnt}"] * volunit,
        f"bid{cnt}_p": lambda x: x[f"bid{cnt}"] / 100 * price_unit,
        f"ask{cnt}_v": lambda x: x[f"ask_vol{cnt}"] * volunit,
        f"ask{cnt}_p": lambda x: x[f"ask{cnt}"] / 100 * price_unit,
    }


for i in range(1, 6):
    for k, v in _quote_convter(i, 100).items():
        tdxStockTickConvter.add_convertors(k, v)

tdxStockTickConvter.add_convertors("volume", lambda x: x["vol"] * 100)
tdxStockTickConvter.add_convertors(
    "created_dt", lambda x: tdx_to_timestamp(x["reversed_bytes0"])
)


# 可转债转化
tdxConBondTickConvter = vxDataConvertor(vxTick, TICK_TRANS)

tdxConBondTickConvter.add_convertors(
    "symbol", lambda x: f"{TdxExchange(x['market']).name}.{x['code']}"
)

for i in range(1, 6):
    for k, v in _quote_convter(i, 1).items():
        tdxConBondTickConvter.add_convertors(k, v)


tdxConBondTickConvter.add_convertors(
    "yclose", lambda x: round(x["last_close"] / 100, 4)
)
tdxConBondTickConvter.add_convertors("open", lambda x: round(x["open"] / 100, 4))
tdxConBondTickConvter.add_convertors("high", lambda x: round(x["high"] / 100, 4))
tdxConBondTickConvter.add_convertors("low", lambda x: round(x["low"] / 100, 4))
tdxConBondTickConvter.add_convertors(
    "lasttrade", lambda x: round(x["price"] / 100, 4) or round(x["last_close"] / 100, 4)
)

tdxConBondTickConvter.add_convertors("volume", lambda x: x["vol"] * 100)
tdxConBondTickConvter.add_convertors(
    "created_dt", lambda x: tdx_to_timestamp(x["reversed_bytes0"])
)

# ETFLOF
tdxETFLOFTickConvter = vxDataConvertor(vxTick, TICK_TRANS)

tdxETFLOFTickConvter.add_convertors(
    "symbol", lambda x: f"{TdxExchange(x['market']).name}.{x['code']}"
)

for i in range(1, 6):
    for k, v in _quote_convter(i, 100, 10).items():
        tdxETFLOFTickConvter.add_convertors(k, v)


tdxETFLOFTickConvter.add_convertors("yclose", lambda x: round(x["last_close"] / 10, 4))
tdxETFLOFTickConvter.add_convertors("open", lambda x: round(x["open"] / 10, 4))
tdxETFLOFTickConvter.add_convertors("high", lambda x: round(x["high"] / 10, 4))
tdxETFLOFTickConvter.add_convertors("low", lambda x: round(x["low"] / 10, 4))
tdxETFLOFTickConvter.add_convertors(
    "lasttrade", lambda x: round(x["price"] / 10, 4) or round(x["last_close"] / 10, 4)
)
tdxETFLOFTickConvter.add_convertors("volume", lambda x: x["vol"] * 100)
tdxETFLOFTickConvter.add_convertors(
    "created_dt", lambda x: tdx_to_timestamp(x["reversed_bytes0"])
)


# * #####################################################################
# * tdxBar的转换器
# * #####################################################################
BAR_TRANS = {
    "close": "price",
    "volume": "vol",
    "created_dt": "created_at",
}


# TDXParams.KLINE_TYPE_1MIN
# TDXParams.KLINE_TYPE_DAILY

tdxBarConvter = vxDataConvertor(vxBar, BAR_TRANS)
# tdxBarConvter.add_convertors('created_at', lambda x: time.strptime(x['datetime'],'%Y-%m-%d %H:%M:%S')
# tdxBarConvter.add_convertors('created_at', conveter_func)
