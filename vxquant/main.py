"""主函数"""

import argparse
import pathlib
from vxquant.utils import logger, vxtime
from vxquant.utils.convertors import to_timestring
from vxquant.utils.toolbox import vxToolBox
from vxquant.scheduler import vxContext, vxhandlers
from vxquant.scheduler.triggers import vxOnceTrigger

_default_context = {
    "connections": {},
    "channels": {
        "local": {
            "class": "vxquant.scheduler.channels.vxChannel",
            "params": {"channel_name": "__local__"},
        }
    },
    "apis": {
        "tdapi": {},
        "mdapi": {},
        "handler": {"class": "vxquant.scheduler.engine.vxhandlers"},
        "engine": {
            "class": "vxquant.scheduler.engine.vxEventEngine",
            "params": {"handlers": "handler", "channel": "local"},
        },
    },
}


@vxhandlers("__init__")
def init1111(context, event):
    """初始化"""
    logger.info(f"初始化程序{event}")
    print(context)


def run(config: str = "etc/config.json", mod: str = "mod/") -> None:
    """主策略函数"""

    logger.info("=" * 60)
    logger.info("=" * 60)
    logger.info("=" * 60)

    vxhandlers.context.update(**_default_context)
    configfile = pathlib.Path(config)
    if configfile.exists():
        vxhandlers.context.load(configfile.as_posix())
        logger.info(f"加载配置文件{configfile.as_posix()}")

    box = vxToolBox()

    if "connections" in vxhandlers.context:
        box.loads(vxhandlers.context.connections)

    if "channels" in vxhandlers.context:
        box.loads(vxhandlers.context.channels)

    if "apis" in vxhandlers.context:
        box.loads(vxhandlers.context.apis)
    logger.info(f"已加载工具: {box}")

    mod_dir = pathlib.Path(mod)
    if not mod_dir.exists():
        logger.warning(f"策略目录不存在:{mod_dir.as_posix()}")

    logger.info("-" * 60)
    logger.info("初始化mod.__init__事件")
    box.local.put("__init__", trigger=vxOnceTrigger(vxtime.now() + 5))
    box.engine.start()
    logger.info("-" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        help="config json file path: etc/config.json",
        default="config.json",
        type=str,
    )
    parser.add_argument(
        "-m", "--mod", help="module directory path : mod/ ", default="mod/", type=str
    )
    args = parser.parse_args()
    run(args.config, args.mod)
