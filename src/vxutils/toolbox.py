"""api工具箱"""
import io
import importlib
import pathlib
from typing import Any, Union, Dict
from collections.abc import Mapping
import vxutils

try:
    import simplejson as json
except ImportError:
    import json
__all__ = ["import_tools", "vxToolBox", "vxWrapper"]


def import_tools(mod_path, params=None):
    """导入工具"""

    if params is None:
        params = {}

    cls_or_obj = mod_path
    if isinstance(mod_path, str):
        if mod_path.find(".") > -1:
            class_name = mod_path.split(".")[-1]
            mod_name = ".".join(mod_path.split(".")[:-1])
            mod = importlib.import_module(mod_name)
            cls_or_obj = getattr(mod, class_name)
        else:
            cls_or_obj = importlib.import_module(mod_path)

    return cls_or_obj(**params) if isinstance(cls_or_obj, type) else cls_or_obj


class vxWrapper:
    """根据参数配置，包装任意对象"""

    def __init__(self, mod_path=None, params=None):
        self._provider = None
        self.register(mod_path, params)

    @property
    def provider(self):
        return self._provider

    def register(self, mod_path, params=None):
        provider = import_tools(mod_path, params)
        if provider is None:
            raise ValueError("provider is None")
        self._provider = provider

    def __repr__(self):
        return f"{self.__class__.__name__}(provider={self._provider})"

    __str__ = __repr__

    def __getattr__(self, key):
        if self.__dict__.get("_provider", None) is None:
            raise AttributeError("Warpper({self.__name__}) 未进行初始化工作")
        return getattr(self._provider, key)

    def __call__(self, *args, **kwargs):
        return self._provider(*args, **kwargs)

    def __getstate__(self):
        # if hasattr(self._provider, "__getstate__"):
        #    return {"_provider": self._provider}

        import joblib

        with io.BytesIO() as bfp:
            joblib.dump(self._provider, bfp)
            return {"_privider_pickle": bfp.getvalue()}

    def __setstate__(self, state):
        try:
            import joblib

            with io.BytesIO(state["_privider_pickle"]) as bfp:
                self._provider = joblib.load(bfp)
        except ImportError:
            self._provider = state["_provider"]

    @staticmethod
    def init_by_config(config: dict):
        """根据配置文件初始化对象

        配置文件格式:
        config = {
            'class': 'vxsched.vxEvent',
            'params': {
                "type": "helloworld",
                "data": {
                    'class': 'vxutils.vxtime',
                },
                "trigger": {
                    "class": "vxsched.triggers.vxIntervalTrigger",
                    "params":{
                        "interval": 10
                    }
                }
            }
        }

        """
        # if not isinstance(config, dict):
        #    raise TypeError("config must be a dict")

        if not isinstance(config, Mapping) or "class" not in config:
            return config

        mod_path = config["class"]
        params = {
            k: vxWrapper.init_by_config(v)
            if isinstance(v, Mapping) and "class" in v
            else v
            for k, v in config.get("params", {}).items()
        }

        return import_tools(mod_path, params)


@vxutils.singleton
class vxToolBox:
    """api box"""

    def __init__(self, settings: Union[str, Dict] = None) -> None:
        if settings:
            self.loads(settings)

    def __getitem__(self, key: str):
        return self.__dict__[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.__dict__[key] = value

    def __str__(self):
        message = {
            name: (
                f"module {tool.__name__} at id ({id(tool)})"
                if hasattr(tool, "__name__")
                else f"class {tool.__class__.__name__} at id ({id(tool)})"
            )
            for name, tool in self.__dict__.items()
        }

        return (
            f"< {self.__class__.__name__} (id-{id(self)}) :"
            f" {vxutils.to_json(message)} >"
        )

    def _load_tool(self, tool_name: str, tool_params: dict, settings: dict) -> None:
        """加载当个工具"""
        if "class" not in tool_params:
            vxutils.logger.warning(f"{tool_name}导入参数格式错误，请修改后，重新导入.")
            return

        if "params" not in tool_params:
            self.__dict__[tool_name] = import_tools(tool_params["class"])
            vxutils.logger.info(f"工具{tool_name} 加载成功.")
            return

        kwargs = {}
        for k, v in tool_params["params"].items():
            if v in settings and v not in self.__dict__:
                self._load_tool(v, settings[v], settings)
            kwargs[k] = self.__dict__.get(v, v)

        self.__dict__[tool_name] = import_tools(tool_params["class"], kwargs)
        vxutils.logger.info(f"工具{tool_name} 加载成功.")

    def loads(self, settings: dict) -> None:
        """加载工具"""

        if isinstance(settings, str):
            settings = pathlib.Path(settings)
            if not settings.exists() or not settings.is_file():
                vxutils.logger.error(f"{settings} 文件不存在.", exc_info=True)
                return

            with open(settings.as_posix(), "r", encoding="utf-8") as f:
                settings = json.load(f)

        for tool_name, tool_params in settings.items():
            if tool_name in self.__dict__:
                vxutils.logger.warning(f"工具名称:{tool_name}已加载，无需重复加载")
                continue

            try:
                self._load_tool(tool_name, tool_params, settings)
            except Exception as err:
                vxutils.logger.error(
                    f"加载工具{tool_params['class']}({tool_params.get('params','')}) 初始化失败:"
                    f" {err}",
                    exc_info=True,
                )


if __name__ == "__main__":
    from vxutils import vxtime

    config = {
        "class": "vxsched.vxEvent",
        "params": {
            "type": "helloworld",
            "data": {
                "class": "vxutils.vxtime",
            },
            "trigger": {
                "class": "vxsched.triggers.vxIntervalTrigger",
                "params": {
                    "interval": 10,
                    "start_dt": vxtime.now() + 10,
                    "skip_holiday": True,
                },
            },
            "channel": float("inf"),
        },
    }
    a = vxWrapper.init_by_config(config)
    print(a)
    print(next(a.trigger))
