"""行情数据接口"""


from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
import pandas as pd
from vxsched import vxContext
from vxutils import vxtime, logger
from vxutils.database.sqlite import vxSqliteDB

from ..model.exchange import vxTick

TICK_TIMEDELTA = 3


class vxMdAPI(ABC):
    """行情数据接口"""

    def __init__(
        self,
        context: Optional[vxContext] = None,
        db: Optional[vxSqliteDB] = None,
        **kwargs,
    ):
        self._cachedb = db or vxSqliteDB()
        self._cachedb.create_table("current", ["symbol"], vxTick)
        self._context = context or vxContext()

    @abstractmethod
    def _hq_api(self, *symbols: List) -> List[vxTick]:
        """实时行情接口

        Keyword Arguments:
            symbols {List} -- 获取实时行情的股票代码

        Returns:
            List[vxTick] -- _description_
        """

    def current(self, *symbols: List) -> Dict[str, vxTick]:
        """_summary_

        Keyword Arguments:
            symbols {List} -- 获取实时行情的股票代码

        Returns:
            Dict[str, vxTick] -- 返回 {"symbol1": vxtick1,"symbol2": vxtick2 ...}
        """
        if symbols is None:
            raise ValueError("symbols 不能为空")

        if isinstance(symbols[0], list):
            symbols = symbols[0]

        now = vxtime.now()
        cached_symbols = set(
            self._cachedb.current.distinct(
                "symbol",
                f"created_dt > {now-TICK_TIMEDELTA}",
            )
        )
        target_symbols = set(symbols) - cached_symbols

        if target_symbols:
            ticks = self._hq_api(*target_symbols)
            self._cachedb.current.savemany(*ticks)

        return {
            tick.symbol: tick
            for tick in self._cachedb.current.query(f"symbol in [{','.join(symbols)}]")
        }

    @abstractmethod
    def calendar(self, start_date: str = None, end_date: str = None) -> List:
        """交易日历

        Keyword Arguments:
            start_date {str} -- 开始日期 (default: {None})
            end_date {str} -- 结束日期 (default: {None})

        Returns:
            List -- 交易日历
        """

    @abstractmethod
    def features(
        self, symbols: List, fields: List, start_date: str = "", end_date: str = ""
    ) -> pd.DataFrame:
        """_summary_

        Arguments:
            symbols {List} -- _description_
            fields {List} -- _description_

        Keyword Arguments:
            start_date {str} -- _description_ (default: {''})
            end_date {str} -- _description_ (default: {""})

        Returns:
            pd.DataFrame -- _description_
        """
