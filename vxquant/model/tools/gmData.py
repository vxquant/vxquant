""" 掘金量化数据转换至vxFinDataModel数据的转换器 """

import datetime
from vxquant.utils.convertors import to_timestamp, combine_datetime, to_timestring
from vxquant.utils.dataclass import vxDataConvertor
from vxquant.utils import vxtime
from vxquant.model.broker import (
    vxCashPosition,
    vxTick,
    vxBar,
    vxPosition,
    vxOrder,
    vxTrade,
    vxAccountInfo,
)
from vxquant.model.preset import vxMarketPreset

from vxquant.model.contants import (
    PositionSide,
    OrderDirection,
    OrderRejectReason,
    OrderOffset,
    OrderStatus,
    OrderType,
    SecType,
    TradeStatus,
)


__all__ = [
    "gmTickConvter",
    "gmBarConvter",
    "gmPortfolioValueConvter",
    "update_gmcredit_cash",
    "gmCashPositionConvter",
    "gmPositionConvter",
    "gmOrderConvter",
    "gmTradeConvter",
]

# * #####################################################################
# * gmTick的转换器
# * #####################################################################
TICK_TRANS = {
    "lasttrade": "price",
    "volume": "cum_volume",
    "amount": "cum_amount",
    "created_dt": "created_at",
}


gmTickConvter = vxDataConvertor(vxTick, TICK_TRANS)


def _quote_convter(cnt):
    return {
        f"bid{cnt}_v": lambda x: x["quotes"][cnt - 1]["bid_v"],
        f"bid{cnt}_p": lambda x: x["quotes"][cnt - 1]["bid_p"],
        f"ask{cnt}_v": lambda x: x["quotes"][cnt - 1]["ask_v"],
        f"ask{cnt}_p": lambda x: x["quotes"][cnt - 1]["ask_p"],
    }


for i in range(1, 6):
    quote_convters = _quote_convter(i)
    for k, v in quote_convters.items():
        gmTickConvter.add_convertors(k, v)


# * gmTickConvter.add_convertors(
# *     "created_dt",
# *     lambda x: x.created_at.timestamp()
# *     if isinstance(x.created_at, datetime.datetime)
# *     else x.created_at.seconds,
# * )


# * #####################################################################
# * gmBar的转换器
# * #####################################################################
BAR_TRANS = {"yclose": "pre_close", "created_dt": "eob"}
gmBarConvter = vxDataConvertor(vxBar, BAR_TRANS)

# * #####################################################################
# * vxAccountInfo 的转换器
# * #####################################################################


PORTOFOLIO_VALUE_TRANS = {
    "asset": "nav",
    "frozen": "order_frozen",
    "float_profit": "fpnl",
    "marketvalue_long": "market_value",
}

gmPortfolioValueConvter = vxDataConvertor(vxAccountInfo, PORTOFOLIO_VALUE_TRANS)

gmPortfolioValueConvter.add_convertors(
    "balance", lambda x: x.order_frozen + x.available
)
gmPortfolioValueConvter.set_defaults("currency", "CNY")


def update_gmcredit_cash(vxdatadict, gmCreditCash):
    """更新负债信息"""
    vxdatadict["marketvalue_short"] = gmCreditCash["dealfmktavl"]
    vxdatadict["debt_long"] = gmCreditCash["ftotaldebts"]
    vxdatadict["debt_short"] = gmCreditCash["dtotaldebts"]
    vxdatadict["margin_available"] = gmCreditCash["marginavl"]
    vxdatadict["balance"] = (
        vxdatadict["asset"] - gmCreditCash["ftotaldebts"] - gmCreditCash["dtotaldebts"]
    )
    return vxdatadict


# * #####################################################################
# * gmPosition的转换器
# * #####################################################################
POSITION_TRANS = {
    "lasttrade": "price",
    "marketvalue": "market_value",
    "cost": "amount",
    "available": "available_now",
    "frozen": "order_frozen",
    "float_profit": "fpnl",
    "created_dt": "created_at",
    "updated_dt": "updated_at",
}

gmPositionConvter = vxDataConvertor(vxPosition, POSITION_TRANS)
gmPositionConvter.add_convertors(
    "security_type", lambda x: vxMarketPreset(x["symbol"]).security_type
)
gmPositionConvter.add_convertors(
    "volume_his", lambda x: x["volume"] - x["volume_today"]
)


# * #####################################################################
# * gmCashPosition的转换器
# * #####################################################################

CASH_POSITION_TRANS = {
    "frozen": "order_frozen",
    "created_dt": "created_at",
    "updated_dt": "updated_at",
}
gmCashPositionConvter = vxDataConvertor(vxCashPosition, CASH_POSITION_TRANS)

gmCashPositionConvter.add_convertors(
    "volume_his", lambda x: x["order_frozen"] + x["available"]
)

# * #####################################################################
# * gmOrder的转化器
# * #####################################################################
ORDER_TRANS = {
    "exchange_order_id": "cl_ord_id",
    "order_id": "cl_ord_id",
    "rej_reason_detail": "ord_rej_reason_detail",
    "created_dt": "created_at",
    "updated_dt": "updated_at",
}


def _make_due_dt(obj):
    created_date = to_timestring(obj["created_at"], "%Y-%m-%d")
    return combine_datetime(created_date, "15:00:00")


gmOrderConvter = vxDataConvertor(vxOrder, ORDER_TRANS)
gmOrderConvter.add_convertors("due_dt", _make_due_dt)

# * #####################################################################
# * gmTrade的转化器
# * #####################################################################

TRADE_TRANS = {
    "trade_id": "exec_id",
    "exchange_order_id": "cl_ord_id",
    "order_id": "cl_ord_id",
    "reject_reason": "ord_rej_reason_detail",
    "created_dt": "created_at",
}

gmTradeConvter = vxDataConvertor(vxTrade, TRADE_TRANS)
