"""组合相关数据模型"""


from typing import Optional
from multiprocessing import Lock

from vxquant.utils import vxtime, logger
from vxquant.utils.convertors import to_timestring
from vxquant.model.preset import vxMarketPreset
from vxquant.model.contants import (
    TradeStatus,
    OrderStatus,
    OrderDirection,
    AccountType,
)
from vxquant.model.broker import (
    vxAccountInfo,
    vxPosition,
    vxOrder,
    vxTrade,
    vxCashPosition,
)


class vxAccountBase:
    """证券账户基类"""

    @property
    def account_id(self):
        """账户id"""
        raise NotImplementedError

    @property
    def account_info(self):
        """账户信息"""
        raise NotImplementedError

    def get_positions(self, symbol=None):
        """获取持仓信息"""
        raise NotImplementedError


class vxStockAccount:
    """股票账户"""

    def __init__(
        self,
        account_id=None,
        balance=100_0000,
        account_type=AccountType.Normal,
        portfolio_id=None,
    ):
        self._account_type = account_type
        self._account_info = vxAccountInfo(
            account_id=account_id, portfolio_id=portfolio_id
        )
        self._positions = {}
        self._algo_orders = {}
        self._orders = {}
        self._trades = {}

        self._positions["CNY"] = vxCashPosition(
            account_id=account_id,
            symbol="CNY",
            security_type="CASH",
            allow_t0=True,
            lasttrade=1.0,
        )

        self._lock = Lock()

        self.deposit(balance)
        self.on_settle()

    def __str__(self):
        return f"< {self.__class__.__name__}({id(self)}) :\n {self.account_info} >"

    __repr__ = __str__

    @property
    def account_id(self):
        """账户id"""
        return self._account_info.account_id

    @property
    def account_info(self):
        """账户信息"""
        return self._account_info

    def get_positions(self, symbol: Optional[str] = None) -> dict | vxPosition:
        """获取持仓信息"""
        if not symbol:
            return self._positions

        if symbol in self._positions:
            return self._positions[symbol]

        preset = vxMarketPreset(symbol)
        return vxPosition(
            account_id=self.account_id,
            symbol=symbol,
            security_type=preset.security_type,
            allow_t0=preset.allow_t0,
        )

    def get_orders(
        self,
        order_id: Optional[str] = None,
        algo_order_id: Optional[str] = None,
        exchange_order_id: Optional[str] = None,
    ) -> dict[Optional[vxOrder]]:
        """获取当日委托信息"""
        if order_id:
            return (
                {order_id: self._orders[order_id]} if order_id in self._orders else {}
            )

        if algo_order_id:
            return {
                order_id: order
                for order in self._orders.values()
                if order.algo_order_id == algo_order_id
            }

        if exchange_order_id:
            return {
                order.order_id: order
                for order in self._orders.values()
                if order.exchange_order_id == exchange_order_id
            }

        return self._orders

    def get_trades(
        self, order_id: Optional[str] = None, trade_id: Optional[str] = None
    ) -> dict:
        """获取当日成交回报"""
        if order_id:
            return {
                trade.trade_id: trade
                for trade in self._trades.values()
                if trade.order_id == order_id
            }

        if trade_id:
            return (
                {trade_id: self._trades[trade_id]} if trade_id in self._trades else {}
            )

        return self._trades

    def deposit(self, money: float) -> None:
        """转入金额"""
        if money <= 0:
            raise ValueError(f"转入金额 {money} <= 0 错误.")

        with self._lock:
            self.account_info.deposit += money
            self.account_info.fund_shares += money / self.account_info.fund_nav
            self._positions["CNY"].volume_today += money
            self._positions["CNY"].cost += money
            self.update_account_info()

    def withdraw(self, money: float) -> None:
        """转出金额"""
        if money <= 0:
            raise ValueError(f"转出金额 {money} <= 0 错误.")

        cash = self._positions["CNY"]
        if money > cash.available:
            raise ValueError(f"转出金额{money} 大于可用金额 {cash.available}。 ")
        with self._lock:
            self.account_info.withdraw += money
            self.account_info.fund_shares -= money / self.account_info.fund_nav
            if money < cash.volume_his:
                cash.volume_his -= money
            else:
                money -= cash.volume_his
                cash.volume_his = 0
                cash.volume_today -= money
            cash.cost = cash.marketvalue
            self.update_account_info()

    @property
    def message(self) -> dict:
        """账户消息"""
        return {
            "account_info": self.account_info,
            "positions": self.get_positions(),
            "orders": self.get_orders(),
            "trades": self.get_trades(),
        }

    def update_account_info(self) -> None:
        """更新账户信息"""

        self._account_info.marketvalue = 0
        self._account_info.fnl = 0

        for position in self._positions.values():
            position.frozen = 0
            if position.symbol != "CNY":
                self._account_info.marketvalue += position.marketvalue
                self._account_info.fnl += position.fnl
            else:
                self._account_info.balance = position.marketvalue
                position.cost = position.marketvalue

        for order in self._orders.values():
            if not order.frozen_position_id or order.status not in [
                OrderStatus.New,
                OrderStatus.PartiallyFilled,
                OrderStatus.PendingNew,
            ]:
                continue

            if order.order_direction == OrderDirection.Buy:
                filled_amount = (
                    (order.volume - order.filled_volume) * order.price * 1.003
                )
                self._positions["CNY"].frozen += filled_amount

            else:
                self._positions[order.symbol].frozen += (
                    order.volume - order.filled_volume
                )
        self.account_info.frozen = self._positions["CNY"].frozen
        logger.debug(f"更新后账户信息: {self.message}")

    def on_tick(self, ticks: dict) -> None:
        """更新交易价格"""
        update_symbols = set(self._positions.keys()) | set(ticks.keys())
        with self._lock:
            for symbol in update_symbols.items():
                self._positions[symbol].lasttrade = ticks[symbol].lasttrade
                self._positions[symbol].updated_dt = ticks[symbol].created_dt
            self.account_info.marketvalue = sum(
                p.marketvalue for p in self._positions.values() if p.symbol != "CNY"
            )

    def on_order_status(self, agent_order: vxOrder) -> None:
        """更新订单状态"""

        with self._lock:
            if agent_order.order_id not in self._orders:
                self._orders[agent_order.order_id] = vxOrder(agent_order.message)
                self.update_account_info()
                return

            vxorder = self._orders[agent_order.order_id]
            if (
                agent_order.status in (OrderStatus.PendingNew, OrderStatus.New)
                and not vxorder.exchange_order_id
            ):
                vxorder.exchange_order_id = agent_order.exchange_order_id
                vxorder.updated_dt = agent_order.updated_dt
                vxorder.status = agent_order.status
                return

            elif agent_order.status in (
                OrderStatus.Canceled,
                OrderStatus.Expired,
                OrderStatus.Filled,
                OrderStatus.Rejected,
                OrderStatus.Suspended,
                OrderStatus.PendingNew,
            ):
                vxorder.filled_volume = agent_order.filled_volume
                vxorder.filled_amount = agent_order.filled_amount
                vxorder.exchange_order_id = agent_order.exchange_order_id
                vxorder.status = agent_order.status
                vxorder.updated_dt = agent_order.updated_dt

            vxorder.exchange_order_id = agent_order.exchange_order_id
            vxorder.status = agent_order.status
            self._orders[agent_order.order_id].updated_dt = agent_order.updated_dt
            self.update_account_info()

    def _handler_open_position(
        self,
        position: vxPosition | vxCashPosition,
        volume: float,
        filled_amount: float,
    ):
        """处理开仓仓位"""
        position.volume_today += volume
        position.cost += filled_amount
        self._positions[position.symbol] = position

    def _handler_close_position(
        self, position: vxPosition | vxCashPosition, volume: float, filled_amount: float
    ):
        """处理平仓仓位"""
        deta = position.volume_his - volume
        position.volume_his = max(deta, 0)
        position.volume_today = (
            position.volume_today if deta >= 0 else position.volume_today + deta
        )
        position.cost -= filled_amount
        self._positions[position.symbol] = position

    def on_execution_reports(self, agent_trade: vxTrade) -> None:
        """更新成交回报信息"""
        if agent_trade.status != TradeStatus.Trade:
            return

        if agent_trade.trade_id in self._trades:
            logger.warning(f"收到重复的委托订单信息 {agent_trade.trade_id} {agent_trade}")
            return

        vxorder = self.get_orders(agent_trade.order_id).get(agent_trade.order_id, None)

        if vxorder is None:
            logger.warning(f"未知订单{agent_trade.order_id}")
            return

        if vxorder.status in (
            OrderStatus.Canceled,
            OrderStatus.Expired,
            OrderStatus.Rejected,
            OrderStatus.Suspended,
        ):
            logger.warning(f"已终止订单{vxorder.order_id} 收到成交信息:{agent_trade}")
            return

        with self._lock:
            self._trades[agent_trade.trade_id] = vxTrade(agent_trade.message)

            cash_position = self.get_positions("CNY")
            symbol_position = self.get_positions(agent_trade.symbol)
            symbol_position.lasttrade = agent_trade.price

            if agent_trade.order_direction == OrderDirection.Buy:
                filled_amount = (
                    agent_trade.price * agent_trade.volume + agent_trade.commission
                )
                # 扣减现金仓位
                self._handler_close_position(
                    cash_position, filled_amount, filled_amount
                )
                self._handler_open_position(
                    symbol_position, agent_trade.volume, filled_amount
                )
            else:
                filled_amount = (
                    agent_trade.price * agent_trade.volume - agent_trade.commission
                )
                # 扣减symbol 持仓
                self._handler_close_position(
                    symbol_position, agent_trade.volume, filled_amount
                )
                self._handler_open_position(cash_position, filled_amount, filled_amount)

            vxorder.filled_volume += agent_trade.volume
            vxorder.filled_amount += filled_amount
            if 0 < vxorder.filled_volume < vxorder.volume:
                vxorder.status = OrderStatus.PartiallyFilled
            else:
                vxorder.status = OrderStatus.Filled

            self.update_account_info()

    def on_settle(self):
        """日结函数"""
        now = vxtime.now()
        logger.debug(f"开始执行日结{to_timestring(now,'%Y-%m-%d')}")

        expired_orders = []
        with self._lock:
            # 1. 去掉超时以及当天已完成订单
            orders = self._orders
            self._orders = {}
            for order in orders.values():
                if order.status in [
                    OrderStatus.Canceled,
                    OrderStatus.Expired,
                    OrderStatus.Filled,
                    OrderStatus.Rejected,
                    OrderStatus.Suspended,
                ]:
                    continue

                if order.due_dt >= now:
                    expired_orders.append(order)

                self._orders[order.order_id] = order

            # 超时的成交信息去掉
            self._trades = {
                trade_id: trade
                for trade_id, trade in self._trades.items()
                if trade.order_id in self._orders
            }
            # position
            positions = self._positions
            self._positions = {}
            for symbol, position in positions.items():
                if position.volume == 0 and position.symbol != "CNY":
                    continue
                position.volume_his, position.volume_today = position.volume, 0
                self._positions[symbol] = position

            self.update_account_info()
            self.account_info.deposit = 0
            self.account_info.withdraw = 0
            self.account_info.asset_yd = self.account_info.asset
            self.account_info.fund_nav_yd = self.account_info.fund_nav
            self.account_info.nav_yd = self.account_info.nav

    def update(
        self,
        account_info: Optional[vxAccountInfo] = None,
        positions: dict[str, vxPosition | vxCashPosition] = None,
        orders: dict[str, vxOrder] = None,
        trades: dict[str, vxTrade] = None,
    ) -> None:
        """直接账户基本信息"""
        with self._lock:
            if account_info:
                self._account_info = account_info

            if positions:
                self._positions = positions

            if orders:
                self._orders = orders

            if trades:
                self._trades = trades
            self.update_account_info()

    @classmethod
    def load_account(
        cls,
        account_info: vxAccountInfo,
        positions: dict[str, vxPosition | vxCashPosition],
        orders: dict[str, vxOrder],
        trades: dict[str, vxTrade],
    ) -> "vxStockAccount":
        """加载账户信息"""
        instance = cls.__new__(cls=cls)
        instance.update(account_info, positions, orders, trades)
        return instance
