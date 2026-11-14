# Directory-bound databases

Every backend-owned test directory runs in its own logical database. The name
is derived from the directory path by `conftest.py` in this directory — nothing
is registered, and no file lists the names:

```
feature/backend/execute/crud  ->  test_backend_execute_crud
```

`feature` is not part of the name; `backend` leads it so the backend-owned
databases are told apart from the feature ones at a glance. The scenario is not
part of the name either: a scenario is a concrete server, so scenarios are
already isolated from each other.

The database is created and cleared **once** per `(directory, scenario)`, on the
first test in that directory that asks for a backend. Every later test in the
same directory against the same scenario reuses it. `feature/backend/conftest.py`
holds the derivation (`_database_for`) and the once-per-pair reset
(`_prepare_database`).

`tests/conftest.py` is not involved; neither is the testsuite. These directories
declare no `prepare` / `teardown` contract because they drive the backend object
directly instead of configuring models, so they never request `environment`.

`--dist=loadgroup` still schedules them safely: `feature/backend/conftest.py`
marks every item under a directory with `xdist_group("clickhouse-backend::<dir>")`,
so a directory runs serially while directories run in parallel.

## `construct/` never opens a connection

The construction directories test rendering only, so they never ask for a
backend and therefore never create a database. `construct/clickhouse/` is a
namespace; its leaf `id_generation/` owns no database for the same reason.

## Directories with tests

| Leaf directory | Database |
|---|---|
| `construct/ddl` | `test_backend_construct_ddl` |
| `construct/dialect` | `test_backend_construct_dialect` |
| `construct/errors` | `test_backend_construct_errors` |
| `construct/expression` | `test_backend_construct_expression` |
| `construct/functions` | `test_backend_construct_functions` |
| `construct/introspection` | `test_backend_construct_introspection` |
| `construct/mixins` | `test_backend_construct_mixins` |
| `construct/statements` | `test_backend_construct_statements` |
| `construct/types` | `test_backend_construct_types` |
| `construct/clickhouse/id_generation` | `test_backend_construct_clickhouse_id_generation` |
| `execute/cli` | `test_backend_execute_cli` |
| `execute/concurrency` | `test_backend_execute_concurrency` |
| `execute/connection` | `test_backend_execute_connection` |
| `execute/crud` | `test_backend_execute_crud` |
| `execute/ddl_column` | `test_backend_execute_ddl_column` |
| `execute/ddl_table` | `test_backend_execute_ddl_table` |
| `execute/dml_insert` | `test_backend_execute_dml_insert` |
| `execute/functions` | `test_backend_execute_functions` |
| `execute/introspection` | `test_backend_execute_introspection` |
| `execute/partition` | `test_backend_execute_partition` |
| `execute/query` | `test_backend_execute_query` |
| `execute/sequence_identity` | `test_backend_execute_sequence_identity` |
| `execute/transaction` | `test_backend_execute_transaction` |
| `execute/clickhouse/column_mapping` | `test_backend_execute_clickhouse_column_mapping` |
| `execute/clickhouse/dialect` | `test_backend_execute_clickhouse_dialect` |
| `execute/clickhouse/native_types` | `test_backend_execute_clickhouse_native_types` |

The `execute/` directories listed in the README as pending hold a `conftest.py`
but no test files yet; they create a database the first time a test lands in
them. `execute/clickhouse/` is a namespace only — it holds no test files and no
database of its own.
