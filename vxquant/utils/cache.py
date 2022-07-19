# encoding = utf-8
"""
缓存，减少网络下载的次数
"""

import time
from datetime import datetime, timedelta
from multiprocessing import Lock

import hashlib
from functools import wraps

__all__ = [
    "cache",
    "Timer",
    "EndlessTimer",
    "TTLTimer",
    "MemoryCacheStorage",
    "MongoDBCacheStorage",
    "CacheExpiredException",
    "NotCacheException",
]


class CacheExpiredException(Exception):
    """超时错误"""


class NotCacheException(Exception):
    """无缓存错误"""


class MemoryCacheStorage:
    """内存存储器"""

    def __init__(self):
        self._data = {}
        self._lock = Lock()

    def set(self, key, value, expire_at=-1):
        """存储缓存"""
        with self._lock:
            now = time.time()
            if expire_at > now or expire_at < 0:
                self._data[key] = {"expire_at": expire_at, "value": value}

    def get(self, key):
        """获取缓存"""
        with self._lock:
            data = self._data.get(key, None)
            if data:
                now = time.time()
                if data["expire_at"] < 0 or now < data["expire_at"]:
                    return data["value"]

                self._data.pop(key)
                raise CacheExpiredException(f"now: {now}, data: {data}")

            raise NotCacheException(f"key: {key}, data: {data}")

    def flush(self):
        """刷新所有数据"""
        with self._lock:
            del self._data
            self._data = {}


class MongoDBCacheStorage:
    """MongoDB缓存存储器"""

    def __init__(self, db_collections):
        self._data = db_collections
        self._lock = Lock()

    def get(self, key):
        """获取缓存"""
        with self._lock:
            data = self._data.find_one({"_id": key})
            if data:
                now = time.time()
                if data["expire_at"] < 0 or now < data["expire_at"]:
                    return data["value"]
                self._data.delete_one({"_id": key})
                raise CacheExpiredException(f"now: {now}, data: {data}")

            raise NotCacheException(f"key: {key}, data: {data}")

    def set(self, key, value, expire_at=-1):
        """存储缓存"""
        with self._lock:
            now = time.time()
            if expire_at > now or expire_at < 0:
                self._data.insert_one(
                    {"_id": key, "value": value, "expire_at": expire_at}
                )

    def flush(self):
        """清楚所有数据"""
        with self._lock:
            self._data.delete_many({})


# 定义计时器
class Timer:
    """定义计时器"""

    def expire_at(self):
        """超时时间"""
        return -1


# 永不超时的计时器
class EndlessTimer(Timer):
    """永不超时的计时器"""

    def expire_at(self):
        """超时时间"""
        return -1


# 按照时间间隔确定的计时器
class TTLTimer(Timer):
    """按照时间间隔确定的计时器"""

    def __init__(self, seconds=0, minutes=0, hours=0, days=0, weeks=0):
        self._ttl = timedelta(
            seconds=seconds, minutes=minutes, hours=hours, days=days, weeks=weeks
        )

    def expire_at(self):
        """超时时间"""
        return (datetime.now() + self._ttl).timestamp()


# 缓存修饰器
class cache:
    """缓存修饰器"""

    storage = MemoryCacheStorage()

    def __init__(self, timer=EndlessTimer()):
        self._timer = timer
        self._lock = Lock()

    @classmethod
    def set_storage(cls, storage):
        """设置缓存存储器"""
        cls.storage = storage

    def __call__(self, func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            with self._lock:
                try:
                    cache_string = f"{func.__name__}_{args}_{kwargs}"
                    cache_key = hashlib.md5(cache_string.encode("utf-8")).hexdigest()
                    ret_val = cache.storage.get(cache_key)
                except (NotCacheException, CacheExpiredException):
                    ret_val = func(*args, **kwargs)
                    expire_at = self._timer.expire_at()
                    cache.storage.set(cache_key, ret_val, expire_at)
            return ret_val

        return wrapped

    @classmethod
    def flush(cls):
        """刷新所有数据"""
        cls.storage.flush()
