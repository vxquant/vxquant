"""数据库ORM抽象"""

from abc import ABC, abstractmethod

from typing import Iterator, List, Optional, Type
from vxutils.dataclass import vxDataClass
from vxutils.database.mongodb import vxMongoDB

__all__ = ["vxDataBase", "vxDBTable", "vxMongoDB"]


class vxDataBase:
    """基于vxDataClass 数据管理"""

    def __init__(self, db_uri: str, db_name: str, **kwargs) -> None:
        self._db_uri = db_uri
        self._dbname = db_name
        self._dbconn = None

    def __getitem__(self, table_name: str) -> "vxDBTable":
        return self.__dict__[table_name]

    @abstractmethod
    def create_table(
        self,
        table_name: str,
        primory_keys: List[str],
        vxdatacls: Type[vxDataClass],
        if_exists: str = "ignore",
    ) -> "vxDBTable":
        """创建数据表

        Arguments:
            table_name {str} -- 数据表名称
            primory_keys {List[str]} -- 表格主键
            vxdatacls {_type_} -- 表格数据格式
            if_exists {str} -- 如果table已经存在，若参数为ignore ，则忽略；若参数为 drop，则drop掉已经存在的表格，然后再重新创建

        Returns:
            vxDBTable -- 返回数据表格实例
        """

    @abstractmethod
    def drop_table(self, table_name: str) -> None:
        """删除数据表

        Arguments:
            table_name {str} -- 数据表名称
        """

    @abstractmethod
    def get_connection(self) -> None:
        """数据库连接"""


class vxDBTable(ABC):
    """数据表映射"""

    def __init__(
        self,
        table_name: str,
        primary_keys: List[str],
        datacls: Type[vxDataClass],
        db: vxDataBase,
    ) -> None:
        """数据表映射

        Arguments:
            table_name: {str} -- 数据表名称
            primary_keys {List[str]} -- 主键
            dataclass {Type[vxDataClass]} -- 对应
        """
        self._table_name = table_name
        self._primary_keys = primary_keys
        self._datacls = datacls
        self._db = db

    @abstractmethod
    def save(self, obj: vxDataClass) -> None:
        """保存vxdata obj对象

        Arguments:
            obj {vxDataClass} -- vxdata obj对象
        """

    @abstractmethod
    def savemany(self, *objs: List[vxDataClass]) -> None:
        """同时保存多个obj对象

        Arguments:
            objs {List[vxDataClass]} -- 多个obj对象
        """

    @abstractmethod
    def find(self, query) -> Iterator:
        """查询vxdata obj对象

        Arguments:
            conditions {List[str]} -- 查询条件,如: "id=3","age>=5"...

        Yields:
            Iterator -- vxdata obj迭代器
        """

    @abstractmethod
    def delete(self, obj: Optional[vxDataClass]) -> None:
        """删除vxdata obj对象

        Arguments:
            obj {vxDataClass} -- obj

        Raises:
            ValueError -- 若 obj 类型不是table对应的dataclass，则抛出 ValueError

        """

    def deletemany(self, query) -> None:
        """按条件删除vxdata obj对象

        Arguments:
            conditions {List[str]} -- 查询条件,如: "id=3","age>=5"...

        Raises:
            ValueError -- 若 conditions 为空，则抛出异常。希望清空表格时，适用 truncate()接口

        """

    @abstractmethod
    def distinct(self, col_name: str, query=None) -> List:
        """去重后的数值列表

        Arguments:
            col_name {str} -- 去重后列表名称

        Returns:
            List -- 去重后的数值列表
        """

    @abstractmethod
    def truncate(self) -> None:
        """清空数据表"""

    @abstractmethod
    def create_table(self) -> None:
        """创建数据库表"""

    @abstractmethod
    def drop_table(self) -> None:
        """删除数据库表"""
