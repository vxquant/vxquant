"""掘金量化交易接口"""


from gm import api as gmapi

from functools import lru_cache
from typing import Dict, List, Union
from vxutils import vxtime, logger
from vxutils.convertors import to_timestring
from vxquant.model.exchange import (
    vxCashPosition,
    vxTick,
    vxAccountInfo,
    vxPosition,
    vxOrder,
    vxTrade,
)
from vxquant.model.contants import AccountType
from vxquant.model.tools.gmData import (
    gmTickConvter,
    gmCashPositionConvter,
    gmPositionConvter,
    gmAccountinfoConvter,
    gmOrderConvter,
    gmTradeConvter,
)
from .base import vxTdAPIBase

_BATCH_SIZE = 100


class gmTdAPI(vxTdAPIBase):
    """掘金量化交易接口"""

    def __init__(
        self, gmcontext, account_type: AccountType = AccountType.Normal
    ) -> None:
        super().__init__()
        self._context = gmcontext
        self._account_type = account_type

    def get_ticks(self, *symbols: List) -> Dict[str, vxTick]:
        allticks = []
        for i in range(0, len(symbols), _BATCH_SIZE):
            gmticks = gmapi.current(symbols=symbols[i : i + _BATCH_SIZE])
            allticks.extend(gmticks)

        return dict(map(lambda gmtick: gmTickConvter(gmtick, key="symbol"), allticks))

    def get_account(self) -> vxAccountInfo:
        gmcash = self._context.account().cash
        return gmAccountinfoConvter(gmcash)

    def get_positions(
        self, symbol: str = None
    ) -> Dict[str, Union[vxCashPosition, vxPosition]]:
        if symbol:
            gmposition = self._context.account().position(symbol)
            return {symbol: gmPositionConvter(gmposition)} if gmposition else None

        gmcash = self._context.account().cash
        vxpositions = {"CNY": gmCashPositionConvter(gmcash)}
        gmpositions = self._context.account().positions()
        vxpositions.update(
            map(
                lambda gmposition: gmPositionConvter(gmposition, key="symbol"),
                gmpositions,
            )
        )
        return vxpositions

    def get_orders(self) -> Dict[str, vxOrder]:
        gmorders = gmapi.get_orders()
        return dict(
            map(
                lambda gmorder: gmOrderConvter(gmorder, key="exchange_order_id"),
                gmorders,
            )
        )

    def get_execution_reports(self) -> Dict[str, vxTrade]:
        gmtrades = gmapi.get_execution_reports()
        return dict(
            map(lambda gmtrade: gmTradeConvter(gmtrade, key="trade_id"), gmtrades)
        )

    @lru_cache(100)
    def _get_borrowable_instruments(self, _) -> List[str]:
        if self._account_type != AccountType.Credit:
            return []

        borrowable_instruments = gmapi.credit_get_borrowable_instruments(gmapi.Po)
        return [
            ins["symbol"]
            for ins in borrowable_instruments
            if ins["margin_rate_for_cash"] > 0
        ]

    def get_borrowable_instruments(self) -> List[str]:
        """可融标的证券

        Returns:
            List[str] -- 可融标的证券
        """
        if self._account_type != AccountType.Credit:
            return []
        return self._get_borrowable_instruments(to_timestring(vxtime.now(), "%Y-%m-%d"))

    def order_batch(self, *vxorders: List[vxOrder]) -> List[vxOrder]:
        """提交委托订单

        Arguments:
            vxorders {List[vxOrder]} -- 待提交的委托订单
        """
        orders = []
        borrowable_instruments = self.get_borrowable_instruments()
        for vxorder in vxorders:
            if (
                self._account_type == AccountType.Credit
                and vxorder.symbol in borrowable_instruments
            ):
                order_business = gmapi.OrderBusiness_CREDIT_BOM
            else:
                order_business = gmapi.OrderBusiness_NORMAL

            gmorder = {
                "symbol": vxorder.symbol,
                "volume": vxorder.volume,
                "price": vxorder.price,
                "side": vxorder.order_direction.value,
                "order_type": vxorder.order_type.value,
                "position_effect": vxorder.order_offset.value,
                "order_business": order_business,
                "position_src": gmapi.PositionSrc_L1,
            }
            orders.append(gmorder)
            logger.debug(f"gmorder={gmorder}")
        gmorders = gmapi.order_batch(orders)
        # for gmorder in gmorders:
        #    logger.debug(f"gmorder={gmorder}")
        return list(map(gmOrderConvter, gmorders))

    def order_cancel(self, *vxorders: List[vxOrder]) -> None:
        wait_cancel_orders = [
            {"cl_ord_id": vxorder.exchange_order_id, "account_id": ""}
            for vxorder in vxorders
            if vxorder.exchange_order_id
        ]
        return gmapi.order_cancel(wait_cancel_orders)
