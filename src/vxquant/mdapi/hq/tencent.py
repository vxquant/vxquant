"""实时行情获取"""

import re
import itertools
import requests
from typing import Dict, List
from functools import reduce
from vxutils import logger, vxtime
from vxquant.model.exchange import vxTick


_TENCENT_HQ_URL = "https://qt.gtimg.cn/q=%s&timestamp=%s"
_HEADERS = {
    "Accept-Encoding": "gzip, deflate, sdch",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/54.0.2840.100 "
        "Safari/537.36"
    ),
}


def _to_tencent_symbol(symbol: str) -> str:
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


class vxTencentHQ:
    def __init__(self, worker_cnt=2):
        self._grep_stock_code = re.compile(r"(?<=_)\w+")
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        resq = self._session.get("https://stockapp.finance.qq.com/mstats/#", timeout=1)
        resq.raise_for_status()
        logger.debug(f"网络连通成功{resq.status_code}...")

    def __call__(self, *symbols) -> Dict[str, vxTick]:
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
        ret_ticks = {}
        reduce(_update_dict, data, ret_ticks)
        return ret_ticks

    def fetch_tencent_ticks(self, symbols: List[str]) -> List[str]:
        """抓取tick数据

        Arguments:
            symbols {List} -- 证券代码s

        Returns:
            Dict[str, vxTick] -- _description_
        """

        url = _TENCENT_HQ_URL % (
            ",".join(map(_to_tencent_symbol, symbols)),
            vxtime.now(),
        )
        try:
            resq = self._session.get(url, timeout=0.5)
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


if __name__ == "__main__":
    hq = vxTencentHQ()
    print(hq("SHSE.600000", "SZSE.000001", "SZSE.300059"))
