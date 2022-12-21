# encoding=utf-8
""" 定制的数据类型

vxDataClass
vxDict

"""


import contextlib
from functools import singledispatch
import zlib
import math
import uuid
import pickle
from pathlib import Path
from enum import Enum
from collections.abc import MutableMapping, Mapping, Sequence
from typing import Any, Callable, Optional, List, Dict

from vxutils import (
    vxtime,
    vxJSONEncoder,
    to_json,
    to_enum,
    to_timestamp,
    to_timestring,
)

try:
    import simplejson as json
except ImportError:
    import json


__all__ = [
    "vxField",
    "vxUUIDField",
    "vxEnumField",
    "vxIntField",
    "vxFloatField",
    "vxPropertyField",
    "vxDatetimeField",
    "vxBoolField",
    "vxDataMeta",
    "vxDataClass",
    "vxDataConvertor",
    "vxDict",
]


class vxField:
    """字段属性描述符

    default_factory: 缺省值 或缺省值生成函数
        ---> default_factory()

    convertor_factory: 类型转换函数
        ---> convertor_factory(input_value) -> value
        ---> 例如: lambda x: to_timestring(x)

    property_factory: 属性函数字段
        ---> property_factory(obj)  -> value
        ---> 例如: lambda obj: obj.x+obj.y

    format_factory: 格式化输入函数
        ---> fortmat_factory(value) ---> string
        ---> 例如：lambda value: to_timestring(value, '%Y-%m-%d %H:%M:%S')


    """

    __slots__ = [
        "_name",
        "_fget",
        "_fset",
        "_property_factory",
        "_default_factory",
        "_convertor_factory",
        "_format_factory",
    ]

    def __init__(
        self,
        default_factory: Any = None,
        convertor_factory: Callable = None,
        property_factory: Callable = None,
        format_factory: Callable = None,
    ):
        self._fget = None
        self._fset = None
        self._property_factory = property_factory
        self._default_factory = (
            default_factory if callable(default_factory) else lambda: default_factory
        )
        self._convertor_factory = convertor_factory
        self._format_factory: Callable = format_factory
        self._name = None

    def __set_name__(self, owner, name):
        """设置属性名称"""

        self._name = f"_{name}"
        # 设置获取attr的方法
        if callable(self._property_factory):
            self._fget = lambda obj, owner: self._property_factory(obj)
            self._fset = None
            return

        self._fget = lambda obj, owner: getattr(obj, self._name, self.default)

        if self._name == "_updated_dt":

            def fset(obj, value):
                setattr(obj, "_updated_dt", self._convertor_factory(value))

        elif callable(self._convertor_factory):

            def fset(obj, value):
                setattr(obj, self._name, self._convertor_factory(value))
                setattr(obj, "_updated_dt", vxtime.now())

        else:

            def fset(obj, value):
                setattr(obj, self._name, value)
                setattr(obj, "_updated_dt", vxtime.now())

        self._fset = fset

    def __get__(self, obj, owner):
        try:
            return self._fget(obj, owner)
        except Exception:
            return self.default

    def __set__(self, obj, value):
        if self._fset is None:
            return

        try:
            self._fset(obj, value)
        except Exception:
            setattr(obj, self._name, self.default)

    def __str__(self) -> str:
        return f"{self.__class__.__name__} default: {self.default}"

    __repr__ = __str__

    @property
    def default(self):
        """缺省值"""

        return self._default_factory()


class vxUUIDField(vxField):
    """uuid类型

    auto : auto 为True,则系统初始化自动创建一个uuid，为false则默认值为: ''
    """

    def __init__(self, auto=True) -> None:
        super().__init__(
            default_factory=lambda: str(uuid.uuid4()) if auto else "",
            convertor_factory=lambda value: value or "",
        )


class vxEnumField(vxField):
    """Enum类型字段"""

    def __init__(self, default: Enum) -> None:
        super().__init__(
            default_factory=lambda: default,
            convertor_factory=lambda x: to_enum(x, default.__class__, default),
        )


class vxIntField(vxField):
    """整数类型字段"""

    def __init__(
        self, default: int, _min: Optional[float] = None, _max: Optional[float] = None
    ):
        if _min is None:
            _min = -math.inf

        if _max is None:
            _max = math.inf

        def check_int(v: Any):
            # 四舍五入
            v = round(v)
            if _min <= v <= _max:
                return v
            raise ValueError(f"赋值 {v} 超出取值范围: [{_min},{_max}]")

        super().__init__(default_factory=default, convertor_factory=check_int)


class vxFloatField(vxField):
    """浮点类型字段"""

    def __init__(
        self,
        default: float,
        ndigits: Optional[int] = None,
        _min: Optional[float] = None,
        _max: Optional[float] = None,
    ):
        if _min is None:
            _min = -math.inf

        if _max is None:
            _max = math.inf

        def check_float(v: Any):
            v = float(v)
            if ndigits is not None:
                v = round(v, ndigits)

            if _min <= v <= _max:
                return v
            raise ValueError(f"赋值 {v} 超出取值范围: [{_min},{_max}]")

        super().__init__(default_factory=default, convertor_factory=check_float)


class vxPropertyField(vxField):
    """函数属性类型字段"""

    def __init__(
        self, property_factory: Callable[[Any], Any], default_factory: Any = None
    ):
        super().__init__(
            property_factory=property_factory, default_factory=default_factory
        )


class vxDatetimeField(vxField):
    """时间类型字段"""

    def __init__(self, default_factory=vxtime.now, formatter_string="%F %H:%M:%S.%f"):
        super().__init__(
            default_factory=default_factory,
            convertor_factory=to_timestamp,
            format_factory=lambda value: to_timestring(value, formatter_string),
        )


class vxBoolField(vxField):
    """bool字段"""

    def __init__(self, default):
        super().__init__(default_factory=bool(default), convertor_factory=bool)


class vxDataMeta(type):
    """data 元类"""

    def __new__(cls, name: str, bases: tuple, attrs: dict):
        message_formater = {
            name: var._format_factory
            for name, var in attrs.items()
            if isinstance(var, vxField)
        }

        for base_cls in bases:
            message_formater.update(**base_cls.__vxfields__)

        attrs["created_dt"]: float = vxDatetimeField()
        attrs["updated_dt"]: float = vxDatetimeField()
        message_formater["created_dt"] = attrs["created_dt"]._format_factory
        message_formater["updated_dt"] = attrs["updated_dt"]._format_factory

        if "__sortkeys__" in attrs:

            def is_lower_than(self, other: "vxDataClass") -> bool:
                """< 根据sortkeys的顺序一次对比"""
                for k in self.__sortkeys__:
                    if getattr(self, k) < getattr(other, k):
                        return True
                    elif getattr(self, k) > getattr(other, k):
                        return False
                return False

            def is_greater_than(self, other: "vxDataClass") -> bool:
                """> 根据sortkeys的顺序一次对比"""
                for k in self.__sortkeys__:
                    if getattr(self, k) < getattr(other, k):
                        return False
                    elif getattr(self, k) > getattr(other, k):
                        return True
                return False

            attrs["__lt__"] = is_lower_than
            attrs["__gt__"] = is_greater_than

        attrs["__vxfields__"] = message_formater
        attrs["__slots__"] = tuple(f"_{name}" for name in message_formater)

        return type.__new__(cls, name, bases, attrs)

    def __call__(cls, *args, **kwds) -> Any:
        created_dt = kwds.pop("created_dt", vxtime.now())
        updated_dt = kwds.pop("updated_dt", created_dt)
        instance = super().__call__(*args, **kwds)
        instance.created_dt = created_dt
        instance.updated_dt = updated_dt

        return instance


class vxDataClass(metaclass=vxDataMeta):
    """数据基类"""

    __vxfields__: dict = {}
    __sortkeys__: tuple = ()

    def __init__(self, *args, **kwargs) -> None:
        if args and isinstance(args[0], Mapping):
            kwargs.update(args[0])
        elif args:
            kwargs.update(zip(self.__vxfields__, args))

        for attr in self.keys():
            value = kwargs.pop(attr, getattr(self, attr))
            setattr(self, attr, value)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __len__(self):
        return len(self.__vxfields__)

    def __str__(self):
        message = {}
        try:
            for attr, formatter in self.__vxfields__.items():
                value = getattr(self, attr)
                if isinstance(value, vxDataClass):
                    value = value
                elif formatter:
                    value = formatter(value)

                message[attr] = value
            return f"< {self.__class__.__name__}(id-{id(self)}) : {to_json(message)} >"
        except Exception:
            message = {k: getattr(self, k) for k in self.keys()}
            return f"< {self.__class__.__name__}(id-{id(self)}) : {message} >"

    __repr__ = __str__

    def __hash__(self):
        return hash(self.__str__())

    def __eq__(self, __o: "vxDataClass") -> bool:
        return all(v == __o[k] for k, v in self.items())

    def __contains__(self, item: str) -> bool:
        return item in self.keys() if item else False

    def __setstate__(self, state: dict):
        self.__init__(**state)

    def __getstate__(self):
        return self.message

    def __iter__(self):
        return next(self)

    def __next__(self):
        yield from self.keys()

    @property
    def message(self) -> dict:
        """展示数据"""
        message = {}
        for k, v in self.items():
            if isinstance(v, Enum):
                message[k] = v.name
            elif isinstance(v, vxDataClass):
                message[k] = v.message
            else:
                message[k] = v

        return message

    @staticmethod
    def pack(obj):
        """打包消息"""
        pickled = pickle.dumps(obj)
        return zlib.compress(pickled)

    @staticmethod
    def unpack(packed_obj):
        """解包消息"""
        pickled = zlib.decompress(packed_obj)
        return pickle.loads(pickled)

    def keys(self) -> Sequence:
        """相关keys"""
        yield from self.__vxfields__

    def update(self, **kwargs):
        """更新数据"""
        for k, v in kwargs.items():
            setattr(self, k, v)

    def values(self) -> Sequence:
        """获取内部数据"""
        yield from [getattr(self, key) for key in self.keys()]

    def items(self) -> Sequence:
        """获取相关(key,value)对"""
        yield from [(key, getattr(self, key)) for key in self.keys()]

    def get(self, key, _default=None) -> Any:
        """获取相关"""
        return getattr(self, key, _default)


@vxJSONEncoder.register(vxDataClass)
def _(obj):
    message = {}

    for attr, formatter in obj.__vxfields__.items():
        value = getattr(obj, attr)
        if isinstance(value, vxDataClass):
            value = value
        elif formatter:
            value = formatter(value)

        message[attr] = value

    return message


class vxDataConvertor:
    """数据转换器基础类"""

    def __init__(self, target_cls, rename_dict: MutableMapping = None) -> None:
        self._target_cls = target_cls
        self._convertors = {}
        self._defaults_data = {}

        if rename_dict is None:
            return

        for target_col, source_col in rename_dict.items():
            self.rename_columns(source_col=source_col, target_col=target_col)

    def add_convertors(self, target_col, conveter_func):
        """设置col的转换函数

        target_col : 待转换的字段名
        convertor_func(other_data) ：转换函数 或者是缺省值，其中other_data 为待转换对象内容
        """
        if not callable(conveter_func):
            raise ValueError(f"func({conveter_func.__name__} is not callable")
        self._convertors[target_col] = conveter_func

    def rename_columns(self, source_col, target_col):
        """重命名字段"""

        def _rename_func(other_data):
            """重命名转换器"""
            if hasattr(other_data, source_col):
                return getattr(other_data, source_col)
            return other_data[source_col]

        self._convertors[target_col] = _rename_func

    def set_defaults(self, target_col, default_value):
        """设置默认值"""
        self._defaults_data[target_col] = default_value

    def __call__(self, other_data, key="", **kwargs):
        data = {}

        def _convert_col(col):
            try:
                if col in self._convertors:
                    return col, self._convertors[col](other_data)
                elif hasattr(other_data, col):
                    return col, getattr(other_data, col)
                else:
                    with contextlib.suppress(KeyError):
                        return col, other_data[col]

            except Exception as err:
                from vxutils import logger

                logger.error(
                    f"target class: {self._target_cls.__name__} Other_data load"
                    f" col:{col} err. {err}",
                    exc_info=True,
                )
                logger.debug(f"other_data={other_data}")
            return col, self._defaults_data.get(col, None)

        data.update(map(_convert_col, self._target_cls.__vxfields__))
        data.update(**kwargs)

        instance = self._target_cls(**data)
        if len(key) > 0 and key in instance.keys():
            return instance[key], instance
        else:
            return instance


class vxDict(MutableMapping):
    """引擎上下文context类"""

    _default_config: Dict[str, Any] = {}

    def __init__(self, default_config: MutableMapping = None, **kwargs):
        default_config = default_config or {}
        default_config.update(kwargs)
        for k, v in default_config.items():
            self.__dict__[k] = _to_vxdict(v)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __delitem__(self, key):
        self.__dict__.__delitem__(key)

    def __setattr__(self, attr: str, value: Any) -> Any:
        self.__dict__[attr] = _to_vxdict(value)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __eq__(self, __o: MutableMapping) -> bool:
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

    def update(self, config: MutableMapping = None, **kwargs):
        """批量更新字典"""
        config = config or kwargs
        for k, v in config.items():
            self.__dict__[k] = _to_vxdict(v)

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

        return vxDict(default_config, **config)

    def save_json(self, json_file: str) -> None:
        """保存json file

        Arguments:
            json_file {str} -- 待保存的json file

        """
        with open(json_file, "w", encoding="utf-8") as fp:
            json.dump(self, fp, indent=4, cls=vxJSONEncoder)


@singledispatch
def _to_vxdict(self: Any):
    """转换为vxdict obj"""
    return self


@_to_vxdict.register(MutableMapping)
def _(obj: MutableMapping) -> vxDict:
    return vxDict(**obj)


@_to_vxdict.register(Sequence)
def _(obj: Sequence) -> List:
    return obj if isinstance(obj, str) else [_to_vxdict(o_) for o_ in obj]


@vxJSONEncoder.register(vxDict)
def _(obj):
    return dict(obj.items())


MutableMapping.register(vxDict)
Mapping.register(vxDataClass)
