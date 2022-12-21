"""sqlite3 连接操作类"""
from contextlib import suppress
import sqlite3 as dbdriver
from typing import Iterator, List, Any, Type, Optional
from vxutils.dataclass import (
    vxBoolField,
    vxDataClass,
    vxField,
    vxFloatField,
    vxIntField,
    vxUUIDField,
    vxDatetimeField,
)
from vxutils.database import vxDataBase, vxDBTable
from vxutils import logger

column_type_map = {vxFloatField: "REAL", vxIntField: "INT", vxDatetimeField: "TEXT"}


class vxSqliteDBTable(vxDBTable):
    """sqlite3 数据库表类"""

    def save(self, obj: vxDataClass) -> None:
        col_names = []
        values = []
        update_string = []
        for col, value in obj.items():
            col_names.append(f"'{col}'")
            values.append(f"'{value}'")
            if col not in self._primary_keys:
                update_string.append(f"{col}=excluded.{col}")

        sql = f"""INSERT INTO {self._table_name} ({','.join(col_names)}) \n\tVALUES ({','.join(values)})"""
        if self._primary_keys:
            sql += f"""\nON CONFLICT({",".join(self._primary_keys)})\n\tDO UPDATE SET {','.join(update_string)}"""
        sql += ";"

        with self._db.get_connection() as conn:
            logger.info(f"执行SQL: {sql}")
            conn.execute(sql)

    def savemany(self, *objs: List[vxDataClass]) -> None:
        with self._db.get_connection() as conn:
            for obj in objs:
                col_names = []
                values = []
                update_string = []
                for col, value in obj.items():
                    col_names.append(f"'{col}'")
                    values.append(f"'{value}'")
                    if col not in self._primary_keys:
                        update_string.append(f"{col}=excluded.{col}")

                sql = f"""INSERT INTO {self._table_name} ({','.join(col_names)}) \n\tVALUES ({','.join(values)})"""
                if self._primary_keys:
                    sql += f"""\nON CONFLICT({",".join(self._primary_keys)})\n\tDO UPDATE SET {','.join(update_string)}"""
                sql += ";"
                conn.execute(sql)

    def find(self, query: str) -> Iterator:
        sql = f"""SELECT * FROM `{self._table_name}`"""
        if query:
            sql += f""" WHERE {query}"""
        sql += ";"

        with self._db.get_connection() as conn:
            logger.info(f"执行SQL: {sql}")
            for row in conn.execute(sql):
                logger.info(f"返回查询结果: {row}")
                yield self._datacls(*row)

    def delete(self, obj: Optional[vxDataClass]) -> None:
        if not isinstance(obj, self._datacls):
            raise ValueError(
                f"type of obj is {type(obj)} is not class: {self._datacls}"
            )

        conditions = [f"{col}={obj[col]}" for col in self._primary_keys]

        if not conditions:
            raise ValueError(f"如需清空表格所有数据，请使用truncate({self._table_name}).")

        sql = f"""DELETE FROM `{self._table_name}` where {" and ".join(conditions)};"""

        with self._db.get_connection() as conn:
            conn.execute(sql)

    def deletemany(self, query) -> None:
        if not query:
            raise ValueError(f"如需清空表格所有数据，请使用truncate({self._table_name}).")

        sql = f"""DELETE FROM `{self._table_name}` where {query};"""

        with self._db.get_connection() as conn:
            conn.execute(sql)

    def truncate(self) -> None:
        """清空数据表"""
        logger.warning(f"truncate table : {self._table_name}")
        with self._db.get_connection() as conn:
            conn.execute(f"DELETE FROM `{self._table_name}``;")

    def create_table(self) -> None:
        """创建数据库表格"""

        column_def = []

        for name, vxfield in self._datacls.__dict__.items():
            if not isinstance(vxfield, vxField):
                continue
            column_type = column_type_map.get(vxfield.__class__, "TEXT")
            if name in self._primary_keys:
                column_type = f"{column_type} NOT NULL"

            column_def.append(f"'{name}' {column_type}")

        if self._primary_keys:
            primary_key_string = f"""PRIMARY KEY(`{"`,`".join(self._primary_keys)}`)"""
            sql = f"""CREATE TABLE IF NOT EXISTS `{self._table_name}` ({','.join(column_def)},{primary_key_string});"""
        else:
            sql = f"""CREATE TABLE IF NOT EXISTS `{self._table_name}` ({','.join(column_def)});"""

        with self._db.get_connection() as conn:
            conn.execute(sql)

    def drop_table(self) -> None:
        sql = f"DROP TABLE `{self._table_name}`;"
        with self._db.get_connection() as conn:
            conn.execute(sql)

    def distinct(self, col_name: str, query=None) -> List:
        sql = f""" SELECT DISTINCT `{col_name}` FROM `{self._table_name}` """
        if query:
            sql += f""" WHERE { query } """
        sql += ";"

        with self._db.get_connection() as conn:
            cur = conn.execute(sql)
            return [row[col_name] for row in cur]


class vxSqliteDB(vxDataBase):
    """基于sqlite3 数据管理"""

    def __init__(self, db_uri: str = ":memory:", db_name: str = "", **kwargs) -> None:
        super().__init__(db_uri, db_name, **kwargs)
        self._db = dbdriver.connect(db_uri, **kwargs)
        self._db.row_factory = dbdriver.Row

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
        if table_name not in self.__dict__:
            self.__dict__[table_name] = vxSqliteDBTable(
                table_name, primory_keys, vxdatacls, self
            )
            self.__dict__[table_name].create_table()
        return self.__dict__[table_name]

    def drop_table(self, table_name: str) -> None:
        """删除数据表

        Arguments:
            table_name {str} -- 数据表名称
        """

        dbtable = self.__dict__.pop(table_name, None)
        if dbtable:
            dbtable.drop_table()

    def get_connection(self):
        """数据库连接"""
        return self._db

    def close(self):
        """关闭连接"""
        self._conn.close()


class vxTest(vxDataClass):
    """初始化"""

    id: str = vxUUIDField()
    name: str = vxIntField(0)
    data: str = vxField()
    is_check: bool = vxBoolField(True)
    due_dt: float = vxDatetimeField(formatter_string="%Y-%m-%d %H:%M:%S.%f")


class vxTest2(vxDataClass):
    """初始化"""

    id2: str = vxUUIDField()
    name2: str = vxField("tt")
    data: str = vxField()
    is_check: bool = vxBoolField(False)
    due_dt: float = vxDatetimeField(formatter_string="%Y-%m-%d %H:%M:%S.%f")


if __name__ == "__main__":
    logger.setLevel("DEBUG")
    db = vxSqliteDB("/Users/libao/src/git/vxutils/tests/test.db")
    db.create_table("test", ["id"], vxTest)
    db.create_table("test2", ["id", "name"], vxTest)
    db.create_table("test3", ["id2", "name2"], vxTest2)

    t1 = vxTest(id=3, name=3, data=33)

    db["test"].save(t1)
    logger.warning("=" * 60)
    t1.id = 5
    db["test"].save(t1)
    t1.id = 3
    db["test"].save(t1)
    t1.name = 10
    db["test"].save(t1)
    t1.data = 10
    db.test.save(t1)
    print(db.test.distinct("name"))

    for obj in db["test"].find("id in (3,5)"):
        print(obj)

    print("=" * 80)
    print("=" * 80)
    db.test.deletemany("name=10")
    for obj in db.test.find("name > 4"):
        print(obj)

    print("=" * 80)
    print("=" * 80)

    names = db.test.distinct("name")
    print(names)
