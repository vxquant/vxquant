"""各类型"""

import pathlib
import importlib

from collections.abc import Mapping
from vxsched import vxContext, vxengine, vxEventQueue
from vxsched.triggers import vxDailyTrigger
from vxutils import storage, logger, vxWrapper

__all__ = ["run_worker", "run_broker"]

_default_worker_config = {
    "settings": {
        "zmqbackend": {
            "addr": "tcp://127.0.0.1:6666",
            "public_key": "",
            "connect_mode": "connect",
            "channels": ["test"],
        },
    },
    "params": {},
}

_default_broker_config = {
    "settings": {
        "frontend": {
            "addr": "tcp://127.0.0.1:5555",
            "public_key": "",
            "connect_mode": "bind",
        },
        "backend": {
            "addr": "tcp://127.0.0.1:6666",
            "public_key": "",
            "connect_mode": "bind",
        },
        "events": {},
    },
    "params": {},
    "rpc_methods": {},
}


@storage("scheduler", "worker")
def run_worker(config: str = "", mod_path: str = ""):
    logger.info(f"{' 欢迎启动worker模式 ':=^80}")
    if pathlib.Path(config).is_file():
        context = vxContext.load_json(config, _default_worker_config)
        logger.info(f"加载配置文件: {config} 完成")
    else:
        context = vxContext(_default_worker_config)
        logger.info("使用缺省的配置项")

    from . import worker

    if mod_path and pathlib.Path(mod_path).is_dir():
        vxengine.load_modules(mod_path)

    # logger.info(f"置换context : {context}")
    vxengine.initialize(context=context)

    vxengine.serve_forever()


@storage("scheduler", "broker")
def run_broker(config: str = "", mod_path: str = ""):
    if pathlib.Path(config).is_file():
        context = vxContext.load_json(config, _default_broker_config)
        logger.info(f"加载配置文件: {config} 完成")
    else:
        context = vxContext(_default_broker_config)
        logger.info("使用缺省的配置项")

    from . import broker

    if mod_path and pathlib.Path(mod_path).is_dir():
        vxengine.load_modules(mod_path)


    logger.info(f"置换context : {context}")
    vxengine.initialize(context=context)

    vxengine.serve_forever()


if __name__ == "__main__":
    # importlib.import_module("worker", ".")
    # importlib.import_module("broker", ".")
    run_broker("etc/broker.json")
