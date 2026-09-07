# DDL 特征 Spec

ClickHouse 从 `SQLDialectBase` 继承核心 DDL 特征认领协议（`dialect.build_spec`）——
通用 Spec 无需任何 ClickHouse 特定代码。

## 认领机制

`Model.generate_create_table(dialect)` 时，生成器把每个声明的 Spec 交给
`dialect.build_spec(spec)`：

- **接受** → 方言构造并返回表达式层实例，进入 `CreateTableExpression`；
- **不接受** → 返回 `None`，该 Spec 被静默忽略。

## 通用 Spec

全部通用 Spec 由核心默认翻译认领。注意 ClickHouse 自身的表约束渲染器有引擎
相关行为：表级 CHECK/UNIQUE 约束即使 Spec 被认领并构建，渲染时也可能报错
（`UnsupportedFeatureError`）。

| Spec | ClickHouse 翻译 |
|------|-----------------|
| `CheckSpec` | `TableConstraint(CHECK)`（渲染可能按引擎 fail-fast） |
| `UniqueSpec` | `TableConstraint(UNIQUE)`（渲染可能按引擎 fail-fast） |
| `NotNullSpec` | `ColumnConstraint(NOT NULL)` |
| `PrimaryKeySpec` | 单列→列级 PK / 复合→表级 PK |
| `DefaultSpec` | `ColumnConstraint(DEFAULT)`，参数化 `Literal` |
| `ForeignKeySpec` | `ForeignKeyConstraint` |
| `IndexSpec` | `IndexDefinition` |
| `JsonColumnSpec` | 列类型补丁 → `JsonType` |

## 分区

ClickHouse 的 MySQL 式声明分区（`PARTITION BY RANGE/LIST/HASH ...`）
fail-fast——不被认领，声明的 `__table_partition__` 被忽略（建普通表）。
ClickHouse 原生分区属于表引擎配置的一部分；见
[表引擎与排序键](table_engine.md)。
