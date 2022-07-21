"""sqlite3 连接操作类"""
import sqlite3 as dbdriver
from typing import Iterator, List, Any, Type
from vxquant.utils.dataclass import (
    vxBoolField,
    vxDataClass,
    vxField,
    vxFloatField,
    vxIntField,
    vxUUIDField,
    vxDatetimeField,
)
from vxquant.utils.db import vxDBConnector
from vxquant.utils import logger

column_type_map = {vxFloatField: "REAL", vxIntField: "INT", vxDatetimeField: "REAL"}


class vxSqliteConnector(vxDBConnector):
    """基于sqlite3 数据管理"""

    def __init__(self, db_string: str = ":memory:", **kwargs) -> None:
        super().__init__(db_string, **kwargs)
        self._conn = dbdriver.connect(db_string, **kwargs)
        self._conn.row_factory = dbdriver.Row

    def create_mapping(
        self, vxdatacls: Type[vxDataClass], table_name: str = ""
    ) -> None:
        """建立vxdatacls类与数据表table_name之间的映射关系

        args:
            vxdatacls: Type[vxDataClass] --> vxDataClass子类
            table_name: str default: '' --> 如果未指定table_name的，按照vxdatacls.get_table_name()设定的数据表格名称执行
                                            如果指定table_name的，修改vxdatacls.__dbtable__的值，并按照最新表格执行
        """

        if not table_name:
            table_name = vxdatacls.get_table_name()
        else:
            vxdatacls.__dbtable__ = table_name

        primary_keys = vxdatacls.get_primary_keys()
        column_def = []

        for name, vxfield in vxdatacls.__dict__.items():
            if not isinstance(vxfield, vxField):
                continue
            column_type = column_type_map.get(vxfield.__class__, "TEXT")
            if name in primary_keys:
                column_type = f"{column_type} NOT NULL"

            column_def.append(f"'{name}' {column_type}")

        if primary_keys:
            primary_key_string = f"""PRIMARY KEY('{"','".join(primary_keys)}')"""
            sql = f"""CREATE TABLE IF NOT EXISTS '{table_name}' ({','.join(column_def)},{primary_key_string});"""
        else:
            sql = f"""CREATE TABLE IF NOT EXISTS '{table_name}' ({','.join(column_def)});"""

        logger.debug(f"创建表格: {sql}")
        self._conn.execute(sql)

        self.__dbtable_maps__[table_name] = vxdatacls
        vxdatacls.install_db(self)

    def execute(self, sql: str, params: Any = None):

        """执行sql语句

        Args:
            sql : 待执行的sql语句
            params: sql的相关参数

        Returns:
            Cursor

        """
        if params is None:
            params = []
        logger.debug(f"执行: {sql}")
        with self._conn:
            return self._conn.execute(sql, params)

    def save(self, obj: vxDataClass) -> None:
        """保存 obj 进入数据库中"""
        if obj.get_table_name() is None:
            raise ValueError(
                f"{obj.__class__.__name__}未进行初始化，请先运行 {self.__class__.__name__}.init_tables 后再进行保存数据."
            )

        col_names = []
        values = []
        update_string = []
        for col, value in obj.items():
            col_names.append(f"{col}")
            values.append(f"'{value}'")
            if obj.get_primary_keys() and col not in obj.get_primary_keys():
                update_string.append(f"{col}=excluded.{col}")

        sql = f"""INSERT INTO {obj.get_table_name()} ({','.join(col_names)}) \n\tVALUES ({','.join(values)})"""
        if obj.get_primary_keys():
            sql += f"""\nON CONFLICT({",".join(obj.get_primary_keys())})\n\tDO UPDATE SET {','.join(update_string)}"""
        sql += ";"
        self._conn.execute(sql)

    def query(self, table_name: str, *conditions: List[str]) -> Iterator:
        """查询条件"""

        sql = f"""SELECT * FROM `{table_name}`"""
        if conditions:
            sql += f""" WHERE {' and '.join(conditions)}"""
        sql += ";"

        vxdatacls = self.__dbtable_maps__[table_name]
        for row in self.execute(sql):
            yield vxdatacls(*row)

    def distinct(
        self, col_name: str, table_name: str, *conditions: list[str]
    ) -> Iterator:
        """独立值"""

        sql = f""" SELECT DISTINCT `{col_name}` FROM `{table_name}` """
        if conditions:
            sql += f""" WHERE {" and ".join(conditions) } """

        return [row[col_name] for row in self.execute(sql)]

    def delete(self, table_name: str, *conditions: list[str]) -> None:
        """删除"""
        if not conditions:
            raise ValueError(f"如需清空表格所有数据，请使用truncate({table_name}).")

        sql = f"""DELETE FROM {table_name} where {' and '.join(conditions)};"""
        self.execute(sql)

    def truncate(self, table_name: str) -> None:
        """清空数据表所有数据"""
        self.execute(f"""DELETE FROM {table_name}""")

    def close(self):
        """关闭连接"""
        self._conn.close()


class vxTest(vxDataClass):
    """初始化"""

    __dbtable__: str = "hello"
    __primary_keys__: tuple = ("id", "name")

    id: str = vxUUIDField()
    name: str = vxField("tt")
    data: str = vxField()
    is_check: bool = vxBoolField(True)
    due_dt: float = vxDatetimeField(formatter_string="%Y-%m-%d %H:%M:%S.%f")


class vxTest2(vxDataClass):
    """初始化"""

    __dbtable__: str = "world"
    __primary_keys__: tuple = ("id2", "name2")

    id2: str = vxUUIDField()
    name2: str = vxField("tt")
    data: str = vxField()
    is_check: bool = vxBoolField(False)
    due_dt: float = vxDatetimeField(formatter_string="%Y-%m-%d %H:%M:%S.%f")


if __name__ == "__main__":
    logger.setLevel("DEBUG")
    sqldb = vxSqliteConnector("/Users/libao/src/git/vxquant/example/test.db")
    sqldb.create_mapping(vxTest)
    sqldb.create_mapping(vxTest2)
    t1 = vxTest(id=3, name=3, data=33)

    t1.save()
    t1.id = 5
    t1.save()
    t1.id = 3
    t1.save()
    t1.name = 10
    t1.save()
    t1.data = 10
    t1.save()

    for obj in t1.query("id = 5"):
        print(obj)

    # t1.delete()
    print("=" * 80)
    for obj in t1.query("name = 10"):
        print(obj)

    sqldb._conn.commit()

    names = t1.distinct("name")
    print(names)
