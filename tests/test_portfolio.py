"""账户信息测试"""

import uuid

from vxquant.model.broker import vxOrder, vxTrade
from vxquant.model.contants import OrderStatus, TradeStatus, OrderType, OrderDirection
from vxquant.model.portfolio import vxStockAccount


def test_account():
    """测试账户"""

    # 创建账户
    balance = 100_0000
    acc = vxStockAccount(account_id="test", balance=balance)
    cash_position = acc.get_positions()["CNY"]

    # 检查重要字段是否正确
    assert cash_position.marketvalue == balance
    assert acc.account_info.balance == cash_position.marketvalue
    assert cash_position.lasttrade == 1.0
    assert (
        acc.account_info.available == cash_position.available * cash_position.lasttrade
    )
    assert acc.account_info.deposit == 0
    assert acc.account_info.withdraw == 0
    assert acc.account_info.asset == cash_position.marketvalue
    assert acc.account_info.nav == cash_position.marketvalue
    assert acc.account_info.fund_shares == cash_position.marketvalue
    assert acc.account_info.fund_nav == 1.0
    assert acc.account_id == "test"
    assert acc.account_info.fund_nav_yd == 1.0
    assert acc.account_info.asset_yd == cash_position.marketvalue
    assert acc.account_info.nav_yd == cash_position.marketvalue

    positions = acc.get_positions()
    orders = acc.get_orders()
    trades = acc.get_trades()
    assert list(positions.keys()) == ["CNY"]
    assert len(orders) == 0

    assert len(trades) == 0
    # 转入、转出金额是否正确
    acc.withdraw(500000)
    assert acc.account_info.withdraw == 500000
    assert acc.account_info.fund_shares == 500000
    acc.deposit(100000)
    assert acc.account_info.withdraw == 500000
    assert acc.account_info.deposit == 100000
    assert acc.account_info.fund_shares == 600000
    acc.deposit(400000)

    # 新下单
    agent_order = vxOrder(
        account_id=acc.account_id,
        symbol="SHSE.test",
        price=20.0,
        volume=10000,
        order_type="Limit",
        order_direction="Buy",
        order_offset="Open",
        frozen_position_id=cash_position.position_id,
    )
    assert agent_order.order_direction == OrderDirection.Buy
    assert agent_order.order_type == OrderType.Limit
    acc.on_order_status(agent_order)
    # 检查下单状态处理是否正确
    assert agent_order.order_id in acc.get_orders()
    assert agent_order.frozen_position_id == cash_position.position_id

    assert (
        round((agent_order.volume * agent_order.price) * 1.003, 2)
        == cash_position.frozen
    )
    assert (
        round((agent_order.volume * agent_order.price) * 1.003, 2)
        == acc.account_info.frozen
    )
    assert cash_position.marketvalue == balance
    assert acc.account_info.asset == balance

    # 返回exchange_order_id
    agent_order.exchange_order_id = str(uuid.uuid4())
    agent_order.status = OrderStatus.New
    acc.on_order_status(agent_order)
    vxorder = acc.get_orders(order_id=agent_order.order_id)[agent_order.order_id]
    assert id(vxorder) != id(agent_order)
    assert vxorder.exchange_order_id == agent_order.exchange_order_id
    assert vxorder.status == OrderStatus.New
    assert vxorder.filled_volume == 0

    # 收到第一笔成交订单
    agent_trade = vxTrade(
        account_id=agent_order.account_id,
        order_id=agent_order.order_id,
        exchange_order_id=agent_order.exchange_order_id,
        order_direction=agent_order.order_direction,
        order_offset=agent_order.order_offset,
        symbol=agent_order.symbol,
        volume=1000,
        price=15,
        commission=1000,
        status=TradeStatus.Trade,
    )
    acc.on_execution_reports(agent_trade)

    vxtrade = acc.get_trades(trade_id=agent_trade.trade_id)[agent_trade.trade_id]

    assert id(vxtrade) != id(agent_trade)
    assert vxtrade.trade_id == agent_trade.trade_id
    assert vxtrade.order_id == agent_trade.order_id
    assert vxtrade.account_id == agent_trade.account_id
    assert vxtrade.exchange_order_id == agent_trade.exchange_order_id
    assert vxtrade.volume == agent_trade.volume
    assert vxtrade.price == agent_trade.price
    assert vxtrade.commission == agent_trade.commission

    cost = agent_trade.volume * agent_trade.price + agent_trade.commission
    symbol_position = acc.get_positions(symbol="SHSE.test")

    assert symbol_position.cost == cost
    assert symbol_position.volume == agent_trade.volume
    assert symbol_position.lasttrade == agent_trade.price
    assert acc.account_info.asset == balance - agent_trade.commission
    assert acc.account_info.balance == balance - cost
    assert acc.account_info.frozen == round(
        (vxorder.volume - vxorder.filled_volume) * vxorder.price * 1.003, 2
    )
    assert vxorder.filled_volume == agent_trade.volume
    assert vxorder.filled_amount == cost
    assert vxorder.status == OrderStatus.PartiallyFilled
    commission = 1600

    # 收到第2笔成交订单
    agent_trade2 = vxTrade(
        account_id=agent_order.account_id,
        order_id=agent_order.order_id,
        exchange_order_id=agent_order.exchange_order_id,
        order_direction=agent_order.order_direction,
        order_offset=agent_order.order_offset,
        symbol=agent_order.symbol,
        volume=1000,
        price=16,
        commission=commission,
        status=TradeStatus.Trade,
    )
    acc.on_execution_reports(agent_trade2)

    cost += agent_trade2.volume * agent_trade2.price + agent_trade2.commission
    trades = acc.get_trades()
    assert agent_trade2.trade_id in trades
    assert symbol_position.cost == cost
    assert (
        symbol_position.volume
        == vxorder.filled_volume
        == agent_trade.volume + agent_trade2.volume
    )
    assert vxorder.filled_amount == cost
    assert cash_position.marketvalue == balance - cost
    assert cash_position.frozen == round(
        (vxorder.volume - vxorder.filled_volume) * vxorder.price * 1.003, 2
    )
    assert (
        acc.account_info.fnl
        == agent_trade.volume * (agent_trade2.price - agent_trade.price)
        - agent_trade.commission
        - agent_trade2.commission
    )

    # 收到第3笔成交订单
    agent_trade3 = vxTrade(
        account_id=agent_order.account_id,
        order_id=agent_order.order_id,
        exchange_order_id=agent_order.exchange_order_id,
        order_direction=agent_order.order_direction,
        order_offset=agent_order.order_offset,
        symbol=agent_order.symbol,
        volume=8000,
        price=20,
        commission=2000,
        status=TradeStatus.Trade,
    )
    acc.on_execution_reports(agent_trade3)
    trades = acc.get_trades()
    cost += agent_trade3.volume * agent_trade3.price + agent_trade3.commission
    assert agent_trade3.trade_id in trades
    assert vxorder.filled_volume == sum(
        [agent_trade.volume, agent_trade2.volume, agent_trade3.volume]
    )
    print(cost)
    assert vxorder.filled_amount == cost
    assert vxorder.status == OrderStatus.Filled
    assert acc.account_info.frozen == 0
    assert cash_position.frozen == 0
    assert cash_position.marketvalue == balance - cost
    assert acc.account_info.fnl == 10000 * 20 - cost
    # asset = acc.account_info.asset
    # nav = acc.account_info.nav
    acc.on_settle()
    assert len(acc.get_orders()) == 0
    assert len(acc.get_trades()) == 0
    assert cash_position.volume_today == 0
    assert cash_position.marketvalue == balance - cost
    assert symbol_position.volume_today == 0

    print(agent_trade3)
    print(vxorder)
    print(acc.message)


if __name__ == "__main__":

    test_account()
