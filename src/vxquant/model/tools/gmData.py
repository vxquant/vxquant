""" 掘金量化数据转换至vxFinDataModel数据的转换器 """


from vxutils import combine_datetime, to_timestring, vxtime, vxDataConvertor, to_text

from vxquant.model.exchange import (
    vxCashPosition,
    vxTick,
    vxBar,
    vxPosition,
    vxOrder,
    vxTrade,
    vxAccountInfo,
)
from vxquant.model.preset import vxMarketPreset

__all__ = [
    "gmTickConvter",
    "gmBarConvter",
    "gmAccountinfoConvter",
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
    "updated_dt": "created_at",
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

gmTickConvter.set_defaults("status", "NORMAL")
gmTickConvter.set_defaults("interest", 0)
gmTickConvter.set_defaults("yclose", 0)

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
    "marketvalue": "market_value",
    "created_dt": "created_at",
    "update_dt": "updated_at",
}

gmAccountinfoConvter = vxDataConvertor(vxAccountInfo, PORTOFOLIO_VALUE_TRANS)

gmAccountinfoConvter.add_convertors("balance", lambda x: x.order_frozen + x.available)
gmAccountinfoConvter.set_defaults("currency", "CNY")


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
    "allow_t0", lambda x: vxMarketPreset(x["symbol"]).allow_t0
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
gmCashPositionConvter.set_defaults("allow_t0", "True")
# * #####################################################################
# * gmOrder的转化器
# * #####################################################################
ORDER_TRANS = {
    "exchange_order_id": "cl_ord_id",
    "order_id": "cl_ord_id",
    "order_direction": "side",
    "order_offset": "position_effect",
    "reject_code": "ord_rej_reason",
    # "rej_reason_detail": "ord_rej_reason_detail",
    "created_dt": "created_at",
    "updated_dt": "created_at",
}


def _make_due_dt(obj):
    created_date = to_timestring(obj["created_at"] or vxtime.now(), "%Y-%m-%d")
    return combine_datetime(created_date, "15:00:00")


gmOrderConvter = vxDataConvertor(vxOrder, ORDER_TRANS)
gmOrderConvter.add_convertors("due_dt", _make_due_dt)
gmOrderConvter.add_convertors(
    "rej_reason_detail", lambda x: to_text(x["ord_rej_reason_detail"])
)


# * #####################################################################
# * gmTrade的转化器
# * #####################################################################

TRADE_TRANS = {
    "trade_id": "exec_id",
    "exchange_order_id": "cl_ord_id",
    "order_id": "cl_ord_id",
    "reject_code": "ord_rej_reason",
    # "reject_reason": "ord_rej_reason_detail",
    "created_dt": "created_at",
    "updated_dt": "created_at",
    "status": "exec_type",
    "order_direction": "side",
    "order_offset": "position_effect",
}

gmTradeConvter = vxDataConvertor(vxTrade, TRADE_TRANS)
gmTradeConvter.add_convertors(
    "reject_reason", lambda x: to_text(x["ord_rej_reason_detail"])
)
