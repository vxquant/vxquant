"""数据库ORM抽象"""

from abc import abstractmethod

from typing import Iterator, List, Optional, Type
from vxquant.utils.dataclass import vxDataClass
from vxquant.utils import logger


class vxDBConnector:
    """基于vxDataClass 数据管理"""

    # 数据表与类、primary_keys的映射表：
    __dbtable_maps__ = {}

    def __init__(self, db_string: str, **kwargs) -> None:
        pass

    @abstractmethod
    def execute(self, sql: str) -> None:
        """执行sql语句"""

    @abstractmethod
    def save(self, obj: vxDataClass) -> None:
        """保存数据"""

    @abstractmethod
    def query(self, table_name: str, *conditions: list[str]) -> Iterator:
        """查询条件"""

    @abstractmethod
    def delete(self, table_name: str, *conditions: list[str]) -> None:
        """删除"""

    @abstractmethod
    def create_mapping(
        self, vxdatacls: Type[vxDataClass], table_name: str = ""
    ) -> None:
        """建立vxdatacls类与数据表table_name之间的映射关系

        args:
            vxdatacls: Type[vxDataClass] --> vxDataClass子类
            table_name: str default: '' --> 如果未指定table_name的，按照vxdatacls.get_table_name()设定的数据表格名称执行
                                            如果指定table_name的，修改vxdatacls.__dbtable__的值，并按照最新表格执行
        """
