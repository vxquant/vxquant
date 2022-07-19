#!encoding=utf-8
"""
author: vex1023
email: vex1023@qq.com
回测用的logger，方便观察回测中的日志
"""

import os
import logging
from logging.config import dictConfig


from vxquant.utils.convertors import to_timestring
from vxquant.utils.timer import vxTimer

vxtime = vxTimer()

__all__ = ["vxLoggerFactory"]


__DEFAULT_LOG_FORMAT__ = (
    "%(quant_time)s %(module)s.%(funcName)s[%(lineno)d] %(levelname)s === %(message)s"
)

old_factory = logging.getLogRecordFactory()


def record_factory(*args, **kwargs):
    """记录工厂"""
    record = old_factory(*args, **kwargs)
    format_str = "%F %T.%f" if vxtime.status == "LIVING" else "%F %T"
    record.quant_time = to_timestring(vxtime.now(), format_str)

    return record


logging.setLogRecordFactory(record_factory)


_log_config_template = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": __DEFAULT_LOG_FORMAT__,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {},
}


class vxLoggerFactory:
    """各类型的logger的工厂类"""

    def __init__(self, root="vxUtils", level=logging.INFO, log_dir="log/"):
        """
        :param root_name: 基础logger的名称，默认为__vxQuant__
        :param log_dir: log文件的存放目录，默认为当前目录
        :param log_level: log的级别，默认为INFO
        """
        self._root = root
        self._log_dir = log_dir
        self._level = (
            level.upper() if isinstance(level, str) else logging.getLevelName(level)
        )
        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": __DEFAULT_LOG_FORMAT__,
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "DEBUG",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "loggers": {},
        }

        if self._log_dir:
            os.makedirs(self._log_dir, exist_ok=True)
            log_config["handlers"][self._root] = {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "default",
                "filename": os.path.join(self._log_dir, f"{root}.log"),
                "maxBytes": 10485760,
                "backupCount": 20,
                "encoding": "utf8",
            }
            log_config["loggers"][self._root] = {
                "level": self._level,
                "handlers": ["console", self._root],
                "propagate": "no",
            }
        else:
            log_config["loggers"][self._root] = {
                "level": self._level,
                "handlers": ["console"],
                "propagate": "no",
            }

        try:
            dictConfig(log_config)
            logger = logging.getLogger(self._root)
            logger.debug(f"logger init success, log_config: {log_config}")
        except ValueError as err:
            raise ValueError(f"logger init failed, log_config: {log_config}") from err

    def getLogger(self, logger_name="", level=logging.INFO, filename=""):
        """获取一个logger的实例

        Keyword Arguments:
            logger_name -- _description_ (default: {""})
            level -- _description_ (default: {logging.INFO})
            filename -- _description_ (default: {""})

        Returns:
            _description_
        """

        level = level.upper() if isinstance(level, str) else logging.getLevelName(level)

        if logger_name == "":
            logger = logging.getLogger(self._root)
            return logger

        # 获得child 目录
        logger_name = f"{self._root}.{logger_name}"

        if self._log_dir and filename:
            log_config = {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "default": {
                        "format": __DEFAULT_LOG_FORMAT__,
                        "datefmt": "%Y-%m-%d %H:%M:%S",
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "DEBUG",
                        "formatter": "default",
                        "stream": "ext://sys.stdout",
                    },
                },
                "loggers": {},
            }

            filename = os.path.join(self._log_dir, os.path.basename(filename))
            log_config["handlers"][logger_name] = {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "default",
                "filename": filename,
                "maxBytes": 10485760,
                "backupCount": 20,
                "encoding": "utf8",
            }
            log_config["loggers"][logger_name] = {
                "level": level,
                "handlers": [logger_name],
                "propagate": "no",
            }
            dictConfig(log_config)
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        return logger
