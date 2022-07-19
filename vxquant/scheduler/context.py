"""引擎上下文context类"""


import os
from collections.abc import Mapping
from contextvars import copy_context, ContextVar

try:
    import simplejson as json
except ImportError:
    import json

from vxquant.utils.convertors import to_json

__all__ = ["vxContext"]


class vxContext(Mapping):
    """引擎上下文context类"""

    def __init__(self, *args, **kwargs):
        if args:
            kwargs.update(args[0])

        self.__dict__["_vars"] = {}
        ctx = copy_context()
        for var in ctx.keys():
            self._vars[var.name] = var

        for k, v in kwargs.items():
            var = ContextVar(k)
            var.set(v)
            self._vars[k] = var

    def __getattr__(self, name):
        if name in self._vars:
            var = self._vars[name]
            return var.get()
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name not in self._vars:
            self._vars[name] = ContextVar(name)
        self._vars[name].set(value)

    def __getitem__(self, name):
        if name in self._vars:
            return self._vars[name].get()
        raise AttributeError(name)

    def __setitem__(self, name, value):
        if name not in self._vars:
            self._vars[name] = ContextVar(name)
        self._vars[name].set(value)

    def __str__(self) -> str:
        var_json = to_json({k: v.get() for k, v in self._vars.items()})
        return f"< {self.__class__.__name__} (id-{id(self)}): {var_json} >"

    __repr__ = __str__

    def __len__(self) -> int:
        return len(self._vars)

    def __iter__(self):
        return iter(self._vars)

    def keys(self):
        """keys列表"""
        return self._vars.keys()

    def values(self):
        return [var.get() for var in self._vars.values()]

    def items(self):
        return [(key, var.get()) for key, var in self._vars.items()]

    def update(self, **kwargs):
        """更新"""
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def load(cls, json_file):
        """加载context数据"""
        if not os.path.exists(json_file):
            raise ValueError(f"file {json_file} not exists.")

        with open(json_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        # instance = cls(**data)
        return cls(**data)

    @classmethod
    def save(cls, context, json_file):
        """保存数据"""
        data = {attr: var.get() for attr, var in context.items()}
        with open(json_file, "w", encoding="utf-8") as fp:
            json.dump(data, fp)

    def reload(self):
        """reload context内容"""
        ctx = copy_context()
        for var in ctx.keys():
            self._vars[var.name] = var
