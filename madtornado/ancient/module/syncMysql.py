from ..rig import genSQL
from ..conf import parser

import pymysql

from typing import List, Tuple, Dict, TypeVar, Any, overload

SQL_CONTENT = TypeVar("SQL_CONTENT", int, float, str, bool)

option = parser.options("db")
print("[syncMysql] is imported.")


class Component:
    """

    该模块参数均来源与madtornado配置文件，并且不支持同时连接多个不同的数据库

    安全建议::

        永远不要相信用户输入内容，sql模块虽然对于value进行了预检测
        但是对于key部分还是无能为力，所以一定不要让用户对key的部分有
        任何操作，只基于用户提供value值的权限，这样做是安全的。

    """

    def __init__(self):
        self.conn = None
        self.cur = None
        self.is_return_dict = False
        self.switch = False

    def __enter__(self):
        self.on()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.off()

    def set_cursor_dict(self, is_return_dict: bool = True) -> None:
        """

        设置是否返回字典格式而非数组格式的数据对象

        :param is_return_dict: 是否返回字典格式数据
        :return: None

        """
        self.is_return_dict = is_return_dict
        self.cur = self.conn.cursor(pymysql.cursors.DictCursor if is_return_dict else None)

    def on(self) -> None:
        """

        开启一个数据库实例从sql_pool当中

        举例::

            db=Component()
            db.on()
            db.select_tw("table")
            db.off()

        快捷使用方法::

            with Component() as db:
                db.select_tw("table")

        :return: None

        """
        self.conn = pymysql.connect(host=option["host"], db=option["db"],
                                    user=option["user"], password=option["password"],
                                    port=int(option["port"]), charset=option["charset"])
        self.set_cursor_dict()
        self.switch = True

    def off(self) -> None:
        """

        关闭一个数据库连接实例

        :return: None

        """
        if self.switch:
            self.switch = False
            self.cur.close()
            self.conn.close()

    def output_sql(
            self,
            sql: str,
            arg_list: List[SQL_CONTENT] = None
    ) -> Tuple:
        """

        输出查询内容，直接传入select的sql语句，用于查询

        :param sql: select开头的sql语句
        :param arg_list: 预处理参数，如果需要预处理查询，需要在sql语句中使用%s作为占位符
        :return: 查询到的结果内容

        """
        self.cur.execute(sql, arg_list)
        result = self.cur.fetchall()
        self.conn.commit()
        return result

    @overload
    def input_sql(
            self,
            sql: str,
            arg_list: List[SQL_CONTENT] = None,
            many: bool = False
    ) -> genSQL.InputResult:
        ...

    @overload
    def input_sql(
            self,
            sql: str,
            arg_list: List[List[SQL_CONTENT]] = None,
            many: bool = True
    ) -> genSQL.InputResult:
        ...

    def input_sql(self, sql, arg_list=None, many=False) -> genSQL.InputResult:
        """

        执行插入，更新，删除等输入系列的sql语句

        :param sql: 输入系列的sql语句
        :param arg_list: 预处理参数列表，可以是二维数组代表多行插入前提需要设置many参数
        :param many: 是否启用多行输入
        :return: genSQL.InputResult 输入语句查询信息

        """
        ir = genSQL.InputResult()
        try:
            if many:
                affect = self.cur.executemany(sql, arg_list)
            else:
                affect = self.cur.execute(sql, arg_list)
        except Exception as e:
            self.conn.rollback()
            ir.status = False
            ir.err_info = e
        else:
            self.conn.commit()
            ir.affect = affect
            ir.last_rowid = self.cur.lastrowid
        return ir

    def select_tcw(
            self,
            table: str,
            field: Tuple[str, ...] = ("*",),
            where: str = None,
            where_arg: List[SQL_CONTENT] = None
    ) -> Tuple:
        """

        简化版的查询，用于快捷查询表格内容，不支持连表等高端操作

        :param table: 查询的表格名称
        :param field: 一个元组，代表要查询的字段名称
        :param where: 一个字符串，代表where条件筛选部分，如id=1 and name=a，可以在其中使用占位符，同时要提供where_arg
        :param where_arg: 如果where传入的字符串包括占位符，那么传入参数列表，让sql可以预查询
        :return: Tuple 查询到的结果内容

        """
        return self.output_sql(genSQL.select_tcw(table, field, where), where_arg)

    @overload
    def insert_tc(
            self,
            table: str,
            content: List[SQL_CONTENT],
            many: bool = False
    ) -> genSQL.InputResult:
        ...

    @overload
    def insert_tc(
            self,
            table: str,
            content: List[List[SQL_CONTENT]],
            many: bool = True
    ) -> genSQL.InputResult:
        ...

    @overload
    def insert_tc(
            self,
            table: str,
            content: Dict[str, SQL_CONTENT],
            many: bool = False
    ) -> genSQL.InputResult:
        ...

    @overload
    def insert_tc(
            self,
            table: str,
            content: Dict[str, List],
            many: bool = True
    ) -> genSQL.InputResult:
        ...

    def insert_tc(self, table, content, many=False) -> genSQL.InputResult:
        """

        简化版的插入数据，只能简单的插入数据

        示例内容::

            insert_tc("table", [1, 2, 3, 4, 5])
            转换内容 ： ('insert into table values(%s,%s,%s,%s,%s)', [1, 2, 3, 4, 5])

            insert_tc("table", [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]], many=True, ph="?")
            转换内容 ： ('insert into table values(?,?,?,?,?)', [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]])

            insert_tc("table", {"id": 12, "name": "SystemLight"}, many=False, ph="%s")
            转换内容 ： ('insert into table(name,id) values(%s,%s)', ['SystemLight', 12])

            insert_tc("table", {"key": ["id", "name"], "value": [["1", "lisys"], ["2", "sl"]]}, many=True, ph="%s")
            转换内容 ： ('insert into table(id,name) values(%s,%s)', [['1', 'lisys'], ['2', 'sl']])

        :param table: 表格的名称
        :param content: 支持四中格式传参，参考示例内容
        :param many: 是否启用多行插入
        :return: genSQL.InputResult结果信息对象

        """
        sql, content = genSQL.insert_tc(table, content, many)
        return self.input_sql(sql, content, many)

    @overload
    def insert_update_tc(
            self,
            table: str,
            content: Dict[str, SQL_CONTENT],
            many: bool = False
    ) -> genSQL.InputResult:
        ...

    @overload
    def insert_update_tc(
            self,
            table: str,
            content: Dict[str, List],
            many: bool = False
    ) -> genSQL.InputResult:
        ...

    def insert_update_tc(self, table, content, many=False) -> genSQL.InputResult:
        """

        简化版的插入即更新，这是mysql的特性方法，存在则更新数据，不存在则插入一条新数据

        :param table: 数据表名称
        :param content: 支持dict多行模式{"key":[],"value":[[]]}，和dict当行模式传参
        :param many: 是否启用多行模式
        :return: genSQL.InputResult结果信息对象

        """
        sql, content = genSQL.insert_update_tc(table, content, many)
        return self.input_sql(sql, content, many)

    def update_tcw(
            self,
            table: str,
            content: Dict[str, Any],
            where: str = None,
            where_arg: List[SQL_CONTENT] = None
    ) -> genSQL.InputResult:
        """

        简化版的更新数据

        :param table: 数据表名称
        :param content: 字典对象，键值对相对应
        :param where: 一个字符串，代表where条件筛选部分，如id=1 and name=a，可以在其中使用占位符，同时要提供where_arg
        :param where_arg: 如果where传入的字符串包括占位符，那么传入参数列表，让sql可以预查询
        :return: genSQL.InputResult结果信息对象

        """
        sql, arg_list = genSQL.update_tcw(table, content, where, where_arg)
        return self.input_sql(sql, arg_list)

    def delete_tw(
            self,
            table: str,
            where: str = None,
            where_arg: List[SQL_CONTENT] = None
    ) -> genSQL.InputResult:
        """

        简化版的删除数据

        :param table: 数据表名称
        :param where: 如果该项不填，则删除整个表格，一个字符串，代表where条件筛选部分，如id=1 and name=a
        :param where_arg: 如果where传入的字符串包括占位符，那么传入参数列表，让sql可以预查询
        :return: genSQL.InputResult结果信息对象

        """
        sql = genSQL.delete_tw(table, where)
        return self.input_sql(sql, where_arg)

    def truncate_t(self, table: str) -> genSQL.InputResult:
        """

        快速清空表格数据

        :param table: 数据表名称
        :return: genSQL.InputResult结果信息对象

        """
        code1, code2, code3 = genSQL.truncate_t(table)
        self.input_sql(code1)
        ir = self.input_sql(code2)
        self.input_sql(code3)
        return ir
