"""各类组件启动程序"""

import os
import sys
import subprocess
import argparse
from vxsched import vxContext
from vxutils import storage, vxtime, logger


@storage("agent", "gmagent")
def run_gmagent(config: str, mod_path: str) -> None:
    """启动gmagent

    Arguments:
        config {str} -- 配置文件
        mod_path {str} -- 模块地址
    """
    os.makedirs("etc/", exist_ok=True)
    context = vxContext.load_json(config)
    _ENV = os.environ.copy()
    _ENV.update(
        {
            "GMCONFIGFILE": config,
            "STRATEGYMOD": mod_path,
            "gm_strategyid": context.settings.gm_strategyid,
            "gm_token": context.settings.gm_token,
        }
    )
    while True:
        if vxtime.now() < vxtime.today("09:10:00"):
            logger.info("休眠等待第二天开盘时间.")
            vxtime.sleep(vxtime.today("09:11:00") - vxtime.now())
        elif vxtime.now() < vxtime.today("15:30:00"):
            try:
                p = subprocess.run(
                    [sys.executable, "-m", "vxquant.agent.gmagent"],
                    env=_ENV,
                    shell=True,
                    check=True,
                )

                vxtime.sleep(1)
            except subprocess.CalledProcessError as e:
                logger.warning(f"运行时错误: {e}")

        else:
            logger.info("休眠等待第二天开盘时间.")
            vxtime.sleep(vxtime.today("09:11:00") + 60 * 60 * 24 - vxtime.now())


@storage("agent", "gmsimagent")
def run_gmsimagent(config: str, mod_path: str) -> None:
    """启动gmsimagent"""
    os.makedirs("etc/", exist_ok=True)
    context = vxContext.load_json(config)
    _ENV = os.environ.copy()
    _ENV.update(
        {
            "GMCONFIGFILE": config,
            "STRATEGYMOD": mod_path,
            "gm_strategyid": context.settings.gm_strategyid,
            "gm_token": context.settings.gm_token,
        }
    )

    subprocess.run(
        [sys.executable, "-m", "vxquant.agent.gmsimagent"],
        env=_ENV,
        shell=True,
        check=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""trade agent server""")
    parser.add_argument("-s", "--script", help="启动组件", default="gmagent")
    parser.add_argument(
        "-c",
        "--config",
        help="path to config json file",
        default="config.json",
        type=str,
    )
    parser.add_argument("-m", "--mod", help="模块存放目录", default="./mod", type=str)
    parser.add_argument(
        "-v", "--verbose", help="debug 模式", action="store_true", default=False
    )
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel("DEBUG")

    func = storage.get("agent", args.script)

    if callable(func):
        func(args.config, args.mod)
