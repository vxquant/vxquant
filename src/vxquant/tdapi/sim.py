"""模拟交易"""

import re
import itertools
from abc import abstractmethod
from multiprocessing.dummy import Pool
from typing import Dict, List, Optional, Union
import uuid
import requests
from vxsched import vxContext, vxscheduler
from vxutils import vxtime, logger
from vxquant.model.exchange import (
    vxAccountInfo,
    vxAlgoOrder,
    vxCashPosition,
    vxOrder,
    vxPosition,
    vxTick,
    vxTrade,
)
from functools import reduce
from vxquant.model.contants import OrderDirection, OrderOffset, OrderStatus, OrderType
from vxquant.tdapi.base import vxTdAPIBase

_TENCENT_HQ_URL = "http://qt.gtimg.cn/q=%s&timestamp=%s"
_HEADERS = {
    "Accept-Encoding": "gzip, deflate, sdch",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/54.0.2840.100 "
        "Safari/537.36"
    ),
}


def to_tencent_symbol(symbol: str) -> str:
    """转换成tencent格式的证券代码"""
    exchange, code = symbol.split(".")
    if exchange == "SHSE":
        return f"sh{code}"
    elif exchange == "SZSE":
        return f"sz{code}"
    else:
        raise ValueError(f"{symbol} 格式不正确.")


def _update_dict(source, target):
    source.update(target)
    return source


class vxSIMTdAPI(vxTdAPIBase):
    """交易接口类"""

    def __init__(self, context: vxContext = None):
        super().__init__()
        self._context = context or vxContext()
        self._session = requests.Session()
        self._grep_stock_code = re.compile(r"(?<=_)\w+")
        self._pool = Pool(5)
        self._session.headers.update(_HEADERS)
        resq = self._session.get("https://stockapp.finance.qq.com/mstats/#", timeout=1)
        resq.raise_for_status()
        logger.info(f"网络连通成功{resq.status_code}...")

    def get_ticks(self, *symbols) -> Dict[str, vxTick]:
        """获取最新的ticks 数据

        Returns:
            Dict[str,vxTick] -- 返回最新的tick数据
        """
        if isinstance(symbols[0], list):
            symbols = symbols[0]

        # print(symbols)
        stock_lines = map(
            self.fetch_tencent_ticks,
            [symbols[i:800] for i in range(0, len(symbols), 800)],
        )
        data = map(self.parser, itertools.chain(*stock_lines))
        return reduce(_update_dict, data, self._cache)

    def fetch_tencent_ticks(self, symbols: List[str]) -> List[str]:
        """抓取tick数据

        Arguments:
            symbols {List} -- 证券代码s

        Returns:
            Dict[str, vxTick] -- _description_
        """

        url = _TENCENT_HQ_URL % (
            ",".join(map(to_tencent_symbol, symbols)),
            vxtime.now(),
        )
        try:
            resq = self._session.get(url)
            resq.raise_for_status()
            text = resq.text.strip()
            return text.split(";")[:-1]

        except requests.exceptions.HTTPError as e:
            logger.error(f"获取{url}数据出错: {e}.")
            return {}

    def parser(self, stock_line: str) -> Dict[str, vxTick]:
        """解析程序

        Arguments:
            stock_line {str} -- 股票信息行

        Returns:
            Dict[str, vxTick] -- vxticks data
        """

        stock = stock_line.split("~")
        if len(stock) <= 49:
            logger.warning(f"skip stock line: {len(stock_line)}")
            return {}

        tencent_symbol = self._grep_stock_code.search(stock[0]).group()
        if tencent_symbol[:2].lower() == "sh":
            symbol = f"SHSE.{tencent_symbol[2:]}"
        elif tencent_symbol[:2].lower() == "sz":
            symbol = f"SZSE.{tencent_symbol[2:]}"
        else:
            logger.warniing(
                f"wrong format tencent_symbol{tencent_symbol} ==== {stock[0]}"
            )
            return {}

        return {
            symbol: vxTick(
                symbol=symbol,
                open=stock[5],
                high=stock[33],
                low=stock[34],
                lasttrade=stock[3],
                yclose=float(stock[3]) - float(stock[31]),
                volume=int(stock[36]) * 100,
                amount=float(stock[37]) * 10000,
                bid1_v=int(stock[10]) * 100,
                bid1_p=stock[9],
                bid2_v=int(stock[12]) * 100,
                bid2_p=stock[11],
                bid3_v=int(stock[14]) * 100,
                bid3_p=stock[13],
                bid4_v=int(stock[16]) * 100,
                bid4_p=stock[15],
                bid5_v=int(stock[18]) * 100,
                bid5_p=stock[17],
                ask1_v=int(stock[20]) * 100,
                ask1_p=stock[19],
                ask2_v=int(stock[22]) * 100,
                ask2_p=stock[21],
                ask3_v=int(stock[24]) * 100,
                ask3_p=stock[23],
                ask4_v=int(stock[26]) * 100,
                ask4_p=stock[25],
                ask5_v=int(stock[28]) * 100,
                ask5_p=stock[27],
                interest=0,
                status="NORMAL",
                created_dt=stock[30],
                updated_dt=stock[30],
            )
        }

    def current(self, *symbols: List[str]) -> Dict[str, vxTick]:
        """实时行情信息

        Arguments:
            symbols {List[str]} -- 证券交易代码
        """
        if not symbols:
            raise ValueError("symbols must not null.")

        if isinstance(symbols[0], list):
            symbols = symbols[0]
        require_symbols = symbols

        now = vxtime.now()
        if now > (self._cached_at + 3):
            require_symbols.extend(self._cache.keys())

            self._cache = {}
            self._cached_at = now

        target_symbols = set(require_symbols) - set(self._cache.keys())
        self.get_ticks(*target_symbols)

        return {
            symbol: self._cache[symbol] for symbol in symbols if symbol in self._cache
        }

    def get_account(self) -> vxAccountInfo:
        """获取账户基本信息"""
        return None

    def get_positions(
        self, symbol: str = None
    ) -> Dict[str, Union[vxCashPosition, vxPosition]]:
        """获取持仓信息

        Keyword Arguments:
            symbol {str} -- 对应的持仓信息 (default: {None})

        Returns:
            Dict[str, Union[vxCashPosition,vxPosition]] -- 返回持仓列表
        """
        return {}

    def order_batch(self, *vxorders: List[vxOrder]) -> List[vxOrder]:
        """提交委托订单

        Arguments:
            vxorders {List[vxOrder]} -- 待提交的委托订单
        """
        if isinstance(vxorders[0], list):
            vxorders = vxorders[0]

        ret_orders = []
        for vxorder in vxorders:
            broker_order = vxOrder(**vxorder)
            broker_order.exchange_order_id = str(uuid.uuid4())
            ret_orders.append(broker_order)
            self.context.sim_orderbooks[broker_order.exchange_order_id] = broker_order

        return ret_orders

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

    def get_orders(self) -> List[vxOrder]:
        """获取当日委托订单列表

        Returns:
            List[vxOrder] -- 当日委托订单列表
        """
        return {}

    def get_execution_reports(self) -> List[vxTrade]:
        """获取当日成交回报信息

        Returns:
            List[vxTrade] -- 当日成交回报列表
        """
        return {}

    def order_cancel(self, *orders: List[vxOrder]) -> None:
        """撤单

        Arguments:
            orders {List[vxOrder]} -- 待撤销订单
        """


if __name__ == "__main__":
    tdapi = vxSIMTdAPI()
    start = vxtime.now()
    ticks = tdapi.current(["SHSE.600000", "SZSE.000001"] * 1000)
    print(f"耗时: {vxtime.now() -start}")

    # print(ticks["SHSE.600000"])
    ticks = tdapi.current(["SHSE.600036", "SZSE.000001", "SHSE.113591"] * 1000)
    # print(ticks["SHSE.600036"])
    print(f"耗时: {vxtime.now() -start}")
    print(ticks["SHSE.113591"])
