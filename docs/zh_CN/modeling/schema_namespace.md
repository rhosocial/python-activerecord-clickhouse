# ClickHouse 后端里的 schema 名称

ClickHouse 没有 schema 这一层。`schema_name` 照样能用，但它指的是 database。

跨后端迁移时这里最容易出错：MySQL 和 MariaDB 也管 database 叫 schema，代码
看起来一样，含义却不是一回事。

## `schema_name` 指的是 database

`supports_schema()` 返回 `True`，值也真能用——只是它指的是 database，不是 schema。

| | PostgreSQL | ClickHouse |
|---|---|---|
| `supports_schema()` | `True` | `True` |
| `schema_name` 指向 | schema | **database** |
| `CREATE SCHEMA` | 可用 | **语法错误** |
| `SHOW SCHEMAS` | 可用 | 没这个命令 |
| 取当前值的函数 | `current_schema()` | `currentDatabase()` |
| 渲染结果 | `"app"."orders"` | `` `app`.`orders` `` |

ClickHouse 自己写限定引用就是 `` `db`.`orders` ``，所以传 `schema_name="app"`
生成的就是这个形式，服务端能接受。

## 声明方式

```python
class Order(ActiveRecord):
    __schema_name__ = "app"   # 这是 database
    __tablename__ = "orders"
```

```sql
-- 生成的 SQL
SELECT * FROM `app`.`orders`
```

## 两个坑

**没有 `CREATE SCHEMA` 这条语句。** 迁移里写它会在服务端报错，改成建 database：

```sql
CREATE DATABASE app
```

**`schema` 不是 `database` 的别名。** MySQL 和 MariaDB 接受 `CREATE SCHEMA` 作为
`CREATE DATABASE` 的别名，ClickHouse 没有。所以为 MySQL 写的迁移搬不过来。

## 取当前 database

`get_current_schema()` 返回当前 database——方法名是统一的 API，读的却是 database。

```python
backend.get_current_schema()   # 'default'
```

只有同步版本。clickhouse-connect 只支持同步，没有对应的 async backend。

## 列引用不带 schema

表引用是两段式，列引用最多也是两段，所以 schema 不会出现第二次：

```sql
SELECT `orders`.`id` FROM `app`.`orders`
```

表带限定，列不带。这条规则和 MySQL 一样，理由也一样：三段式的列引用是语法错误。

## database 不存在时

框架不会拦你。database 是 ClickHouse 自己就能表达的命名空间，所以传了照传；
等语句发过去，服务端发现没有这个 database，才会报错。

## 相关

- [不支持的功能](capabilities/unsupported.md) —— ClickHouse 直接拒绝的东西，
  以及它们和本文这种情况的区别
- 核心库的 `docs/modeling/schema_namespace.md` —— 跨后端对照表