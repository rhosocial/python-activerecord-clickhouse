# 分区维护

ClickHouse 只有**单层分区**。MergeTree 家族在 `CREATE TABLE` 中通过
`PARTITION BY <expr>` 声明分区键（见[表引擎与排序键](table_engine.md)），
第一条落入某个键值的行会创建对应分区。ClickHouse 没有 `SUBPARTITION BY`，
没有具名的 `PARTITION ... VALUES LESS THAN` 边界，因此也不存在分区树：
一张表的所有分区都是同级，按服务器从键表达式推导、并在
`system.parts.partition_id` 中报告的 id 来寻址。

因此 `ALTER TABLE` 只有三个维护动词：

```sql
ALTER TABLE visits DROP PARTITION ID '202601';
ALTER TABLE visits DETACH PARTITION ID '202601';
ALTER TABLE visits ATTACH PARTITION ID '202601';
```

后端通过 `backend.partition_maintenance` 提供这三个动词，以及保留策略真正
需要的读取入口。该服务不内置任何表名或保留策略：维护哪些表、保留多久，
属于应用层的决定。

## 列出分区

`list()` 返回自省器（introspector）的结果——每个分区 id 一条
`ClickHousePartitionInfo`，只聚合 active part——因此两个入口不会给出不同答案：

```python
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host="localhost", port=8123, database="analytics",
    username="root", password="password",
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()

service = backend.partition_maintenance
for partition in service.list("visits"):
    print(partition.partition_id, partition.partition, partition.row_count)
```

`partition_id` 正是三个维护方法接收的值。`partition` 是可读的键值
（对 `toYYYYMM(created_at)` 而言是 `'202601'`）；没有 `PARTITION BY` 的表
只有唯一的 `'all'` 分区。传 `database` 可显式指定 ClickHouse 数据库，
省略时使用当前连接的数据库。

自省器会缓存这份列表。如果分区是在助手之外被改动的——例如直接通过
`backend.execute` 执行原始 `ALTER TABLE`，或同一服务器上的另一个进程——
请传 `refresh=True` 重新读取服务器：

```python
service.list("visits", refresh=True)
```

## 删除、分离与重新附加

```python
service.drop("visits", "202601")     # 删除分区及其数据
service.detach("visits", "202601")   # 移到一边，数据仍保留在磁盘上
service.attach("visits", "202601")   # 把分离的分区重新接回
```

`drop` 正是分区存在的意义：服务器把该分区的 part 标记为 inactive 并在后台
删除，而不是逐行删除。`detach` 与 `attach` 是一对：后者从表的 `detached/`
目录读回分区并把行归还给表。一次助手调用就是一条语句，因为 ClickHouse 没有
事务；分区变更成功后还会清除该表的自省缓存，使下一次 `list()` 描述服务器
当前的真实状态。

如果调用方把动词保存在配置中，可以按名称分派：

```python
service.execute("detach", "visits", "202601")
```

## ClickHouse 没有的能力

上面的三个动词就是完整清单。不存在 `ADD PARTITION`，因为分区随第一条行
自动产生；`TRUNCATE PARTITION` 的替代写法是
`ALTER TABLE ... DELETE IN PARTITION ID ... WHERE ...`；也不存在
`REORGANIZE`、`EXCHANGE`、`COALESCE`、`REMOVE PARTITIONING` 或
`SUBPARTITION BY`。`execute()` 对其他任何动词抛出 `UnsupportedFeatureError`，
dialect 的能力开关也给出同样的答案：
`supports_subpartitioning()`、`supports_range_table_partitioning()`、
`supports_list_table_partitioning()`、`supports_hash_table_partitioning()`
均为 `False`，而 `supports_drop_partition()`、`supports_detach_partition()`、
`supports_attach_partition()` 为 `True`。这里不做任何模拟，也不会渲染服务器
会拒绝的语句。

> ⚠️ 分区 id 由服务器分配。这些助手只作用于已经存在的分区；ClickHouse
> 无法预先创建一个空分区。某个键值第一次写入时会自动产生对应分区，
> 因此写路径之前没有 `ensure()` 需要调用。
