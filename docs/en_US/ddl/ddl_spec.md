# DDL Feature Specs

ClickHouse inherits the core DDL feature-spec claiming protocol
(`dialect.build_spec`) from `SQLDialectBase` — no ClickHouse-specific code is
required for the generic Specs.

## How claiming works

At `Model.generate_create_table(dialect)` time the generator hands each
declared Spec to `dialect.build_spec(spec)`:

- **Accepted** → the dialect builds and returns an expression-layer instance,
  which lands in the `CreateTableExpression`;
- **Not accepted** → returns `None`, and the Spec is silently ignored.

## Generic Specs

All generic Specs are claimed and translated by the core default. Note that
ClickHouse's own table-constraint renderer has engine-specific behavior:
table-level CHECK/UNIQUE constraints may be rejected at render time
(`UnsupportedFeatureError`) even though the Spec itself is claimed and built.

| Spec | ClickHouse translation |
|------|------------------------|
| `CheckSpec` | `TableConstraint(CHECK)` (rendering may fail-fast per engine) |
| `UniqueSpec` | `TableConstraint(UNIQUE)` (rendering may fail-fast per engine) |
| `NotNullSpec` | `ColumnConstraint(NOT NULL)` |
| `PrimaryKeySpec` | column-level PK (single) / table-level composite PK |
| `DefaultSpec` | `ColumnConstraint(DEFAULT)` with a parameterized `Literal` |
| `ForeignKeySpec` | `ForeignKeyConstraint` |
| `IndexSpec` | `IndexDefinition` |
| `JsonColumnSpec` | column type patch → `JsonType` |

## Partitions

ClickHouse's MySQL-style declarative partitioning (`PARTITION BY RANGE/LIST/
HASH ...`) fail-fasts — it is not claimed, and a declared
`__table_partition__` is ignored (a plain table is built). ClickHouse-native
partitioning is part of the table engine configuration; see
[Table engines & sorting key](table_engine.md).
