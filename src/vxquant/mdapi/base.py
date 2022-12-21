"""行情接口基础类"""

import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Optional
from vxquant.model.exchange import vxTick


class vxMdAPI:
    def __init__(self, context) -> None:
        pass

    def current(self, *symbols: List[str]) -> Dict[str, vxTick]:
        """实时行情数据

        Returns:
            Dict[str, vxTick] -- _description_
        """

    def calendar(
        self, start_date: str, end_date: str, exchange_id: str = "SHSE"
    ) -> List[datetime]:
        """交易日历

        Arguments:
            start_date {str} -- 开始日期(含)
            end_date {str} -- 结束日期(含)
            exchange_id {str} -- 交易所

        Returns:
            List[datetime] -- 开始日期至结束日期之间的时间序列
        """

    def instruments(self, *args, **kwargs) -> pd.DataFrame:
        """交易标的"""

    def features(
        self, symbols: List, start_dt: str, end_dt: str, *features
    ) -> pd.DataFrame:
        """因子

        Returns:
            pd.DataFrame -- index: [日期、交易标的] columns: [feature ...]
        """
