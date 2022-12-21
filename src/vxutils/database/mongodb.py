"""mongodb with vxDataClass and vxDict"""

import contextlib
from functools import reduce
from multiprocessing import Lock
import operator
from typing import Type, List, Dict, Any
import pymongo
from pymongo import MongoClient
from vxutils import vxDict, vxDataClass, logger
from vxutils.convertors import local_tzinfo


class vxMongoDB:
    def __init__(
        self,
        db_uri: str,
        db_name: str,
        collection_mapping: Dict = None,
    ) -> None:
        self._db_conn = MongoClient(
            db_uri, document_class=vxDict, tz_aware=True, tzinfo=local_tzinfo
        )
        self._lock = Lock()
        self._db = self._db_conn.get_database(db_name)
        self._collection_mapping = collection_mapping or {}
        try:
            self._db_conn.admin.command("replSetGetStatus")
            self._is_replica_set = True
        except pymongo.errors.OperationFailure:
            self._is_replica_set = False

    def __getitem__(self, collection_name: str):
        return (
            getattr(self._db_conn, collection_name)
            if collection_name in dir(self._db_conn)
            else self._db[collection_name]
        )

    def __getattr__(self, collection_name: str):
        return (
            getattr(self._db_conn, collection_name)
            if collection_name in dir(self._db_conn)
            else self._db[collection_name]
        )

    @contextlib.contextmanager
    def start_session(
        self,
        causal_consistency=None,
        default_transaction_options=None,
        snapshot=None,
        lock=True,
    ):
        if lock:
            self._lock.acquire()
        try:
            with self._db_conn.start_session(
                causal_consistency, default_transaction_options, snapshot
            ) as session:
                if self._is_replica_set:
                    with session.start_transaction():
                        yield session
                else:
                    yield session
        finally:
            if lock:
                self._lock.release()

    def mapping(
        self,
        collection_name: str,
        doc_class: Any,
        primary_keys: List[str] = None,
    ) -> None:
        """建立collection 和 vxDataClass 映射关系

        Arguments:
            collection_name {str} -- _description_
            doc_class {Type[vxDataClass]} -- _description_
        """
        primary_keys = primary_keys or []
        self._collection_mapping[collection_name] = (doc_class, primary_keys)
        logger.info(
            f"{self.__class__.__name__}: collection({collection_name}) mapping to"
            f" {doc_class.__name__} primary_keys {primary_keys}"
        )

    def query(
        self,
        collection_name: str,
        filter_: dict = None,
        session=None,
        **kwargs,
    ):
        """查询条件

        Arguments:
            collection_name {str} -- collection名称
            filter_ {dict} -- 过滤条件 (default: {None})
            session {_type_} -- db session (default: {None})
        """
        cur = self._db[collection_name].find(
            filter_,
            session=session,
            # cursor_type=pymongo.CursorType.NON_TAILABLE,
            **kwargs,
        )
        if collection_name in self._collection_mapping:
            target_class, _ = self._collection_mapping[collection_name]
            return map(target_class, cur)
        else:
            return cur

    def query_one(
        self, collection_name: str, filter_: dict = None, session=None, **kwargs
    ):
        """查找一个文档对象

        Arguments:
            collection_name {str} -- collection 名称

        Keyword Arguments:
            filter_ {dict} -- 过滤条件 (default: {None})
            session {_type_} -- 数据库session (default: {None})
        """
        item = self._db[collection_name].find_one(filter_, {"_id": 0}, **kwargs)
        if not item or collection_name not in self._collection_mapping:
            return item

        target_class, _ = self._collection_mapping[collection_name]
        return target_class(item)

    def save(
        self,
        collection_name: str,
        vxdata_obj: vxDataClass,
        filter_: Dict = None,
        session=None,
    ) -> None:
        """保存vxdataclass obj

        Arguments:
            collection_name {str} -- 保存的数据表
            vxdata_obj {vxDataClass} -- vxdata实例
            filter_ {Dict} -- 过滤条件 (default: {None})
            session {MongoClient session} -- 数据库session (default: {None})
        """
        if not isinstance(vxdata_obj, vxDataClass):
            raise TypeError(f"vxdata_obj({vxdata_obj} 必须为vxDataClass格式。")

        if collection_name in self._collection_mapping:
            _, primarykey_keys = self._collection_mapping[collection_name]
            filter_ = {key: vxdata_obj[key] for key in primarykey_keys}
            logger.debug(f"{self.__class__.__name__} save vxdata_obj: {vxdata_obj}")
            self._db[collection_name].update_one(
                filter_,
                update={
                    "$set": vxdata_obj.message
                    if hasattr(vxdata_obj, "message")
                    else vxdata_obj
                },
                session=session,
                upsert=True,
            )
        else:
            self._db[collection_name].insert_one(
                vxdata_obj.message if hasattr(vxdata_obj, "message") else vxdata_obj,
                session=session,
            )
        return

    def save_many(
        self, collection_name: str, vxdata_objs: List[vxDataClass], session=None
    ):
        """保存多个对象

        Arguments:
            collection_name {str} -- 表格名称
            vxdata_objs {List[vxDataClass]} -- 对象
            session {_type_} -- 数据库连接对象 (default: {None})
        """
        if collection_name in self._collection_mapping:
            _, primarykey_keys = self._collection_mapping[collection_name]
        else:
            primarykey_keys = []

        commands = []
        for vxdata_obj in vxdata_objs:
            filter_ = {key: vxdata_obj[key] for key in primarykey_keys}
            if filter_:
                cmd = pymongo.UpdateOne(
                    filter_,
                    update={
                        "$set": vxdata_obj.message
                        if hasattr(vxdata_obj, "message")
                        else vxdata_obj
                    },
                    upsert=True,
                )
            else:
                cmd = pymongo.InsertOne(
                    vxdata_obj.message if hasattr(vxdata_obj, "message") else vxdata_obj
                )
            commands.append(cmd)
        if commands:
            self._db[collection_name].bulk_write(
                commands, ordered=False, session=session
            )

    def delete(self, collection_name: str, filter_: Dict, session=None):
        """删除记录

        Arguments:
            collection_name {str} -- 表格名称
            filter_ {Dict} -- 过滤条件
            session {_type_} -- 数据库连接 (default: {None})
        """
        if not filter_:
            raise ValueError("filter 必须指定相应条件，若删除全表内容，请使用turncate方法.")

        self._db[collection_name].delete_many(filter_, session=session)

    def turncate(self, collection_name: str, session=None) -> None:
        """清空整表

        Arguments:
            collection_name {str} -- 表格名称
            session {_type_} -- 数据库连接 (default: {None})
        """
        self._db[collection_name].delete_many({}, session=session)

    def distinct(
        self, collection_name: str, col_name: str, filter_: Dict = None, session=None
    ) -> List:
        """去重后的数值列表

        Arguments:
            collection_name {str} -- 数据表格名称
            col_names {List[str]} -- 去重字段
            filter_ {Dict} -- 过滤条件
            session {_type_} -- 数据库session (default: {None})

        Returns:
            List -- 去重后列表
        """
        filter_ = filter_ or {}
        return self._db[collection_name].distinct(col_name, filter_, session=session)

    def disconnect(self):
        self._db_conn.disconnect()


if __name__ == "__main__":
    import time

    db = vxMongoDB(
        "mongodb://writer:writer18007558228@127.0.0.1:27017/vxcollector", "vxcollector"
    )

    with db.start_session(causal_consistency=True) as session:
        print(
            db.test.count_documents({}),
            db.test2.count_documents({}),
        )
        db.turncate("test")
        db.turncate("test2")
        start = time.perf_counter()

        datas = [vxDict({"name": "test", "cnt": i}) for i in range(100000)]

        # for i in range(100000):
        #    data =
        #    datas.append(data)
        # db.save("test", data)
        # db.test2.update_one({"cnt": i}, {"$set": data}, upsert=True)
        # print(f"save: {data.cnt}")

        print(
            time.perf_counter() - start,
            db.test.count_documents({}),
        )

        db.save_many("test2", datas)
        print(
            "save test2 datas:",
            time.perf_counter() - start,
            db.test2.count_documents({}),
        )

        print("=" * 60)

        cur = db.query("test2", {})

        print(f"total={reduce(lambda x,y: x+y.cnt, cur,0)}")
        print(time.perf_counter() - start)
        print("=" * 60)
        print(f"total={reduce(operator.add, range(10000),0)}")
        print(time.perf_counter() - start)
        print("=" * 60)
        cnts = db.distinct("test2", "cnt")
        print(len(cnts))
        print(time.perf_counter() - start)

    db.close()
    print(time.perf_counter() - start)
