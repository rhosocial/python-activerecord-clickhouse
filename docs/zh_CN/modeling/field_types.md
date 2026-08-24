# 字段类型映射

ClickHouse 是强类型列式数据库，每个列都有精确的类型。本后端在 Python 类型与 ClickHouse 列类型之间建立映射。

## 基本映射

| Python 类型 | ClickHouse 列类型 | 说明 |
|------------|-------------------|------|
| `int`（主键） | `Int64` | 主键由雪花算法生成，固定 `Int64` |
| `int`（普通） | `Int32` | 有符号 32 位 |
| `int`（大范围） | `Int64` | 显式注解 `int64` 即可 |
| `float` | `Float64` | 双精度浮点 |
| `str` | `String` | 不限长字符串 |
| `bool` | `Bool` | `UInt8` 的别名（ClickHouse 21+ 原生 `Bool`）|
| `bytes` | `String` | 字节流以 `String` 存储 |
| `datetime.datetime` | `DateTime64(6)` | 微秒精度时间戳 |
| `datetime.date` | `Date` | 日期 |
| `decimal.Decimal` | `Decimal(p, s)` | 需指定精度与标度 |
| `uuid.UUID` | `UUID` | 原生 UUID |
| `ipaddress.IPv4Address` | `IPv4` | 原生 IPv4 |
| `ipaddress.IPv6Address` | `IPv6` | 原生 IPv6 |

## 复合类型

ClickHouse 的列式复合类型是它的强项：

| Python 形态 | ClickHouse 列类型 | 示例 |
|------------|-------------------|------|
| `list[int]` | `Array(Int32)` | 标签数组 |
| `list[float]` | `Array(Float32)` | 嵌入向量（替代 MySQL `VECTOR`，配合 `L2Distance`） |
| `list[str]` | `Array(String)` | 字符串数组 |
| `dict[str, str]` | `Map(String, String)` | 键值映射 |
| `dict[str, int]` | `Map(String, Int32)` | 计数器映射 |
| `tuple` | `Tuple(...)` | 固定结构元组 |
| `enum.Enum` | `Enum8` / `Enum16` | 枚举（8/16 位）|

## 特殊类型

| ClickHouse 类型 | 用途 | 备注 |
|----------------|------|------|
| `Nullable(T)` | 允许 NULL 的 `T` | 见 [Nullable 与可选字段](nullable.md) |
| `LowCardinality(T)` | 低基数去重存储 | 枚举值少时显著降存储/提速 |
| `FixedString(N)` | 定长字符串 | 如定长 code |
| `JSON` | 原生 JSON 类型 | 配合 `JSONExtract*` 查询 |
| `Date32` | 1970–2149 日期范围 | 比 `Date` 范围大 |
| `Decimal32/64/128` | 定点数 | 按范围选位宽 |

## 在模型上声明类型

ActiveRecord 模型用 Pydantic 注解声明字段，后端据此推断 ClickHouse 列类型：

```python
from typing import Optional
from pydantic import Field
from rhosocial.activerecord.model import ActiveRecord

class Event(ActiveRecord):
    __table_name__ = "events"
    __primary_key__ = "id"

    id: Optional[int] = None                  # Int64 (雪花 id)
    user_id: int                              # Int32
    amount: float                              # Float64
    tags: list[str]                            # Array(String)
    counters: dict[str, int]                   # Map(String, Int32)
    created_at: Optional["datetime"] = None   # Nullable(DateTime64)
```

> 💡 *AI 提示词："ClickHouse 的 `LowCardinality(String)` 相比 `String` 有什么收益？什么时候不该用它？"*

## 不支持的类型（快速失败）

以下 MySQL/其他数据库的类型**不在** ClickHouse 后端暴露，相关表达式会 fail-fast：

- 空间类型：`GEOMETRY`/`POINT`/`LINESTRING`/`POLYGON`/... → 存 WKT 为 `String`
- `VECTOR`（MySQL 9.0）→ `Array(Float32)` + `L2Distance`
- `SET` → `Enum16` 或 `Array(String)`
- `BLOB`/`TEXT`（MySQL）→ `String`

## 下一步

- [Nullable 与可选字段](nullable.md)
- [JSON 查询](../querying/json.md)
