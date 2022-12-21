"""引擎上下文context类"""


from collections.abc import MutableMapping, Mapping, Sequence
from pathlib import Path
from typing import Dict, Any, List
from functools import singledispatch
from vxutils import to_json, vxDict, vxJSONEncoder

try:
    import simplejson as json
except ImportError:
    import json

__all__ = ["vxContext"]


class vxContext(MutableMapping):
    """引擎上下文context类"""

    _default_config: Dict[str, Any] = {}

    def __init__(self, default_config: Dict = None, **kwargs):
        default_config = default_config or {}
        default_config.update(kwargs)
        for k, v in default_config.items():
            self.__dict__[k] = _to_vxcontext(v)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __delitem__(self, key):
        self.__dict__.__delitem__(key)

    def __setattr__(self, attr: str, value: Any) -> Any:
        self.__dict__[attr] = _to_vxcontext(value)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __eq__(self, __o: Mapping) -> bool:
        if len(self) != len(__o):
            return False

        try:
            return all(v == __o[k] for k, v in self.items())
        except Exception:
            return False

    def __hash__(self):
        return hash(self.__str__())

    def __setstate__(self, state) -> None:
        self.__init__(**state)

    def __getstate__(self) -> dict:
        return self.__dict__

    def __str__(self):
        try:
            return f"< {self.__class__.__name__}(id-{id(self)}) : {to_json(self)} >"
        except (TypeError, KeyError):
            return f"< {self.__class__.__name__}(id-{id(self)}) : {self.__dict__} >"

    __repr__ = __str__

    def __iter__(self):
        yield from self.__dict__

    def keys(self):
        yield from self.__dict__

    def values(self):
        yield from self.__dict__.values()

    def update(self, config: Dict = None, **kwargs):
        """批量更新字典"""
        config = config or kwargs
        for k, v in config.items():
            self.__dict__[k] = _to_vxcontext(v)

    def items(self):
        """(key,value) pairs"""
        yield from self.__dict__.items()

    def pop(self, key: str, default_: Any = None) -> Any:
        """弹出key对应的value，若无此数据，则返回default_"""
        return self.__dict__.pop(key, default_)

    def clear(self) -> None:
        """清空context"""
        self.__dict__ = {}

    @staticmethod
    def load_json(json_file, default_config=None) -> None:
        """加载json file

        Arguments:
            json_file {_type_} -- 加载的json file

        Raises:
            OSError: 文件不存在
        """

        json_file = Path(json_file)
        if not json_file.exists():
            raise OSError(f"json_file({json_file.as_posix()}) is not exists.")

        with open(json_file.as_posix(), "r", encoding="utf-8") as fp:
            config = json.load(fp)

        return vxContext(default_config, **config)

    def save_json(self, json_file: str) -> None:
        """保存json file

        Arguments:
            json_file {str} -- 待保存的json file

        """
        with open(json_file, "w", encoding="utf-8") as fp:
            json.dump(self, fp, indent=4, cls=vxJSONEncoder)


@singledispatch
def _to_vxcontext(self: Any):
    """转换为vxdict obj"""
    return self


@_to_vxcontext.register(Mapping)
def _(obj: Mapping) -> vxDict:
    return vxContext(**obj)


@_to_vxcontext.register(Sequence)
def _(obj: Sequence) -> List:
    return obj if isinstance(obj, str) else [_to_vxcontext(o_) for o_ in obj]


@vxJSONEncoder.register(vxContext)
def _(obj):
    return dict(obj.items())


MutableMapping.register(vxContext)
