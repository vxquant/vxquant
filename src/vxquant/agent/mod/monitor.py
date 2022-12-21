# 市值网格法

import json

# from gm import api as gm_api
from vxsched import vxengine
from vxsched.triggers import vxIntervalTrigger
from vxquant.model.exchange import vxOrder
from vxquant.model.preset import vxMarketPreset
from vxquant.model.contants import OrderStatus
from vxutils import logger, vxtime

MIN_ORDER_AMOUNT = 50000
MAX_ORDER_VOLUME = 99000


@vxengine.event_handler("__init__")
def init_shell(gmcontext, _):
    """初始化"""

    gmcontext.params["target_values"] = gmcontext.params.get(
        "target_values", {"CNY": 0}
    )
    gmcontext.pending_orders = {}
    gmcontext.params["weights"] = gmcontext.params.get("weights", {"CNY": 1})
    vxengine.submit_event("update_target_values", gmcontext.params["weights"])


@vxengine.event_handler("on_tick")
def remove_expired_order(gmcontext, event=None):
    pending_orders = {}
    now = vxtime.now()
    for order in gmcontext.pending_orders.values():
        order = gmcontext.broker_orders[order.exchange_order_id]
        if order.created_dt + 60 > now:
            pending_orders[order.symbol] = order
        elif order.status in [
            OrderStatus.New,
            OrderStatus.PartiallyFilled,
            OrderStatus.PendingNew,
        ]:
            gmcontext.tdapi.order_cancel(order)
            logger.info(f"委托单超时: {order.order_id} 撤单")
    gmcontext.pending_orders = pending_orders


def grid_sell(gmcontext, position, diff_marketvalue):
    if position.available <= 0:
        return
    symbol = position.symbol
    lasttrade = position.lasttrade
    preset_instrument = vxMarketPreset(symbol)

    diff_volume = min(
        diff_marketvalue
        / lasttrade
        // preset_instrument.volume_unit
        * preset_instrument.volume_unit,
        position.available,
    )
    if diff_volume < 0:
        return

    gap_volume = (
        MIN_ORDER_AMOUNT
        / lasttrade
        // preset_instrument.volume_unit
        * preset_instrument.volume_unit
    )
    if diff_volume > 2 * gap_volume:
        diff_volume = gap_volume
    diff_volume = min(diff_volume, 99000)
    sell_order = gmcontext.tdapi.order_volume(
        symbol=symbol,
        volume=-diff_volume,
        price=position.lasttrade - preset_instrument.price_tick,
    )
    gmcontext.pending_orders[symbol] = sell_order
    logger.info(
        f"提交卖出订单: {sell_order.symbol} -volume({sell_order.volume:,.2f})"
        f" -marketvalue({sell_order.volume *position.lasttrade:,.2f})"
    )


def grid_buy(gmcontext, account, symbol, diff_marketvalue, lasttrade):
    diff_marketvalue = min(diff_marketvalue, account.available)
    preset_instrument = vxMarketPreset(symbol)

    if diff_marketvalue > 2 * MIN_ORDER_AMOUNT:
        diff_marketvalue = MIN_ORDER_AMOUNT

    diff_volume = (
        diff_marketvalue
        / lasttrade
        // preset_instrument.volume_unit
        * preset_instrument.volume_unit
    )

    if diff_volume > 0:
        diff_volume = min(diff_volume, 99000)
        buy_order = gmcontext.tdapi.order_volume(
            symbol=symbol,
            volume=diff_volume,
            price=lasttrade + preset_instrument.price_tick,
        )
        gmcontext.pending_orders[symbol] = buy_order
        account.frozen = account.frozen + round((diff_volume * lasttrade) * 1.003, 2)
        logger.info(
            f"提交买入订单: {buy_order.symbol} +volume({buy_order.volume:,.2f})"
            f" +marketvalue({buy_order.volume *lasttrade:,.2f})"
        )


@vxengine.event_handler("monitor_position", 0)
def strategy_monitor_position(gmcontext, _):
    positions = gmcontext.tdapi.get_positions()
    account = gmcontext.tdapi.get_account()
    positions.pop("CNY")
    # now = vxtime.now()
    logger.info(
        "当前净值:"
        f" {account.nav:,.2f}元，持仓{len(positions)}只股票.持仓比例:{account.marketvalue/account.nav*100:,.2f}%"
    )

    remove_expired_order(gmcontext)
    cnt = 0

    for symbol, position in positions.items():
        cnt += 1
        target_value = gmcontext.params["target_values"].get(symbol, 0)
        if target_value == 0:
            logger.info(
                f"检查第({cnt})只股票: {symbol} 当前市值: {position.marketvalue:,.2f} 标准值:"
                " 0.00元，清仓。"
            )
        else:
            logger.info(
                f"检查第({cnt})只股票: {symbol} 当前市值: {position.marketvalue:,.2f} 标准值:"
                f" {target_value:,.2f}, 偏离度:"
                f" {(position.marketvalue/target_value*100-100):,.2f}%"
            )

        if symbol in gmcontext.pending_orders:
            continue

        if position.marketvalue > target_value * 1.05 and position.available > 0:
            grid_sell(gmcontext, position, position.marketvalue - target_value)

        elif target_value * 0.95 > position.marketvalue and account.available > 50000:
            grid_buy(
                gmcontext,
                account,
                symbol,
                target_value - position.marketvalue,
                position.lasttrade,
            )

    new_symbols = set(gmcontext.params["target_values"].keys()) - set(positions.keys())
    new_symbols = [symbol for symbol in new_symbols if symbol != "CNY"]

    if not new_symbols:
        return

    vxticks = gmcontext.tdapi.current(*new_symbols)

    for symbol in new_symbols:
        if symbol in gmcontext.pending_orders:
            continue

        if symbol == "CNY":
            continue

        target_value = gmcontext.params["target_values"][symbol]
        if account.available <= 50000:
            break

        diff_marketvalue = min(target_value, account.available / 1.003)
        lasttrade = vxticks[symbol].lasttrade
        grid_buy(gmcontext, account, symbol, diff_marketvalue, lasttrade)


@vxengine.event_handler("update_target_values")
def update_target_values(gmcontext, event):
    """更新目标持仓数据"""
    weights = event.data
    account = gmcontext.tdapi.get_account()
    total_weight = sum(weights.values())
    if total_weight == 0:
        weights = {"CNY": 1}
        total_weight = 1

    gmcontext.params["target_values"] = {}
    gmcontext.pending_orders = {}
    for symbol, weight in weights.items():
        if weight <= 0:
            continue

        gmcontext.params["target_values"][symbol] = round(
            account.nav * weight / total_weight, 2
        )
        logger.info(
            f"{symbol} 目标持仓市值更新为:"
            f" {gmcontext.params['target_values'][symbol]:,.2f},持仓比例:"
            f" {weight/total_weight*100:,.2f}%"
        )


@vxengine.event_handler("before_trade")
def update_marketvalue_benchmarks(gmcontext, _):
    try:
        weights_file = "etc/weights.json"
        with open(weights_file, "r") as f:
            weights = json.load(f)
        logger.info(f"读取持仓文件weights.json 最新目标持仓仓位: {weights}")
        # gmcontext.params.load_weight = gmcontext.mode == gm_api.MODE_LIVE
    except OSError:
        weights = {"CNY": 1}
        with open(weights_file, "w") as f:
            json.dump(weights, f, indent=4)
        logger.info(f"持仓文件weights.json不存在，默认清仓所有股票: {weights}")

    account = gmcontext.tdapi.get_account()
    total_weight = sum(weights.values())
    gmcontext.params["target_values"] = {}
    gmcontext.pending_orders = {}
    for symbol, weight in weights.items():
        if weight <= 0:
            continue

        gmcontext.params["target_values"][symbol] = round(
            account.nav * weight / total_weight, 2
        )
        logger.info(
            f"{symbol} 目标持仓市值更新为:"
            f" {gmcontext.params['target_values'][symbol]:,.2f},持仓比例:"
            f" {weight/total_weight*100:,.2f}%"
        )
    if vxtime.now() < vxtime.today("11:30:00"):
        vxengine.submit_event(
            "monitor_position",
            "",
            vxIntervalTrigger(
                10, start_dt=vxtime.today("10:00:00"), end_dt=vxtime.today("11:30:00")
            ),
        )
    if vxtime.now() < vxtime.today("15:00:00"):
        vxengine.submit_event(
            "monitor_position",
            "",
            vxIntervalTrigger(
                10, start_dt=vxtime.today("13:00:00"), end_dt=vxtime.today("15:00:00")
            ),
        )


@vxengine.event_handler("on_broker_order_status")
def strategy_on_broker_order_status(gmcontext, event):
    vxorder = event.data
    if isinstance(vxorder, dict):
        vxorder = vxOrder(vxorder)

    if vxorder.status in [
        OrderStatus.Expired,
        OrderStatus.Rejected,
        OrderStatus.Suspended,
        OrderStatus.Canceled,
    ]:
        gmcontext.pending_orders.pop(vxorder.symbol, None)
