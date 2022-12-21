#!encoding=utf-8
"""
author: vex1023
email: vex1023@qq.com
回测用的logger，方便观察回测中的日志
"""


import pathlib
import sys
import logging
import logging.handlers


__all__ = ["vxLoggerFactory"]

__DEFAULT_LOG_FORMAT__ = (
    "%(asctime)s [%(process)s:%(threadName)s - %(funcName)s@%(filename)s:%(lineno)d]"
    " %(levelname)s === %(message)s"
)


class vxLoggerFactory:
    def __init__(self, root="__vxQuant__", level=logging.INFO, log_dir="log/"):
        """
        :param root_name: 基础logger的名称，默认为__vxQuant__
        :param log_dir: log文件的存放目录，默认为当前目录
        :param log_level: log的级别，默认为INFO
        """
        self._root = root
        self._root_level = level
        self._log_dir = log_dir
        logger = logging.getLogger(root)
        logger.setLevel(level)
        has_console = False
        has_filehandler = False
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                has_console = True
            elif isinstance(handler, logging.handlers.TimedRotatingFileHandler):
                has_filehandler = True

        if has_console is False:
            self._formatter = logging.Formatter(__DEFAULT_LOG_FORMAT__)
            console = logging.StreamHandler(sys.stdout)
            console.setFormatter(self._formatter)
            console.setLevel(logging.DEBUG)
            logger.addHandler(console)

        if log_dir and has_filehandler is False:
            self._log_dir = pathlib.Path(log_dir)
            self._log_dir.mkdir(parents=True, exist_ok=True)
            self._add_filehandler(logger, "vxquant.log", logging.DEBUG)
        logger.debug("logger 初始化完成.")

    def _add_filehandler(self, logger, filename, level=None):
        if self._log_dir is None:
            logger.warning(f"{self.__class__.__name__} 未设置log dir.")
            return

        level = level or logging.INFO

        filename = self._log_dir.joinpath(filename).as_posix()

        filehandler = logging.handlers.TimedRotatingFileHandler(
            filename, when="D", backupCount=20, encoding="utf8"
        )

        filehandler.setFormatter(self._formatter)
        filehandler.setLevel(self._root_level)
        logger.addHandler(filehandler)

    def getLogger(self, logger_name="", level=logging.INFO, filename=""):
        """获取一个logger的实例

        Keyword Arguments:
            logger_name -- _description_ (default: {""})
            level -- _description_ (default: {logging.INFO})
            filename -- _description_ (default: {""})

        Returns:
            _description_
        """
        if not logger_name:
            return logging.getLogger(self._root)

        logger_name = f"{self._root}.{logger_name}"
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            logger.removeHandler(handler)
            logger.debug(f"移除 log handler: {handler}")

        logger.setLevel(level)
        if filename and self._log_dir:
            self._add_filehandler(logger, filename, logging.DEBUG)
        return logger
