# 变更（UPDATE/DELETE）

ClickHouse 的 UPDATE/DELETE 与 OLTP 不同。本后端生成 ClickHouse 的**轻量级变更（lightweight updates/deletes）**——`UPDATE ... WHERE` / `DELETE ... WHERE` 语法，而非传统 `ALTER TABLE ... UPDATE` 异步 mutation。

## 生成的 SQL

本后端在 UPDATE/DELETE 路径生成的 SQL 形如：

```sql
UPDATE `users` SET `age` = ? WHERE `id` = ?
DELETE FROM `users` WHERE `id` = ?
```

后端在执行时附 `mutations_sync=1` 会话设置以兼容传统 mutation 语义，但 lightweight update 本身是同步的。

## ⚠️ 前置设置：默认被拒绝

ClickHouse 26.x **默认拒绝**轻量级 UPDATE/DELETE，直接执行会报：

```
Code: 48. DB::Exception: Lightweight updates are not supported.
Lightweight updates are supported only for tables with materialized
_block_number column. Run 'MODIFY SETTING enable_block_number_column = 1'
command to enable it. (NOT_IMPLEMENTED)
```

要启用本后端的 `save()`（UPDATE）与 `delete()`，建表时**必须**加：

```sql
CREATE TABLE users (...) ENGINE = MergeTree ORDER BY (...)
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
```

或建表后补：

```sql
ALTER TABLE users MODIFY SETTING
  enable_block_number_column = 1,
  enable_block_offset_column = 1;
```

> 💡 *AI 提示词："为什么 ClickHouse 默认禁用轻量级 UPDATE？`_block_number`/`_block_offset` 列起什么作用？"*

## affected_rows 语义

| 操作 | `affected_rows` |
|------|----------------|
| INSERT | `0`（ClickHouse 不报告插入行数；实际插入数需另行 `count()`）|
| UPDATE | WHERE 匹配行的预计数（pre-counted）|
| DELETE | WHERE 匹配行的预计数 |

```python
alice.age = 31
r = alice.save()           # UPDATE，affected_rows = 1（匹配行）
bulk = User.bulk_delete(to_delete)   # affected_rows = 匹配行预计数
```

ClickHouse 无法在 lightweight 执行时精确报告"实际改了几行"，只能报告 WHERE 匹配数。若需精确计数，应在变更前后各查一次 `count()` 对比。

## 单个 vs 批量变更

```python
# 单个：实例方法
alice.save()         # UPDATE
alice.delete()       # DELETE

# 批量：类方法（先查询得实例列表）
to_delete = User.query().where(User.c.age < 18).all()
User.bulk_delete(to_delete)

to_upsert = [User(...) for ...]
User.bulk_insert(to_upsert)
```

> `ActiveQuery` 是只读（DQL），**没有** `delete()`/`update()`。批量变更走 `Model.bulk_insert`/`bulk_delete` 类方法。

## 变更的代价与替代

| 操作 | 代价 | 替代 |
|------|------|------|
| UPDATE 少量行 | 重写受影响 part | `ReplacingMergeTree` 写新版本，合并时去重 |
| DELETE 少量行 | 标记删除，等待 merge | `CollapsingMergeTree` + sign 标记 |
| 大批量 DELETE | 按 partition drop | `ALTER TABLE ... DROP PARTITION` |

## 排序键列不可更新

`ORDER BY` 列（即主键排序键）**不能** 被 UPDATE 修改——会抛错。如需改主键列，只能删旧行插新行（或重建表）。

## 事务不存在

各 UPDATE/DELETE 独立执行，无跨语句事务。`transaction()` 是空操作上下文管理器，rollback 不撤销已完成的变更。详见 [能力边界](../introduction/capability_boundaries.md)。

## 下一步

- [不支持的功能](unsupported.md)
- [表引擎与排序键](../ddl/table_engine.md)
