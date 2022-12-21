"""掘金量化tick行情数据"""


from gm import api as gm_api
from vxquant.model.tools.gmData import gmTickConvter

_BATCH_SIZE = 100


class vxGMHQ:
    def __init__(self, token=None):
        if token:
            gm_api.set_token(token)

    def __call__(self, *symbols) -> dict:
        allticks = []
        for i in range(0, len(symbols), _BATCH_SIZE):
            gmticks = gm_api.current(symbols=symbols[i: i + _BATCH_SIZE])
            allticks.extend(gmticks)

        return dict(map(lambda gmtick: gmTickConvter(gmtick, key="symbol"), gmticks))
