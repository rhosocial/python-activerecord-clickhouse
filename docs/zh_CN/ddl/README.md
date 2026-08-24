# DDL

本节说明 ClickHouse 的表结构定义，重点是 MergeTree 家族与排序键。

- [表引擎与排序键](table_engine.md)：`ENGINE`、`ORDER BY`、`PARTITION BY`、`TTL`
- [跳数索引](skip_indexes.md)：`INDEX ... USING` skip indexes

> ⚠️ ClickHouse 的 `ORDER BY` 既是排序键也是主键索引，与 OLTP 数据库的"主键 = 唯一约束"语义不同。主键列**不可更新**。
