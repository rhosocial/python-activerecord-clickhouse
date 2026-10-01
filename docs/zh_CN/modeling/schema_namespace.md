# ClickHouse 后端中的 schema 名称

> ClickHouse 没有 schema 命名空间。`schema_name` 仍然被接受，但它指的是一个
> **database**。本页存在的理由是：这里最容易让读者的"schema"直觉出错。

## `schema_name` 在这里指什么

`supports_schema()` 返回 `True`，这个值也确实可用 —— 只是它下面没有 schema 层。

| | PostgreSQL | ClickHouse |
|---|---|---|
| `supports_schema()` | `True` | `True` |
| `schema_name` 指向 | schema | **database** |
| `CREATE SCHEMA` | 可用 | **语法错误** |
| `SHOW SCHEMAS` | 可用 | 不存在 |
| 当前 schema 函数 | `current_schema()` | `currentDatabase()` |
| 渲染结果 | `"app"."orders"` | `` `app`.`orders` `` |

ClickHouse 自己书写限定引用就是 `` `db`.`orders` ``，所以传 `schema_name="app"`
得到的正是这个形式，服务端会接受。

## 如何声明

```python
class Order(ActiveRecord):
    __schema_name__ = "app"   # 这是 database
    __tablename__ = "orders"
```

```sql
-- 生成
SELECT * FROM `app`.`orders`
```

## 两个容易踩的坑

**不存在 `CREATE SCHEMA`。** 写一条创建 schema 的迁移会在服务端失败。
请改为创建 database：

```sql
CREATE DATABASE app
```

**`schema` 在这里不是 `database` 的同义词。** MySQL 与 MariaDB 接受
`CREATE SCHEMA` 作为 `CREATE DATABASE` 的别名，ClickHouse 没有这个别名。
所以为 MySQL 写的迁移无法直接移植过来。

## 查询服务端当前所在的 database

`get_current_schema()` 返回当前 database。名字是共享 API，读的却是 database。

```python
backend.get_current_schema()   # 'default'
```

只有同步 backend。clickhouse-connect 是同步专用库，因此没有 async 版本可调用。

## 列引用从不带 schema

虽然表引用在这里是两段式，列引用最多也是两段，所以 schema 部分不会重复出现：

```sql
SELECT `orders`.`id` FROM `app`.`orders`
```

表被限定，列没有。这与 MySQL 遵循同一条规则，原因也相同：三段式列引用是语法错误。

## 传了 schema 但用不了时

这里不会拒绝 `schema_name`，因为 database 是这个方言能够表达的真实命名空间。
如果你连接到的服务端不存在该 database，错误来自服务端执行语句的那一刻，
而不是框架构造语句的那一刻。

## 相关

- [不支持的功能](capabilities/unsupported.md) —— ClickHouse 直接拒绝什么，
  以及与本文这种情况的区别
- 核心库指南：核心库的 `docs/modeling/schema_namespace.md`，含跨后端对照表
