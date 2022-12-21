"""组合相关数据模型"""


import uuid
import pymongo

from typing import Optional, Union, Dict
from multiprocessing import Lock

from vxsched import vxZMQPublisher, vxZMQSubscriber
from vxutils import vxtime, logger
from vxutils.database import vxMongoDB
from vxutils.convertors import to_timestring
from vxquant.exceptions import (
    NoEnoughCash,
    NoEnoughPosition,
    IllegalVolume,
    IllegalPrice,
    # * RiskRuleCheckFailed,
    # * IllegalAccountId,
    # * IllegalStrategyId,
    # * IllegalSymbol,
    # * AccountDisabled,
    # * AccountDisconnected,
    # * AccountLoggedout,
    # * NotInTradingSession,
    # * OrderTypeNotSupported,
    # * Throttle,
    # * IllegalOrder,
    # * OrderFinalized,
    # * UnknownOrder,
    # * AlreadyInPendingCancel,
)
from vxquant.mdapi.hq import vxTdxHQ
from vxquant.model.preset import vxMarketPreset
from vxquant.model.contants import (
    OrderOffset,
    TradeStatus,
    OrderType,
    OrderStatus,
    OrderDirection,
    AccountType,
)
from vxquant.model.exchange import (
    vxAccountInfo,
    vxPosition,
    vxOrder,
    vxTrade,
    vxCashPosition,
    vxTick,
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
        publisher=None,
    ):
        self._account_type = account_type
        self._account_info = vxAccountInfo(
            account_id=account_id, portfolio_id=portfolio_id
        )
        self._positions = {}
        self._algo_orders = {}
        self._orders = {}
        self._trades = {}
        self._publisher = publisher

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

    def get_positions(
        self, symbol: Optional[str] = None
    ) -> Union[Dict, vxPosition, vxCashPosition]:
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
    ) -> Dict[str, Optional[vxOrder]]:
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
            raise IllegalPrice(f"转入金额 {money} <= 0 错误.")

        with self._lock:
            self.account_info.deposit += money
            self.account_info.fund_shares += money / self.account_info.fund_nav
            self._positions["CNY"].volume_today += money
            self._positions["CNY"].cost += money
            self.update_account_info()

    def withdraw(self, money: float) -> None:
        """转出金额"""
        if money <= 0:
            raise IllegalPrice(f"转出金额 {money} <= 0 错误.")

        cash = self._positions["CNY"]
        if money > cash.available:
            raise NoEnoughCash(f"转出金额{money} 大于可用金额 {cash.available}。 ")
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

    def set_bechmark_marketvalue(
        self,
        symbol: str,
        benchmark_marketvalue: float = -1,
        uplimit: float = -1,
        downlimit: float = -1,
    ) -> None:
        """设置持仓基准市值、持仓市值上限，持仓市值下限

        Arguments:
            symbol {str} -- 证券代码
            benchmark_marketvalue {float} -- 持仓基准市值，若市值小于0，则不做持仓市值监控 (default: {-1})
            uplimit {float} -- 持仓市值上限，市值突破上限时，减仓至基准市值。 若小于0，则不做上限管理  (default: {-1})
            downlimit {float} -- 持仓市值下限，市值跌破下限时，加仓至基准市值。若小于0，则不做下限管理 (default: {-1})
        """
        position = self.get_positions(symbol)
        position.benchmark_marketvalue = benchmark_marketvalue
        position.uplimit_marketvalue = uplimit
        position.downlimit_marketvalue = downlimit
        self._positions[position.position_id] = position

    def check_benchmark_marketvalue(self):
        """检查目标市值是否突破"""

    def submit_order(self, symbol: str, volume: float, price=0) -> vxOrder:
        """提交订单
        进行下单前的检查，并且冻结资金及股票，形成一个PendingNew状态的order 以便提交

        Arguments:
            symbol {str} -- 下单标的
            volume {float} -- 下单数量
            price {int} -- 交易价格，若交易价格为0，则适用市价单，否则采用限价单 (default: {0})

        Returns:
            vxOrder -- 委托订单
        """
        if volume == 0:
            raise IllegalVolume("volume不能为0.")

        with self._lock:
            if volume > 0:
                if not price:
                    tick = self.current(symbol)
                    amount = (tick.lasttrade * volume) * 1.003
                else:
                    amount = price * volume * 1.003

                position = self.get_positions("CNY")
                if position.available < amount:
                    raise NoEnoughCash(
                        f"Not enough cash({position.available}) < need({amount})"
                    )
            else:
                position = self.get_positions(symbol)
                if position.available < volume:
                    raise NoEnoughPosition(
                        f"Not enough volume {symbol} {position.available} < amount"
                    )

            vxorder = vxOrder(
                account_id=self.account_id,
                symbol=symbol,
                order_direction=OrderDirection.Buy
                if volume > 0
                else OrderDirection.Sell,
                order_offset=OrderOffset.Open if volume > 0 else OrderOffset.Close,
                order_type=OrderType.Limit if price <= 0 else OrderType.Market,
                volume=abs(volume),
                price=price,
                status=OrderStatus.PendingNew,
            )
            self._orders[vxorder.order_id] = vxorder
            self.update_account_info()

        if self._publisher:
            logger.debug(f"通过 {self._publisher.channel_name} 下单: {vxorder}")
            self._publisher("on_submit_broker_order", vxorder)

        return vxorder

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
            if order.status not in [
                OrderStatus.PendingNew,
                OrderStatus.New,
                OrderStatus.PartiallyFilled,
            ]:
                continue

            if order.order_direction == OrderDirection.Buy:
                need_amount = (order.volume - order.filled_volume) * order.price * 1.003
                self._positions["CNY"].frozen += need_amount

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

        if agent_order.order_id not in self._orders:
            with self._lock:
                self._orders[agent_order.order_id] = vxOrder(agent_order.message)
                self.update_account_info()
                return

        vxorder = self._orders[agent_order.order_id]
        if vxorder.status in (
            OrderStatus.Canceled,
            OrderStatus.Expired,
            OrderStatus.Filled,
            OrderStatus.Rejected,
            OrderStatus.Suspended,
        ):
            logger.info(
                f"已经完结的委托信息，收到更新委托: {agent_order.status} {agent_order.filled_volume}"
            )
            return

        if vxorder.filled_volume > agent_order.filled_volume:
            logger.info(
                f"收到早前的委托订单更新信息.filled_volume: vxorder{vxorder.filled_volume} >"
                f" agent_order:{agent_order.filled_volume}."
            )
            return

        with self._lock:
            vxorder.exchange_order_id = agent_order.exchange_order_id
            vxorder.filled_volume = agent_order.filled_volume
            vxorder.filled_amount = agent_order.filled_amount
            vxorder.status = agent_order.status
            vxorder.updated_dt = agent_order.updated_dt
            self.update_account_info()

    def _handler_open_position(
        self,
        position: Union[vxPosition, vxCashPosition],
        volume: float,
        filled_amount: float,
    ):
        """处理开仓仓位"""
        position.volume_today += volume
        position.cost += filled_amount
        self._positions[position.symbol] = position

    def _handler_close_position(
        self,
        position: Union[vxPosition, vxCashPosition],
        volume: float,
        filled_amount: float,
    ):
        """处理平仓仓位"""
        deta = position.volume_his - volume
        position.volume_his = max(deta, 0)
        position.volume_today = (
            position.volume_today if deta >= 0 else position.volume_today + deta
        )
        position.cost -= filled_amount
        self._positions[position.symbol] = position

    def on_execution_report(self, agent_trade: vxTrade) -> None:
        """更新成交回报信息"""
        if agent_trade.status != TradeStatus.Trade:
            logger.warning(f"收到非成交回报信息。 {agent_trade}")
            return

        if agent_trade.trade_id in self._trades:
            logger.warning(f"收到重复的委托订单信息 {agent_trade.trade_id} {agent_trade}")
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
            cash_position.updated_dt = agent_trade.updated_dt
            symbol_position.updated_dt = agent_trade.updated_dt

            self._handle_order_status(agent_trade, filled_amount)
            self.update_account_info()

    def _handle_order_status(self, agent_trade: vxTrade, filled_amount: float) -> None:
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

        vxorder.filled_volume += agent_trade.volume
        vxorder.filled_amount += filled_amount
        vxorder.status = (
            OrderStatus.PartiallyFilled
            if vxorder.filled_volume < vxorder.volume
            else OrderStatus.Filled
        )
        vxorder.updated_dt = max(agent_trade.updated_dt, vxorder.updated_dt)

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
        positions: Dict[str, Union[vxCashPosition, vxPosition]] = None,
        orders: Dict[str, vxOrder] = None,
        trades: Dict[str, vxTrade] = None,
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
        positions: Dict[str, Union[vxCashPosition, vxPosition]],
        orders: Dict[str, vxOrder],
        trades: Dict[str, vxTrade],
    ) -> "vxStockAccount":
        """加载账户信息"""
        instance = cls.__new__(cls=cls)
        instance.update(account_info, positions, orders, trades)
        return instance


class vxPortfolioManager:
    """组合管理"""

    def __init__(self, portfolio_id: str, dbwriter):
        pass

    def create_portfolio(self, balance: float = 10_000_000.00, account_ids=None):
        """创建组合"""

    def create_account(self, account_id, balance=1_000_000.00):
        """创建账户"""


class vxAccountsManager:
    def __init__(self, db_uri, db_name, publisher=None, hqfetcher=None):
        self._database = vxMongoDB(db_uri, db_name)
        self._database.mapping("accounts", vxAccountInfo, ["account_id"])
        self._database.mapping("positions", vxPosition, ["account_id", "symbol"])
        self._database.mapping("orders", vxOrder, ["order_id"])
        self._database.mapping("trades", vxTrade, ["trade_id"])
        self._database.mapping("current", vxTick, ["symbol"])

        self._publisher = publisher
        self._hqfetcher = hqfetcher or vxTdxHQ()
        cur = self._database.agent_mapping.find({})
        self._agent_map = {item.account_id: item.channel_name for item in cur}

    def create_account(
        self,
        account_id: str = None,
        balance: float = 1_000_000,
        portfolio_id: str = "",
        channel_name: str = None,
        if_exists: str = "skip",
    ) -> str:
        """创建账户

        Keyword Arguments:
            account_id {str} -- 账户id (default: {None})
            balance {float} -- 初始余额 (default: {1_000_000})
            portfolio_id {str} -- 组合id (default: {""})
            channel_name {str} -- 下单通道，缺省为空 (default: {None})
            if_exists {str} -- 若存在账户已存在(default: {"skip"})
                                'delete' ---> 删除原来账户
                                'skip' --->  跳过
                                'raise' ---> raise 一个exception


        Raises:
            ValueError: 账户已存在时，且if_exists == 'raise' 则raise一个exception

        Returns:
            str -- _description_
        """

        channel_name = channel_name or "simtest"

        if self._database.accounts.count_documents({"account_id": account_id}) > 0:
            if if_exists == "skip":
                return account_id
            elif if_exists == "delete":
                self._database.accounts.delete_many({"account_id": account_id})
                self._database.positions.delete_many({"account_id": account_id})
                self._database.orders.delete_many({"account_id": account_id})
                self._database.trades.delete_many({"account_id": account_id})
            elif if_exists == "raise":
                raise ValueError(f"account_id({account_id}) 已存在。")

        account_id = account_id or str(uuid.uuid4())
        account_info = vxAccountInfo(
            account_id=account_id,
            portfolio_id=portfolio_id,
            deposit=balance,
            balance=balance,
            fund_shares=balance,
            fund_nav_yd=1.0,
            settle_day=vxtime.today("00:00:00") - 60 * 60 * 24,
        )

        cash_position = vxCashPosition(
            portfolio_id=portfolio_id,
            account_id=account_id,
            volume_today=balance,
        )

        with self._database.start_session() as session:
            self._database.save("accounts", account_info, session=session)
            self._database.save("positions", cash_position, session=session)
            self._database.agent_mapping.update_one(
                {"account_id": account_id},
                {"$set": {"channel_name": channel_name}},
                upsert=True,
            )
            self._agent_map[account_id] = channel_name
        self._update_account_info([account_id])

        return account_id

    def deposit(self, account_id, money: float) -> None:
        """转入金额"""

        account_info = self._database.accounts.find_one(
            {"account_id": account_id}, {"_id": 0}
        )
        if account_info is None:
            raise ValueError(f"账户信息不存在: {account_id}")
        account_info = vxAccountInfo(account_info)

        cash_position = self._database.positions.find_one(
            {"account_id": account_id, "symbol": "CNY"}, {"_id": 0}
        )
        cash_position = vxCashPosition(cash_position)
        logger.info(f"{account_info.nav}, {money}")

        account_info.fund_shares += money / account_info.fund_nav
        account_info.deposit += money
        account_info.balance += money
        cash_position.volume_today += money
        logger.info(f"{account_info.nav}, {money},{cash_position.marketvalue}")

        with self._database.start_session() as session:
            self._database.save("accounts", account_info, session=session)
            self._database.save("positions", cash_position, session=session)

            self._update_account_info([account_id], session=session)

    def withdraw(self, account_id, money: float) -> None:
        """转出金额"""
        if money <= 0:
            raise IllegalPrice(f"转出金额 {money} <= 0 错误.")

        with self._database.start_session(causal_consistency=True) as session:
            cash = self._database.query_one(
                "positions",
                {"account_id": account_id, "symbol": "CNY"},
                session=session,
            )
            cash = vxCashPosition(cash)
            if money > cash.available:
                raise NoEnoughCash(f"转出金额{money} 大于可用金额 {cash.available}。 ")
            account_info = self._database.query_one(
                "accounts", {"account_id": account_id}, session=session
            )

            account_info.withdraw += money
            account_info.fund_shares -= money / account_info.fund_nav
            account_info.balance -= money

            if money < cash.volume_his:
                cash.volume_his -= money
            else:
                money -= cash.volume_his
                cash.volume_his = 0
                cash.volume_today -= money

            self._database.save("accounts", account_info, session=session)
            self._database.save("positions", cash, session=session)
            self._update_account_info([account_id], session=session)

    def _update_account_info(self, account_ids, session=None):
        """重新计算账户值"""

        positions = self._database.query(
            "positions", {"account_id": {"$in": account_ids}}, session=session
        )
        account_infos = {}
        update_positions = []
        for position in positions:
            if position.account_id not in account_infos:
                account_infos[position.account_id] = {
                    "balance": 0,
                    "frozen": 0,
                    "marketvalue": 0,
                    "fnl": 0,
                }
            if position.symbol == "CNY":
                cash = vxCashPosition(position)
                account_infos[position.account_id]["balance"] = cash.marketvalue
                account_infos[position.account_id]["frozen"] = cash.frozen
                update_positions.append(cash)
            else:
                account_infos[position.account_id][
                    "marketvalue"
                ] += position.marketvalue
                account_infos[position.account_id]["fnl"] += position.fnl
                update_positions.append(position)

        cur = self._database.query(
            "accounts", {"account_id": {"$in": list(account_ids)}}, session=session
        )

        update_account_infos = []
        for account_info in cur:
            update_dict = account_infos.get(account_info.account_id, {})
            account_info.update(**update_dict)
            logger.debug(f"更新后account_info:{account_info}")
            update_account_infos.append(account_info)

        self._database.save_many("positions", update_positions, session=session)
        self._database.save_many("accounts", update_account_infos, session=session)

    def _update_frozens(self, account_ids, session=None):
        """重新计算持仓冻结信息"""
        modify_position_ids = self._database.orders.distinct(
            "frozen_position_id", {"account_id": {"$in": account_ids}}, session=session
        )
        agg_position_frozens = self._database.orders.aggregate(
            [
                {
                    "$match": {
                        "frozen_position_id": {"$in": modify_position_ids},
                        "status": {"$in": ["New", "PartiallyFilled", "PendingNew"]},
                    }
                },
                {
                    "$project": {
                        "account_id": "$account_id",
                        "order_id": "$order_id",
                        "frozen_position_id": "$frozen_position_id",
                        "order_direction": "$order_direction",
                        "left_volume": {"$subtract": ["$volume", "$filled_volume"]},
                        "price": "$price",
                        "cost": {
                            "$multiply": [
                                {"$subtract": ["$volume", "$filled_volume"]},
                                "$price",
                            ]
                        },
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "account_id": "$account_id",
                            "position_id": "$frozen_position_id",
                            "order_direction": "$order_direction",
                        },
                        "left_volume": {"$sum": "$left_volume"},
                        "cost": {"$sum": "$cost"},
                    }
                },
            ],
            session=session,
        )
        update_position_cmds = [
            pymongo.UpdateMany(
                {"position_id": {"$in": modify_position_ids}}, {"$set": {"frozen": 0.0}}
            )
        ]
        update_account_cmds = []

        for agg_position_frozen in agg_position_frozens:
            position_id = agg_position_frozen["_id"]["position_id"]
            order_direction = agg_position_frozen["_id"]["order_direction"]

            if order_direction == "Buy":
                update_cmd = pymongo.UpdateOne(
                    {"position_id": position_id},
                    {"$set": {"frozen": (agg_position_frozen["cost"] * 1.003)}},
                )
                update_account_cmd = pymongo.UpdateOne(
                    {"accountt_id": agg_position_frozen["_id"]["account_id"]},
                    {"$set": {"frozen": (agg_position_frozen["cost"] * 1.003)}},
                )
                update_account_cmds.append(update_account_cmd)
                logger.info(f"更新SQL accounts: {update_account_cmd}")

            else:
                update_cmd = pymongo.UpdateOne(
                    {"position_id": position_id},
                    {"$set": {"frozen": (agg_position_frozen["left_volume"])}},
                )

            update_position_cmds.append(update_cmd)
            logger.info(f"更新SQL positions: {update_cmd}")

        self._database.positions.bulk_write(
            update_position_cmds, ordered=True, session=session
        )
        if update_account_cmds:
            self._database.accounts.bulk_write(
                update_account_cmds,
                ordered=True,
            )
            logger.warning(f"更新SQL accounts: {update_account_cmds}")
        return modify_position_ids

    def _update_order_filled_volumes(self, account_ids, session=None):
        """重新计算委托订单成交信息"""
        unfinished_order_ids = self._database.distinct(
            "orders",
            "order_id",
            {
                "status": {"$in": ["New", "PendingNew", "PartiallyFilled", "Unknown"]},
                "account_id": {"$in": account_ids},
            },
            session=session,
        )
        logger.info(f"共有{len(unfinished_order_ids)}个未完成订单.")
        agg_filled_volumes = self._database.trades.aggregate(
            [
                {"$match": {"order_id": {"$in": unfinished_order_ids}}},
                {
                    "$group": {
                        "_id": {
                            "order_id": "$order_id",
                            "order_direction": "$order_direction",
                        },
                        "volume": {"$max": "$volume"},
                        "filled_volume": {"$sum": "$volume"},
                        "commission": {"$sum": "$commission"},
                        "cost": {"$sum": {"$multiply": ["$price", "$volume"]}},
                    }
                },
                {"$match": {"filled_volume": {"$gt": 0}}},
            ],
            session=session,
        )

        update_order_cmds = []
        modify_order_ids = []
        for agg_filled_volume in agg_filled_volumes:
            order_id = agg_filled_volume["_id"]["order_id"]
            order_direction = agg_filled_volume["_id"]["order_direction"]
            filled_amount = (
                (agg_filled_volume["cost"] + agg_filled_volume["cost"])
                if order_direction == "Buy"
                else (agg_filled_volume["cost"] - agg_filled_volume["cost"])
            )
            filled_vwap = filled_amount / agg_filled_volume["filled_volume"]
            logger.info(
                f"订单{order_id} {order_direction} filled_amount={filled_amount} filled_vwap={filled_vwap}."
            )

            update_order_cmd = pymongo.UpdateOne(
                {"order_id": order_id},
                {
                    "$set": {
                        "filled_volume": agg_filled_volume["filled_volume"],
                        "filled_amount": filled_amount,
                        "filled_vwap": filled_vwap,
                        "status": "Filled"
                        if agg_filled_volume["filled_volume"]
                        >= agg_filled_volume["volume"]
                        else "PartiallyFilled",
                    }
                },
            )
            update_order_cmds.append(update_order_cmd)
            modify_order_ids.append(order_id)
        if update_order_cmds:
            self._database.accounts.bulk_write(update_order_cmds, session=session)
        return modify_order_ids

    def get_account(self, account_id: str, session=None) -> vxAccountInfo:
        """获取账户信息

        Arguments:
            account_id {str} -- 账户id

        Returns:
            vxAccountInfo -- 账户信息
        """
        logger.info(f"account_id({account_id}) session: {session}")
        item = self._database.accounts.find_one(
            {"account_id": account_id}, session=session
        )

        return vxAccountInfo(item)

    def get_positions(self, account_id: str, symbol: str = None) -> Dict:
        """获取相应的持仓信息

        Arguments:
            account_id {str} -- account_id 账户id
            symbol {str} -- 持仓信息 (default: {None})

        Returns:
            Dict -- Dict['account_id': vxAccountInfo]
        """
        filter_ = {"account_id": account_id}
        if symbol:
            filter_["symbol"] = symbol
        cur = self._database.query("positions", filter_)
        return {position.symbol: position for position in cur}

    def get_orders(
        self,
        account_id: str,
        order_id: str = None,
        exchange_order_id: str = None,
        is_unfinished=False,
    ) -> Dict:
        """获取成交订单信息

        Arguments:
            account_id {str} -- 账户id

        Keyword Arguments:
            order_id {str} -- 委托订单id (default: {None})
            exchange_order_id {str} -- 交易所委托订单id (default: {None})
            is_unfinished {bool} -- 是否未完成 (default: {False})

        Returns:
            Dict -- Dict['order_id': vxOrder]
        """
        filter_ = {"account_id": account_id}
        if order_id:
            filter_["order_id"] = order_id
        if exchange_order_id:
            filter_["exchange_order_id"] = exchange_order_id
        if is_unfinished:
            filter_["status"] = {"$in": ["New", "PendingNew", "PartiallyFilled"]}

        cur = self._database.query("orders", filter_)
        return {o.order_id: o for o in cur}

    def get_trades(
        self,
        account_id: str,
        order_id: str = None,
        trade_id: str = None,
        exchange_order_id: str = None,
    ) -> Dict:
        """获取成交信息

        Arguments:
            account_id {str} -- 账户id

        Keyword Arguments:
            order_id {str} -- 委托订单id (default: {None})
            trade_id {str} -- 成交回报id (default: {None})
            exchange_order_id {str} -- 交易所委托订单id (default: {None})

        Returns:
            Dict -- Dict['trade_id':vxTrade]
        """
        filter_ = {"account_id": account_id}
        if order_id:
            filter_["order_id"] = order_id

        if trade_id:
            filter_["trade_id"] = trade_id

        if exchange_order_id:
            filter_["exchange_order_id"] = exchange_order_id

        cur = self._database.query("trades", filter_)
        return {t.trade_id: t for t in cur}

    def _update_ticks(self, *symbols) -> Dict:
        """更新ticks数据

        Returns:
            Dict -- Dict['symbol':vxTick]
        """
        now = vxtime.now()
        cached_symbols = self._database.distinct(
            "current",
            "symbol",
            {"symbol": {"$in": symbols}, "created_dt": {"$gt": now - 3}},
        )
        missing_symbols = set(symbols) - set(cached_symbols)
        if len(missing_symbols) > 0:
            vxticks = self._hqfetcher(*missing_symbols)

            self._database.save_many("current", vxticks.values())
        cur = self._database.query("current", {"symbol": {"$in": symbols}})
        return {vxtick.symbol: vxtick for vxtick in cur}

    def order_volume(
        self,
        account_id: str,
        symbol: str,
        volume: int,
        price: float = 0.0,
        algo_order_id: str = "",
    ) -> vxOrder:
        """委托交易volume的symbol证券

        Arguments:
            account_id {str} -- 交易账号
            symbol {str} -- 目标证券代码
            volume {int} -- volume> 0时，表示买入，volume < 0时，表示卖出
            price {float} -- price 为0 时，则表示市价单，price > 0 时，表示限价单 (default: {0.0})

        Returns:
            vxOrder -- 委托订单号
        """
        with self._database.start_session(
            causal_consistency=True, lock=True
        ) as session:
            order = vxOrder(
                account_id=account_id,
                algo_order_id=algo_order_id,
                symbol=symbol,
                status="PendingNew",
            )

            if price < 0.0:
                raise ValueError(f"委托价格({price})必须大于等于0.")
            elif price == 0:
                order.order_type = "Market"
                tick = self._update_ticks(order.symbol)

                order.price = (
                    tick[order.symbol].bid1_p
                    if volume < 0
                    else tick[order.symbol].ask1_p
                )
            else:
                order.order_type = "Limit"
                order.price = price

            if volume == 0:
                raise ValueError("委托volume 不可以为0.")

            elif volume > 0:
                order.order_direction = "Buy"
                order.order_offset = "Open"
                order.volume = volume
                frozen_position = self._database.query_one(
                    "positions",
                    {"account_id": account_id, "symbol": "CNY"},
                    session=session,
                )
                frozen_position = vxCashPosition(frozen_position)
                frozen_amount = order.volume * order.price * 1.003
                if frozen_amount > frozen_position.available:
                    raise NoEnoughCash(
                        f"Buy {symbol} volume({order.volume}) on price({order.price})"
                        f" frozen {frozen_amount} > {frozen_position.available}"
                    )
                order.frozen_position_id = frozen_position.position_id
                frozen_position.frozen += frozen_amount
            else:
                order.order_direction = "Sell"
                order.order_offset = "Close"
                order.volume = abs(volume)
                frozen_position = self._database.query_one(
                    "positions",
                    {"account_id": account_id, "symbol": symbol},
                    session=session,
                )
                if not frozen_position or frozen_position.available < order.volume:
                    raise NoEnoughPosition(
                        f"Sell {symbol} volume({order.volume})"
                        f" 可用持仓:({frozen_position.available if frozen_position else 0})."
                    )
                order.frozen_position_id = frozen_position.position_id
                frozen_position.available += order.volume

            self._database.save("orders", order, session=session)
            self._database.save("positions", frozen_position, session=session)

            self._update_frozens([account_id], session=session)
            self._update_account_info([account_id], session=session)

            channel = self._agent_map.get(account_id, "simtest")
            self._publisher("on_submit_broker_order", data=order, channel=channel)
            logger.warning(
                f"account({account_id}) 通过channel({channel}) 发送"
                f" on_submit_broker_order 委托订单: {order}"
            )
            return order

    def order_cancel(self, *orders):
        """取消委托订单"""

        cancel_order_ids = [order.order_id for order in orders]

        cur = self._database.query(
            "orders",
            {
                "order_id": {"$in": cancel_order_ids},
                "status": {"$in": ["New", "PendingNew", "PartiallyFilled"]},
                "exchange_order_id": {"$ne": ""},
            },
        )
        for order in cur:
            channel = self._agent_map.get(order.account_id, "simtest")
            self._publisher("on_submit_broker_order_cancel", order, channel=channel)
            logger.warning(
                f"account({order.account_id})通过 {channel} 发送 on_submit_broker_cancel"
                f" 取消委托订单: {order}"
            )
        return

    def on_order_status(self, context, event) -> None:
        """订单状态更新"""
        with self._database.start_session(causal_consistency=True) as session:
            # 1. 更新order 状态信息
            broker_order = event.data
            if broker_order.status not in [
                OrderStatus.PartiallyFilled,
                OrderStatus.New,
                OrderStatus.PendingNew,
            ]:
                # 已终结订单，根据返回信息更新数据库订单
                self._database.orders.update_one(
                    {
                        "order_id": broker_order.order_id,
                        "status": {"$in": ["New", "PendingNew", "PartiallyFilled"]},
                    },
                    {
                        "$set": {
                            "filled_volume": broker_order.filled_volume,
                            "filled_amount": broker_order.filled_amount,
                            "filled_vwap": broker_order.filled_vwap,
                            "status": broker_order.status.name,
                            "exchange_order_id": broker_order.exchange_order_id,
                            "updated_dt": broker_order.updated_dt,
                        }
                    },
                    upsert=True,
                    session=session,
                )
            else:
                self._database.orders.update_one(
                    {
                        "order_id": broker_order.order_id,
                        "status": {"$in": ["New", "PendingNew", "PartiallyFilled"]},
                    },
                    {
                        "$set": {
                            "filled_volume": broker_order.filled_volume,
                            "filled_amount": broker_order.filled_amount,
                            "filled_vwap": broker_order.filled_vwap,
                            "status": broker_order.status.name,
                            "exchange_order_id": broker_order.exchange_order_id,
                            "updated_dt": broker_order.updated_dt,
                        }
                    },
                    session=session,
                )
            self._update_frozens([broker_order.account_id], session=session)
            self._update_account_info([broker_order.account_id], session=session)

    def on_trade_status(self, context, event) -> None:
        """收到成交回报信息"""

        with self._database.start_session(
            causal_consistency=True, lock=True
        ) as session:
            broker_trade = event.data
            # 保存trades 层数据
            self._database.save("trades", broker_trade, session=session)

            # 处理order filled_volumes
            self._update_order_filled_volumes(
                [broker_trade.account_id], session=session
            )

            # 处理 position volume数据
            if broker_trade.order_direction == OrderDirection.Buy:
                self._update_position_buy(broker_trade, session)
            else:
                self._update_position_sell(broker_trade, session)
            self._update_frozens([broker_trade.account_id], session=session)
            self._update_account_info([broker_trade.account_id], session=session)

            # *cash = self._database.positions.find_one(
            # *    {"account_id": broker_trade.account_id, "symbol": "CNY"},
            # *    {"_id": 0},
            # *    session=session,
            # *)
            # *cash = vxCashPosition(cash)
            # *
            # *symbol_position = self._database.query_one(
            # *    "positions",
            # *    {"account_id": broker_trade.account_id, "symbol": broker_trade.symbol},
            # *    session=session,
            # *)
            # *if not symbol_position:
            # *    preset = vxMarketPreset(broker_trade.symbol)
            # *    symbol_position = vxPosition(
            # *        account_id=broker_trade.account_id,
            # *        symbol=broker_trade.symbol,
            # *        security_type=preset.security_type,
            # *        allow_t0=preset.allow_t0,
            # *    )
            # *
            # *filled_amount = broker_trade.price * broker_trade.volume
            # *commission = broker_trade.commission
            # *
            # *if broker_trade.order_direction == OrderDirection.Buy:
            # *    delta = cash.volume_his - filled_amount - commission
            # *    cash.volume_his = max(delta, 0)
            # *    cash.volume_today = cash.volume_today + min(delta, 0)
            # *    cash.frozen = max(cash.frozen - filled_amount - commission, 0)
            # *
            # *    symbol_position.volume_today += broker_trade.volume
            # *    symbol_position.lasttrade = broker_trade.price
            # *    symbol_position.cost += filled_amount + commission
            # *
            # *else:
            # *    delta = symbol_position.volume_his - broker_trade.volume
            # *    symbol_position.volume_his = max(delta, 0)
            # *    symbol_position.volume_today = symbol_position.volume_today + min(
            # *        delta, 0
            # *    )
            # *    symbol_position.frozen = max(
            # *        symbol_position.frozen - broker_trade.volume, 0
            # *    )
            # *    symbol_position.lasttrade = broker_trade.price
            # *    symbol_position.cost += commission - filled_amount
            # *    cash.volume_today += filled_amount - commission
            # *self._database.save_many(
            # *    "positions", [cash, symbol_position], session=session
            # *)
            # *self._update_account_info([broker_trade.account_id], session=session)

    def _update_position_buy(self, broker_trade, session=None):
        filled_amount = broker_trade.price * broker_trade.volume
        commission = broker_trade.commission

        item = self._database.positions.find_one(
            {
                "account_id": broker_trade.account_id,
                "symbol": "CNY",
            },
            {"_id": 0},
        )

        cash = vxCashPosition(item)
        delta = cash.volume_his - filled_amount - commission
        cash.volume_his = max(delta, 0)
        cash.volume_today += min(delta, 0)
        self._database.save("positions", cash, session=session)

        preset = vxMarketPreset(broker_trade.symbol)
        # * item = (
        # *     self._database.positions.find_one(
        # *         {"account_id": broker_trade.account_id, "symbol": broker_trade.symbol},
        # *         {"_id": 0},
        # *     )
        # *     or {}
        # * )

        self._database.positions.update_one(
            {"account_id": broker_trade.account_id, "symbol": broker_trade.symbol},
            {
                "$set": {
                    "lasttrade": broker_trade.price,
                },
                "$inc": {
                    "volume_today": broker_trade.volume,
                    "cost": filled_amount + commission,
                },
                "$setOnInsert": {
                    "position_id": str(uuid.uuid4()),
                    "position_side": "Long",
                    "volume_his": 0,
                    "volume": broker_trade.volume,
                    "security_type": preset.security_type.name,
                    "allow_t0": preset.allow_t0,
                    "frozen": 0,
                    "available": broker_trade.volume if preset.allow_t0 else 0,
                    "fnl": -commission,
                    "benchmark_marketvalue": -1,
                    "uplimit_marketvalue": -1,
                    "downlimit_marketvalue": -1,
                },
            },
            upsert=True,
            session=session,
        )

        return

    def _update_position_sell(self, broker_trade, session=None):
        filled_amount = broker_trade.price * broker_trade.volume
        commission = broker_trade.commission
        item = self._database.positions.find_one(
            {"account_id": broker_trade.account_id, "symbol": broker_trade.symbol}
        )
        symbol_position = vxPosition(item)
        delta = symbol_position.volume_his - symbol_position.volume
        symbol_position.volume_his = max(delta, 0)
        symbol_position.volume_today += min(delta, 0)
        symbol_position.lasttrade = broker_trade.price
        symbol_position.cost = symbol_position.cost - filled_amount + commission

        self._database.positions.update_one(
            {"account_id": broker_trade.account_id, "symbol": broker_trade.symbol},
            {"$set": symbol_position.message},
        )

        self._database.positions.update_one(
            {"account_id": broker_trade.account_id, "symbol": "CNY"},
            {
                "$inc": {
                    "volume_today": +filled_amount - commission,
                    "volume": +filled_amount - commission,
                    "available": +filled_amount - commission,
                    "marketvalue": +filled_amount - commission,
                    "cost": +filled_amount - commission,
                }
            },
        )


if __name__ == "__main__":
    publisher = vxZMQPublisher(
        "simtest",
        "tcp://uat.vxquant.com:12307",
        "/Users/libao/src/git/all/vxquantlib/etc/frontend.key",
    )
    subscriber = vxZMQSubscriber(
        "gateway",
        "tcp://uat.vxquant.com:12309",
        "/Users/libao/src/git/all/vxquantlib/examples/backend.key",
    )

    m = vxAccountsManager("mongodb://uat:uat@localhost:27017/uat", "uat", publisher)
    m.create_account("test", if_exists="delete", channel_name="simtest")
    # m.deposit("test", 1000)
    # m.withdraw("test", 1000)
    # logger.info(m.get_account("test"))
    # logger.info(m.get_positions("test"))
    # logger.info(m.get_orders("test"))
    # logger.info(m.get_trades("test"))
    order = m.order_volume("test", "SHSE.600000", 1000, 0)
    # print(order)
    # account = m.get_account("test")

    # cash = m.get_positions("test", "CNY")
    # print(cash)
    # orders = m.get_orders("test")
    # print(orders)
    update_trade = False
    update_order = False

    while True:
        reply_events = subscriber()
        for reply_event in reply_events:
            if reply_event.type == "on_execution_report":
                reply_trade = reply_event.data
                logger.info(
                    f"{reply_trade.exchange_order_id},"
                    f"{reply_trade.volume},"
                    f"{reply_trade.price},"
                )
                m.on_trade_status(1, reply_event)
                update_trade = True

            elif reply_event.type == "on_order_status":
                reply_order = reply_event.data
                logger.info(
                    f"{reply_order.exchange_order_id},"
                    f"{reply_order.filled_volume},"
                    f"{reply_order.status},"
                )

                m.on_order_status(None, reply_event)

                if reply_order.status in (
                    OrderStatus.Filled,
                    OrderStatus.Canceled,
                    OrderStatus.Rejected,
                    OrderStatus.Expired,
                ):
                    update_order = True

        if update_order and update_trade:
            logger.info(f"订单已结束: {reply_order}")
            a = input("wait ...")
            trades = m.get_trades("test", order_id=order.order_id)
            logger.info(f"trades: {trades}")

            a = input("wait ...")
            orders = m.get_orders("test", order_id=order.order_id)
            logger.info(f"orders: {orders}")

            a = input("wait ...")
            positions = m.get_positions("test")
            logger.info(f"positions:{positions}")

            a = input("wait ...")
            account = m.get_account("test")
            logger.info(f"account:{account}")

            break

        vxtime.sleep(1)

    # * while True:
    # *     vxticks = m._update_ticks(
    # *         "SHSE.600000",
    # *         "SZSE.000001",
    # *         "SHSE.000001",
    # *         "SZSE.399001",
    # *         "SZSE.300059",
    # *         "SHSE.000001",
    # *         "SHSE.000688",
    # *         "SHSE.511880",
    # *         "SHSE.510300",
    # *         "SHSE.511990",
    # *         "SHSE.511660",
    # *         "SHSE.204001",
    # *         "SZSE.399001",
    # *         "SZSE.399673",
    # *         "SZSE.159001",
    # *         "SZSE.159919",
    # *         "SZSE.159915",
    # *         "SZSE.159937",
    # *         "SZSE.131810",
    # *     )
    # *     logger.info("=" * 60)
    # *     for symbol, tick in vxticks.items():
    # *         logger.info(
    # *             f"更新时间:{to_timestring(tick.created_dt,'%X.%f')}"
    # *             f" {symbol} : 最新: {tick.lasttrade} 涨幅(%):"
    # *             f" {tick.lasttrade*100/tick.yclose-100:.2f}%"
    # *         )

    # *     vxtime.sleep(3)
