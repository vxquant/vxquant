#!/usr/bin/env python
"""setup.py"""
# Note: To use the 'upload' functionality of this file, you must:
#   $ pipenv install twine --dev


import os
import sys
import pathlib
import importlib
import contextlib
from shutil import rmtree
from setuptools import setup, Command
from setuptools.config import setupcfg


# 读取配置文件中的设置内容
here = pathlib.Path(__file__).parent

conf_dict = setupcfg.read_configuration(here.joinpath("setup.cfg").absolute())
metadata = conf_dict.get("metadata", {})
options = conf_dict.get("options", {})

try:
    package = importlib.import_module(metadata["name"])
    metadata["version"] = package.VERSION
except ImportError:
    version = input("Please input package version:  ")
    metadata["version"] = version


def remove_subdirs(root_dir, rmdirs=None):
    """删除root目录以下"""
    if isinstance(root_dir, str):
        root_dir = pathlib.Path(root_dir)

    for d in root_dir.iterdir():
        if d.name in rmdirs:
            with contextlib.suppress(OSError):
                rmtree(d.absolute())

        if d.is_dir():
            remove_subdirs(d, rmdirs)


# 初始化命令 python setup.py init
class InitCommand(Command):
    """Support setup.py init."""

    description = "运行自动化测试"
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print(f"\033[1m{s}\033[0m")

    def initialize_options(self):
        """初始化options"""

    def finalize_options(self):
        """finalize_options"""

    def run(self):
        """运行"""

        # 1. 创建package根目录
        root_dir = pathlib.Path(__file__).parent
        package_dir = root_dir.joinpath(metadata["name"])
        if not package_dir.exists():
            self.status(f"create package dir: {package_dir.absolute()}")
            package_dir.mkdir(parents=True, exist_ok=True)

        init_file = package_dir.joinpath("__init__.py")
        if not init_file.exists():
            self.status(f"create __init__.py: {init_file.absolute()}")
            with open(init_file.absolute(), "w", encoding="utf-8") as fp:
                fp.write(f"\"\"\" {metadata['description']} \"\"\"\n\n\n")
                fp.write(f'VERSION = "{metadata["version"]}"\n')

        testcase_dir = root_dir.joinpath("tests")
        if not testcase_dir.exists():
            self.status(f"create testcase dir: {testcase_dir.absolute()}")
            testcase_dir.mkdir(parents=True, exist_ok=True)

        self.status("Creating Virtual Envriments...")
        os.system(f"{sys.executable} -m pip install -U pip")
        os.system(f"pipenv install {' '.join(options['install_requires'])}")

        self.status("Install requirements ...")

        os.system(
            f"{sys.executable} -m pip install -U {' '.join(options['install_requires'])}"
        )

        dev_requirements = options["extras_require"].get("dev", [])
        if dev_requirements:
            self.status("Install Develop requirements ...")
            os.system(
                f"{sys.executable} -m pip install -U {' '.join(dev_requirements)}"
            )

        self.status("Activate Virtual Envriments...")
        os.system("pipenv shell")

        sys.exit()


class TestCommand(Command):
    """Support setup.py test."""

    description = "运行自动清理"
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print(f"\033[1m{s}\033[0m")

    def initialize_options(self):
        """初始化options"""

    def finalize_options(self):
        """finalize_options"""

    def run(self):
        """执行自动化测试"""
        self.status(f'Installing {metadata["name"]}')
        os.system(f"{sys.executable} setup.py install")

        self.status("Start run test cases...")
        os.system("pytest")


class DistCleanCommand(Command):
    """Support setup.py distclean."""

    description = "运行自动清理"
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print(f"\033[1m{s}\033[0m")

    def initialize_options(self):
        """初始化options"""

    def finalize_options(self):
        """finalize_options"""

    def run(self):
        """运行"""

        for dir_ in ["dist", "build", "log", f'{metadata["name"]}.egg-info']:
            with contextlib.suppress(OSError):
                self.status(f"Removing previous build dir: {dir_}/ ")
                rmtree(here.joinpath(dir_).absolute())

        self.status("Removing python cache dir: __pycache__/ .ipynb_checkpoints/")
        remove_subdirs(here, ["__pycache__", ".ipynb_checkpoints"])

        sys.exit()


class UploadCommand(Command):
    """Support setup.py upload."""

    description = "Build and publish the package."
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print(f"\033[1m{s}\033[0m")

    def initialize_options(self):
        """初始化options"""

    def finalize_options(self):
        """finalize_options"""

    def run(self):
        """运行"""

        with contextlib.suppress(OSError):
            self.status("Removing previous builds…")
            rmtree(os.path.join(here, "dist"))

        self.status("Building Source and Wheel (universal) distribution…")
        os.system(f"{sys.executable} setup.py sdist")  # bdist_wheel --universal")

        self.status("Uploading the package to PyPI via Twine…")
        os.system("twine upload dist/*")

        self.status("Pushing git tags…")
        os.system(f"git tag v{metadata['version']}")
        os.system("git push --tags")

        sys.exit()


cmdclass = {
    "upload": UploadCommand,
    "mytest": TestCommand,
    "distclean": DistCleanCommand,
}


setup(
    name=metadata["name"],
    version=metadata.get("version", "0.0.1"),
    description=metadata["description"],
    long_description=metadata["long_description"],
    long_description_content_type="text/markdown",
    author=metadata["author"],
    author_email=metadata["author_email"],
    python_requires=str(options["python_requires"]),  # ">=3.7.0",
    url=metadata["url"],
    packages=options["packages"],
    entry_points=options["entry_points"],
    install_requires=options["install_requires"],
    extras_require=options["extras_require"],
    include_package_data=True,
    license=metadata["license"],
    classifiers=metadata["classifiers"],
    # $ setup.py publish support.
    cmdclass={
        "upload": UploadCommand,
        "test": TestCommand,
        "distclean": DistCleanCommand,
        "init": InitCommand,
    },
)
