"""交易接口"""

import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union
from vxquant.model.preset import vxMarketPreset
from vxutils import vxtime
from vxquant.model.exchange import (
    vxAccountInfo,
    vxAlgoOrder,
    vxCashPosition,
    vxOrder,
    vxPosition,
    vxTick,
    vxTrade,
)
from vxquant.model.contants import (
    OrderDirection,
    OrderOffset,
    OrderStatus,
    OrderType,
    SecType,
)


class vxTdAPIBase(ABC):
    """交易接口类"""

    def __init__(self):
        self._cache = {}
        self._cached_at = 0

    @abstractmethod
    def get_ticks(self, *symbols) -> Dict[str, vxTick]:
        """获取最新的ticks 数据

        Returns:
            Dict[str,vxTick] -- 返回最新的tick数据
        """

    def current(self, *symbols: List[str]) -> Dict[str, vxTick]:
        """实时行情信息

        Arguments:
            symbols {List[str]} -- 证券交易代码
        """
        if not symbols:
            raise ValueError("symbols must not null.")

        if isinstance(symbols[0], list):
            symbols = symbols[0]

        symbols = list(symbols)

        now = vxtime.now()
        if now > (self._cached_at + 3):
            symbols.extend(self._cache.keys())
            self._cache = {}
            self._cached_at = now

        target_symbols = set(symbols) - set(self._cache.keys())
        vxticks = self.get_ticks(*target_symbols)
        self._cache.update(vxticks)

        return {
            symbol: self._cache[symbol] for symbol in symbols if symbol in self._cache
        }

    @abstractmethod
    def get_account(self) -> vxAccountInfo:
        """获取账户基本信息"""

    @abstractmethod
    def get_positions(
        self, symbol: str = None
    ) -> Dict[str, Union[vxCashPosition, vxPosition]]:
        """获取持仓信息

        Keyword Arguments:
            symbol {str} -- 对应的持仓信息 (default: {None})

        Returns:
            Dict[str, Union[vxCashPosition,vxPosition]] -- 返回持仓列表
        """

    @abstractmethod
    def order_batch(self, *vxorders: List[vxOrder]) -> List[vxOrder]:
        """提交委托订单

        Arguments:
            vxorders {List[vxOrder]} -- 待提交的委托订单
        """

    def order_volume(
        self, symbol: str, volume: int, price: Optional[float] = 0
    ) -> vxOrder:
        """下单

        Arguments:
            account_id {str} -- _description_
            symbol {str} -- _description_
            volume {int} -- _description_
            price {Optional[float]} -- _description_ (default: {None})

        Returns:
            vxorder {vxOrder} -- 下单委托订单号
        """
        if volume == 0:
            raise ValueError("volume can't be 0.")

        if (
            not price
            and vxMarketPreset(symbol).security_type == SecType.BOND_CONVERTIBLE
        ):
            ticks = self.current(symbol)
            price = ticks[symbol].ask1_p if volume > 0 else ticks[symbol].bid1_p

        vxorder = vxOrder(
            symbol=symbol,
            volume=abs(volume),
            price=price,
            order_offset=OrderOffset.Open if volume > 0 else OrderOffset.Close,
            order_direction=OrderDirection.Buy if volume > 0 else OrderDirection.Sell,
            order_type=OrderType.Market if price <= 0 else OrderType.Limit,
            status=OrderStatus.PendingNew,
        )

        ret_orders = self.order_batch(vxorder)
        return ret_orders[0]

    @abstractmethod
    def get_orders(self) -> List[vxOrder]:
        """获取当日委托订单列表

        Returns:
            List[vxOrder] -- 当日委托订单列表
        """

    @abstractmethod
    def get_execution_reports(self) -> List[vxTrade]:
        """获取当日成交回报信息

        Returns:
            List[vxTrade] -- 当日成交回报列表
        """

    @abstractmethod
    def order_cancel(self, *orders: List[vxOrder]) -> None:
        """撤单

        Arguments:
            orders {List[vxOrder]} -- 待撤销订单
        """
