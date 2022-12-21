# endcoding = utf-8
"""
author : vex1023
email :  vex1023@qq.com
各类型的decorator
"""


import signal
import time

from typing import Any
from collections import defaultdict
from multiprocessing.pool import ThreadPool
from multiprocessing import Lock
from functools import wraps


__all__ = [
    "retry",
    "timeit",
    "singleton",
    "threads",
    "lazy_property",
    "timeout",
    "storage",
]


###################################
# 错误重试方法实现
# @retry(tries, CatchExceptions=(Exception,), delay=0.01, backoff=2)
###################################


def retry(tries, CatchExceptions=(Exception,), delay=0.01, backoff=2):
    """
    错误重试的修饰器
    :param tries: 重试次数
    :param CatchExceptions: 需要重试的exception列表
    :param delay: 重试前等待
    :param backoff: 重试n次后，需要等待delay * n * backoff
    :return:
    @retry(5,ValueError)
    def test():
        raise ValueError
    """
    if backoff <= 1:
        raise ValueError("backoff must be greater than 1")

    if tries < 0:
        raise ValueError("tries must be 0 or greater")

    if delay <= 0:
        raise ValueError("delay must be greater than 0")

    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mdelay = delay
            retException = None
            for mtries in range(tries):
                try:
                    return f(*args, **kwargs)
                except CatchExceptions as ex:
                    print(
                        f"function {f.__name__}({args}, {kwargs}) try {mtries} times"
                        f" error: {str(ex)}\n"
                    )
                    print("Retrying in {mdelay:.4f} seconds...")

                    retException = ex
                    time.sleep(mdelay)
                    mdelay *= backoff
            raise retException

        return f_retry

    return deco_retry


###################################
# 计算运行消耗时间
# @timeit
###################################


def timeit(func):
    """
    计算运行消耗时间
    @timeit
    def test():
        time.sleep(1)
    """

    def wapper(*args, **kwargs):
        _start = time.time()
        retval = func(*args, **kwargs)
        _end = time.time()
        print(f"function {func.__name__}() used : {(_end - _start):.6f)}s")
        return retval

    return wapper


###################################
# Singleton 实现
# @singleton
###################################


class singleton(object):
    """
    单例
    example::

        @singleton
        class YourClass(object):
            def __init__(self, *args, **kwargs):
                pass
    """

    def __init__(self, cls):
        self._instance = None
        self._cls = cls
        self._lock = Lock()

    def __call__(self, *args, **kwargs):
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self._cls(*args, **kwargs)
        return self._instance


###################################
# 异步多线程
# @thread(n,timeout=None)
###################################


class asyncResult:
    """异步返回结果"""

    def __init__(self, future, timeout_time):
        self._future = future
        self._timeout = timeout_time
        self._result = None

    def __getattr__(self, name):
        return getattr(self.result, name)

    @property
    def result(self):
        """获取异步返回结果

        Returns:
            返回计算结果
        """
        if self._result is None:
            self._result = self._future.get(self._timeout)
        return self._result


def threads(n, time_limit=5):
    """多线程装饰器
    @thread(n,timeout=None)
    def handler(*args, **kwargs):
        pass

    rets = map(handler , iterable)
    for ret in rets:
        print(ret.get())
    """

    def decorator(f):
        pool = ThreadPool(n)

        @wraps(f)
        def warpped(*args, **kwargs):
            return asyncResult(
                pool.apply_async(func=f, args=args, kwds=kwargs), time_limit
            )

        return warpped

    return decorator


###################################
# 限制超时时间
# @timeout(seconds, error_message='Function call timed out')
###################################


def timeout(seconds, error_message="Function call timed out"):
    """超时限制装饰器

    Arguments:
        seconds -- 超时秒数

    Keyword Arguments:
        error_message -- 超时返回信息 (default: {"Function call timed out"})
    """

    def decorated(func):
        def _handle_timeout(signum, frame):
            message = f"{error_message} after {seconds} seconds,{signum},{frame}"
            print(message)
            raise TimeoutError(message)

        @wraps(func)
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    return decorated


###################################
# 类似@property的功能，但只执行一次
# @lazy_property
###################################


class lazy_property(object):
    """类似@property的功能，但只执行一次"""

    def __init__(self, deferred):
        self._deferred = deferred
        self.__doc__ = deferred.__doc__

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = self._deferred(obj)
        setattr(obj, self._deferred.__name__, value)
        return value


###################################
# 存储器 ---- 用于收集，整理各种元素
# @storage(type_name, element_name)
#
###################################


class storage:
    """采集器，负责收集零散在各处的元素

    storage("hello", "jack","hi")
    storage("hello", "vex1023","hi")
    ------------------------------------
    @storage("parser","sina"):
    def sina_parser(content):
        print("sina_parser",content)

    @storage("parser","qq"):
    def qq_parser(content):
        print("qq_parser",content)

    parser = storage.get("parser",'sina')
    parser()

    """

    __elements = defaultdict(dict)

    def __init__(self, type_name: str, element_name: str, element: Any = None) -> None:
        self._type_name = type_name
        self._element_name = element_name
        self.__call__(element)

    def __call__(self, element: Any) -> Any:
        self.__class__.__elements[self._type_name][self._element_name] = element
        return element

    @classmethod
    def get(cls, type_name: str, element_name: str) -> Any:
        return cls.__elements[type_name][element_name]

