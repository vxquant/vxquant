# encoding=utf-8
"""
author : vex1023
email :  vex1023@qq.com

@debug_log
def func(*args, **kwargs):
    pass
    
"""


import time
import inspect
from functools import wraps
from typing import Any


def debug_log(func) -> Any:
    from vxutils import vxLogging

    # 创建日志器
    _logger = vxLogging.getLogger("__DEBUG__")
    # 获取函数参数信息
    sig = inspect.signature(func)

    @wraps(func)
    def debug_func(*args, **kwargs):
        # 计算函数的参数
        ba = sig.bind(*args, **kwargs)
        ba.apply_defaults()

        # 记录函数开始执行时间
        start = time.perf_counter()

        try:
            # 执行函数，并记录返回值
            ret = func(*args, **kwargs)
        except Exception as e:
            # 如果函数执行出错，记录异常信息
            ret = e
            raise
        finally:
            # 记录函数执行结束时间
            end = time.perf_counter()

            # 输出函数调用信息
            if isinstance(ret, Exception):
                _logger.error(
                    f"func:{func.__name__}({ba.arguments}) 调用出错: {ret}", exc_info=True
                )
            else:
                _logger.warning(
                    f"func:{func.__name__}({ba.arguments}) 耗时: {(end-start)*1000:.2f}ms"
                    f" 返回值: {ret}"
                )

            return ret

    return debug_func
