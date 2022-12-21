"""baostock获取行情"""
from vxutils import logger

try:
    import baostock as bs
except ImportError:
    logger.warning("未安装第三方库: baostock,请通过: pip install baostock 安装")
    bs = None
