"""gmagent"""

import os
import pathlib

try:
    from gm import api as gm_api
    from vxquant.tdapi.gm import gmTdAPI
except ImportError:
    gm_api = None
    gmTdAPI = None

from vxutils import logger, vxtime, to_timestamp, to_enum, to_timestring, vxWrapper

from vxsched.triggers import vxDailyTrigger
from vxsched import vxengine, vxContext
from vxquant.model.exchange import OrderStatus, TradeStatus
from vxquant.model.contants import AccountType
from vxquant.model.preset import vxMarketPreset
from vxquant.model.tools.gmData import gmOrderConvter, gmTradeConvter


__all__ = ["run_gmagent", "init", "on_tick", "on_order_status", "on_execution_report"]

_default_gmagent_config = {
    "settings": {
        "account_type": "NORMAL",
        "gm_strategyid": "",
        "gm_token": "",
        "tick_symbols": [
            "SHSE.000001",
            "SHSE.000688",
            "SHSE.511880",
            "SHSE.510300",
            "SHSE.511990",
            "SHSE.511660",
            "SHSE.204001",
            "SZSE.399001",
            "SZSE.399673",
            "SZSE.159001",
            "SZSE.159919",
            "SZSE.159915",
            "SZSE.159937",
            "SZSE.131810",
        ],
        "events": {
            "before_trade": "09:15:00",
            "on_trade": "09:30:00",
            "noon_break_start": "11:30:00",
            "noon_break_end": "13:00:00",
            "before_close": "14:45:00",
            "on_close": "14:55:00",
            "after_close": "15:30:00",
        },
        "publisher": {},
        "subscriber": {},
    },
    "params": {},
}


def init(gmcontext):
    """
    掘金量化策略中必须有init方法,且策略会首先运行init定义的内容
    """

    # 设置 时间函数
    vxtime.set_timefunc(lambda: to_timestamp(gmcontext.now))
    logger.info("=" * 80)
    logger.info(f"{' 初始化开始 ':=^80}")
    logger.info("=" * 80)

    configfile = os.environ.get("GMCONFIGFILE", "gmagent.json")
    vxcontext = vxContext.load_json(configfile, _default_gmagent_config)
    mod_path = os.environ.get("STRATEGYMOD", "mod/")

    # 拷贝context内容只gmcontext中
    for k, v in vxcontext.items():
        setattr(gmcontext, k, v)

    # 设置gm tdapi接口
    account_type = to_enum(
        vxcontext.settings["account_type"], AccountType, AccountType.Normal
    )
    gmcontext.tdapi = gmTdAPI(gmcontext, account_type)

    gmcontext.broker_orders = gmcontext.tdapi.get_orders()
    logger.info(f"当前委托订单: {len(gmcontext.broker_orders)}个.")

    gmcontext.broker_trades = gmcontext.tdapi.get_execution_reports()
    logger.info(f"当前成交回报: {len(gmcontext.broker_trades)}个.")

    account = gmcontext.tdapi.get_account()
    logger.info(
        f"检查下单接口是否正常: 账户({account.account_id}) 类型: {account_type} 净资产:"
        f" {account.nav:,.2f}元."
    )

    if gmcontext.settings.publisher and gmcontext.settings.subscriber:
        gmcontext.publisher = vxWrapper.init_by_config(gmcontext.settings.publisher)
        logger.info(f"设置publisher: {gmcontext.publisher}")
        gmcontext.subscriber = vxWrapper.init_by_config(gmcontext.settings.subscriber)
        logger.info(f"设置subscriber: {gmcontext.subscriber}")
        gmcontext.has_remote_event = True
        logger.info("开启接送和发送远端消息事件模式...")
        gmcontext.last_subscriber_time = 0
    else:
        gmcontext.publisher = None
        gmcontext.subscriber = None
        gmcontext.has_remote_event = False
        logger.info("关闭接受和发送远端消息时间...")

    # 订阅各种接口
    tick_symbols = vxcontext.settings["tick_symbols"]
    gm_api.subscribe(
        tick_symbols,
        "tick",
    )
    logger.info(f"订阅tick data: {tick_symbols}")

    for event_type, run_time in vxcontext.settings["events"].items():
        vxengine.submit_event(
            event=event_type, trigger=vxDailyTrigger(run_time=run_time)
        )
        logger.info(f"订阅事件{event_type} 触发时间: {run_time}")

    gm_api.schedule(quit_simtrade, "1d", "16:30:00")
    logger.info("设置退出时间 16:30:00")

    vxengine.load_modules(mod_path)
    vxengine.initialize(context=gmcontext)

    logger.info("=" * 80)
    logger.info(f"{' 初始化完成 ':=^80}")
    logger.info("=" * 80)

    if vxtime.today("09:15:00") < vxtime.now() < vxtime.today("15:00:00"):
        vxengine.submit_event("before_trade")
        logger.warning("当前为开盘时间，触发一次before_trade。")
        vxengine.trigger_events()


def on_tick(gmcontext, gmtick=None):
    """on tick"""
    if gmcontext.has_remote_event and gmcontext.last_subscriber_time + 1 < vxtime.now():
        list(map(vxengine.submit_event, gmcontext.subscriber()))
        gmcontext.last_subscriber_time = vxtime.now()

    vxengine.trigger_events()


def on_order_status(gmcontext, order):
    """
    委托状态更新事件. 参数order为委托信息
    响应委托状态更新事情，下单后及委托状态更新时被触发
    3.0.113 后增加.
    与on_order_status 具有等同含义, 在二者都被定义时(当前函数返回类型为类，速度更快，推介使用), 只会调用 on_order_status_v2
    """
    logger.debug(f"gmorder: {order}")
    vxorder = gmOrderConvter(order)

    if vxorder.exchange_order_id not in gmcontext.broker_orders:
        gmcontext.broker_orders[vxorder.exchange_order_id] = vxorder
        logger.info(f"[新增] 委托订单{vxorder.exchange_order_id} 更新为: {vxorder}")
        vxengine.submit_event("on_broker_order_status", vxorder)
        vxengine.trigger_events()
        if gmcontext.has_remote_event:
            gmcontext.publisher("on_broker_order_status", vxorder)
        return

    broker_order = gmcontext.broker_orders[vxorder.exchange_order_id]

    if broker_order.status in [
        OrderStatus.Filled,
        OrderStatus.Expired,
        OrderStatus.Rejected,
        OrderStatus.Canceled,
        OrderStatus.Suspended,
    ]:
        logger.warning(
            f"[忽略更新] 委托订单 {vxorder.exchange_order_id} "
            f" 当前状态:{broker_order.status} 须更新状态: {vxorder.status}"
        )
        return

    if broker_order.filled_volume > vxorder.filled_volume:
        logger.warning(
            f"[忽略更新] 委托订单 {vxorder.exchange_order_id} 当前已成交:"
            f" {broker_order.filled_volume} > 更新状态:{vxorder.filled_volume}"
        )
        return

    # 更新委托订单状态
    broker_order.status = vxorder.status
    broker_order.filled_volume = vxorder.filled_volume
    broker_order.filled_amount = vxorder.filled_amount
    broker_order.updated_dt = vxorder.updated_dt
    gmcontext.broker_orders[broker_order.exchange_order_id] = broker_order
    vxengine.submit_event("on_broker_order_status", broker_order)
    logger.info(f"[更新] 委托订单{vxorder.exchange_order_id} 更新为: {broker_order}")
    vxengine.trigger_events()
    if gmcontext.has_remote_event:
        gmcontext.publisher("on_broker_order_status", vxorder)


def on_execution_report(gmcontext, execrpt):
    """
    委托执行回报事件. 参数 execrpt 为执行回报信息
    响应委托被执行事件，委托成交后被触发
    3.0.113 后增加
    已 on_execution_report 具有等同含义, 在二者都被定义时(当前函数返回类型为类，速度更快，推介使用), 只会调用 on_execution_report_v2
    """

    logger.debug(f"gmtrade: {execrpt}")
    vxtrade = gmTradeConvter(execrpt)
    if vxtrade.commission == 0:
        _preset = vxMarketPreset(vxtrade.symbol)
        vxtrade.commission = max(
            (
                vxtrade.price
                * vxtrade.volume
                * (
                    _preset.commission_coeff_peramount
                    if vxtrade.order_direction.name == "Buy"
                    else (
                        _preset.commission_coeff_peramount + _preset.tax_coeff_peramount
                    )
                )
            ),
            5,
        )

    if vxtrade.status != TradeStatus.Trade:
        logger.warning(f"收到非成交的回报信息: {vxtrade}")
        return

    if vxtrade.trade_id in gmcontext.broker_trades:
        logger.warning("收到重复的委托订单信息")
        return

    gmcontext.broker_trades[vxtrade.trade_id] = vxtrade
    if gmcontext.has_remote_event:
        gmcontext.publisher("on_broker_order_status", vxtrade)
    vxengine.submit_event("on_broker_order_status", vxtrade)
    logger.info(f"收到成交回报信息: {vxtrade}")
    vxengine.trigger_events()
    if gmcontext.has_remote_event:
        gmcontext.publisher("on_broker_order_status", vxtrade)


def save_config(gmcontext, configfile):
    config = vxContext(_default_gmagent_config)
    config["settings"].update(gmcontext.settings)
    config["params"].update(gmcontext.params)
    config.save_json(configfile)
    logger.info(f"保存最新的配置文件内容:{configfile}")


def quit_simtrade(gmcontext):
    """退出时调用"""

    configfile = os.environ.get("GMCONFIGFILE", "gmagent.json")
    save_config(gmcontext, configfile)
    logger.warning("=" * 80)
    logger.warning("{' 当天交易结束 ':*^80}")
    logger.warning("=" * 80)

    gm_api.stop()


def on_trade_data_disconnected(gmcontext):
    """当交易网络断开的时候，保存配置文件"""
    configfile = os.environ.get("GMCONFIGFILE", "gmagent.json")
    save_config(gmcontext, configfile)


if __name__ == "__main__":
    gm_strategyid = os.environ.get("gm_strategyid", None)
    gm_token = os.environ.get("gm_token", None)

    assert gm_token is not None
    assert gm_strategyid is not None
    logger.info(f"策略ID: {gm_strategyid} token: {gm_token}")

    try:
        gm_api.run(
            strategy_id=gm_strategyid,
            filename="vxquant.agent.gmagent",
            mode=gm_api.MODE_LIVE,
            token=gm_token,
        )
    finally:
        vxtime.sleep(5)
