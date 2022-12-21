"""gmtrade 掘金量化仿真交易接口"""


from gmtrade import api as gmtrade_api
from vxquant.tdapi.base import vxTdAPI
from vxquant.model.exchange import (
    vxAccountInfo,
    vxOrder,
    vxCashPosition,
    vxPosition,
    vxTrade,
    vxTick,
)

from vxquant.model.tools.gmData import (
    gmAccountinfoConvter,
    gmCashPositionConvter,
    gmOrderConvter,
    gmPositionConvter,
    gmTickConvter,
    gmTradeConvter,
)


class gmTradeTdAPI(vxTdAPI):
    """gmtrade 掘金量化仿真交易接口"""

    def __init__(self, token: str, account_id: str = "", endpoint: str = None) -> None:
        super().__init__()

        self._token = token
        self._account_id = account_id
        self._endpoint = endpoint or "api.myquant.cn:9000"

        gmtrade_api.set_token(self._token)
        gmtrade_api.set_endpoint(endpoint)
        self._account = gmtrade_api.account(account_id=self._account_id)
        gmtrade_api.login(self._account)

    def get_account(self) -> vxAccountInfo:
        cash = gmtrade_api.get_cash()
        return gmAccountinfoConvter(cash)

    def get_positions(
        self, symbol: str = None
    ) -> Dict[str, Union[vxCashPosition, vxPosition]]:
        return super().get_positions(symbol)

    def get_orders(self) -> List[vxOrder]:
        return super().get_orders()

    def get_execution_reports(self) -> List[vxTrade]:
        return super().get_execution_reports()

    def get_ticks(self, *symbols) -> Dict[str, vxTick]:
        return super().get_ticks(*symbols)
