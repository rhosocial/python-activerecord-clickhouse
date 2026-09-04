# Command Line (CLI)

This backend provides a standalone CLI, run via the `python -m` entry point. All subcommands are **measured and working** (the examples below come from actual calls against ClickHouse 26.7).

```bash
python -m rhosocial.activerecord.backend.impl.clickhouse --help
```

## Common arguments

All connection-type subcommands share:

| Argument | Default | Description |
|------|------|------|
| `--host` | `localhost` (env `CLICKHOUSE_HOST`) | ClickHouse host |
| `--port` | **`8123`** (env `CLICKHOUSE_PORT`) | ClickHouse HTTP port |
| `--database` | — (env `CLICKHOUSE_DATABASE`) | database name |
| `--user` | `root` (env `CLICKHOUSE_USER`) | username |
| `--password` | — (env `CLICKHOUSE_PASSWORD`) | password |
| `--ssl` | `auto` | SSL mode: `auto`/`disabled` (HTTP plaintext), `require` (HTTPS no verification), `verify-ca` (HTTPS verify certificate), `verify-full` (HTTPS verify certificate+hostname). See [SSL/TLS configuration](../installation/configuration.md#ssltls). Measured: `require`/`verify-ca`/`verify-full` all work against ClickHouse 26.7 |
| `--async` | — | **not available**: ClickHouse is a purely synchronous backend; passing `--async` fails |
| `--named-connection` | — | Python module qualified name of a named connection (e.g., `myapp.connections.prod`) |
| `--conn-param KEY=VALUE` | — | named connection parameter override; can be repeated |
| `-o, --output` | `table` | `table`/`json`/`csv`/`tsv` |

## query — execute SQL

Execute arbitrary SQL (SELECT or DDL) and output formatted results. SQL can be a positional argument, `-f FILE`, or stdin.

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse query \
    "SELECT version()" --host localhost --database test_db --user root --password password
[
  {
    "version()": "26.7.3.19"
  }
]
```

Specific arguments: `-f FILE` (read SQL from file), `--log-level`, `--rich-ascii`.

## info — environment information

Display ClickHouse environment, version, and the **capability matrix** (support rate per protocol).

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse info \
    --host localhost --database test_db --user root --password password
```

The output contains a `capabilities` block listing supported/total/percentage for each `ClickHouseXxxSupport` protocol (unsupported capabilities show 0%, consistent with [Unsupported features](../capabilities/unsupported.md)).

Specific arguments: `--version` (simulated version; defaults to the server-reported value), `-v`/`-vv` (verbosity: family/details).

## introspect — database introspection

Introspect the schema via `system.*` tables.

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
    --host localhost --database test_db --user root --password password
```

Positional argument (introspection type): `tables`/`views`/`table`/`columns`/`indexes`/`foreign-keys`/`triggers`/`database`. `foreign-keys`/`triggers` return empty for ClickHouse (not supported).

Specific arguments: `--schema SCHEMA`, `--include-system` (include system tables).

## status — server status

Display a server status overview.

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse status databases \
    --host localhost --database test_db --user root --password password
```

Positional argument (status type): `all` (default)/`config`/`performance`/`connections`/`storage`/`databases`/`users`. Data comes from `system.metrics`/`system.processes` etc.

Specific arguments: `-v`, `--rich-ascii`.

## named-connection — manage named connections

List/view/preview named connection configurations (from Python modules), **without connecting to the database**.

```bash
# 列出模块内所有命名连接
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-connection --list myapp.connections

# 查看详情（脱敏）
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-connection --show myapp.connections.prod_db

# 预览解析后的配置（dry-run）
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-connection --describe myapp.connections.prod_db
```

Specific arguments: `--list`, `--show`, `--describe`, `--param KEY=VALUE`.

## named-expression — execute named expressions

Execute Python callable expressions defined by the core library's **named-expression framework** (looked up by module qualified name).

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-expression \
    myapp.queries.top_users --host localhost --database test_db --user root --password password
```

Specific arguments: `-e EXAMPLE`, `--describe`, `--dry-run`, `--list`, `--force`, `--explain`, `--dialect-version`, `--param KEY=VALUE`.

## named-procedure — execute named procedures

Execute named procedures of the **named-expression framework** (Python classes, **not SQL stored procedures**).

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-procedure \
    myapp.procedures.monthly_report --host localhost --database test_db --user root --password password \
    --param month=2026-03
```

> ClickHouse does not support SQL `CREATE PROCEDURE`/`CALL` (see [Unsupported features](../capabilities/unsupported.md)). `named-procedure` is the core library's Python-layer callable object framework and is unrelated to SQL stored procedures.

Specific arguments: `--describe`, `--dry-run`, `--list`, `--transaction {auto,step,none}` (note: ClickHouse has no transactions; `--transaction` only controls execution orchestration and does not provide rollback), `--param`.

## named-procedure-graph — execute named procedure graphs

Execute a procedure graph composed of multiple named procedures (DAG orchestration). Arguments are the same as `named-procedure`.

## named-migration — execute named migrations

Execute the UP/DOWN of a named migration (core library migration framework, DDL version management).

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-migration \
    myapp.migrations.create_users --host localhost --database test_db --user root --password password
```

Specific arguments: `--describe`, `--dry-run`, `--list`, `--force`, `--explain`.

## Testing

CLI black-box tests are in `tests/rhosocial/activerecord_clickhouse_test/feature/backend/cli/test_cli_blackbox.py` and are covered by CI.

## Next steps

- [Connection configuration](../installation/configuration.md)
- [Test configuration](../testing/README.md)
