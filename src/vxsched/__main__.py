"""vxsched 主函数"""

import argparse
import pathlib
from vxutils import logger, storage
from vxsched import vxengine, vxContext

from vxsched.scripts import *

_default_context = {"settings": {}, "params": {}}


@storage("scheduler", "scheduler")
def run_scheduler(config=None, mod_path=None):
    if config and pathlib.Path(config).is_file():
        logger.info(f"loading config file: {config}")
        context = vxContext.load_json(config, _default_context)
    else:
        context = vxContext()

    vxengine.load_modules(mod_path)
    vxengine.initialize(context=context)
    vxengine.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--script", help="启动组件", default="scheduler")

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
    parser.add_argument(
        "-v", "--verbose", help="debug 模式", action="store_true", default=False
    )
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel("DEBUG")

    run_func = storage.get("scheduler", args.script)

    run_func(config=args.config, mod_path=args.mod)
