# 命令行（CLI）

本后端提供独立 CLI，通过 `python -m` 入口运行。所有子命令均**实测可行**（下文示例来自对 ClickHouse 26.7 的实际调用）。

```bash
python -m rhosocial.activerecord.backend.impl.clickhouse --help
```

## 通用参数

所有连接类子命令共享：

| 参数 | 默认 | 说明 |
|------|------|------|
| `--host` | `localhost`（env `CLICKHOUSE_HOST`）| ClickHouse 主机 |
| `--port` | **`8123`**（env `CLICKHOUSE_PORT`）| ClickHouse HTTP 端口 |
| `--database` | —（env `CLICKHOUSE_DATABASE`）| 数据库名 |
| `--user` | `root`（env `CLICKHOUSE_USER`）| 用户名 |
| `--password` | —（env `CLICKHOUSE_PASSWORD`）| 密码 |
| `--ssl` | `auto` | SSL 模式：`auto`/`disabled`（HTTP 明文）、`require`（HTTPS 不校验）、`verify-ca`（HTTPS 校验证书）、`verify-full`（HTTPS 校验证书+主机名）。详见 [SSL/TLS 配置](../installation/configuration.md#ssltls)。实测 `require`/`verify-ca`/`verify-full` 对 ClickHouse 26.7 均可用 |
| `--async` | — | **不可用**：ClickHouse 是纯同步后端，传 `--async` 会失败 |
| `--named-connection` | — | 命名连接的 Python 模块限定名（如 `myapp.connections.prod`）|
| `--conn-param KEY=VALUE` | — | 命名连接参数覆盖，可多次 |
| `-o, --output` | `table` | `table`/`json`/`csv`/`tsv` |

## query — 执行 SQL

执行任意 SQL（SELECT 或 DDL），输出格式化结果。SQL 可作位置参数、`-f FILE` 或 stdin。

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse query \
    "SELECT version()" --host localhost --database test_db --user root --password password
[
  {
    "version()": "26.7.3.19"
  }
]
```

专属参数：`-f FILE`（从文件读 SQL）、`--log-level`、`--rich-ascii`。

## info — 环境信息

显示 ClickHouse 环境、版本与**能力矩阵**（各 protocol 支持率）。

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse info \
    --host localhost --database test_db --user root --password password
```

输出含 `capabilities` 块，列出各 `ClickHouseXxxSupport` protocol 的 supported/total/percentage（不支持的能力显示 0%，与 [不支持的功能](../capabilities/unsupported.md) 一致）。

专属参数：`--version`（模拟版本，默认用服务端报告值）、`-v`/`-vv`（详细度，family/details）。

## introspect — 数据库自省

通过 `system.*` 表自省 schema。

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
    --host localhost --database test_db --user root --password password
```

位置参数（自省类型）：`tables`/`views`/`table`/`columns`/`indexes`/`foreign-keys`/`triggers`/`database`。`foreign-keys`/`triggers` 对 ClickHouse 返回空（不支持）。

专属参数：`--schema SCHEMA`、`--include-system`（含系统表）。

## status — 服务器状态

显示服务器状态概览。

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse status databases \
    --host localhost --database test_db --user root --password password
```

位置参数（状态类型）：`all`（默认）/`config`/`performance`/`connections`/`storage`/`databases`/`users`。数据来自 `system.metrics`/`system.processes` 等。

专属参数：`-v`、`--rich-ascii`。

## named-connection — 管理命名连接

列出/查看/预览命名连接配置（来自 Python 模块），**不连库**。

```bash
# 列出模块内所有命名连接
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-connection --list myapp.connections

# 查看详情（脱敏）
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-connection --show myapp.connections.prod_db

# 预览解析后的配置（dry-run）
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-connection --describe myapp.connections.prod_db
```

专属参数：`--list`、`--show`、`--describe`、`--param KEY=VALUE`。

## named-expression — 执行命名表达式

执行核心库 **named-expression 框架**定义的 Python 可调用表达式（按模块限定名查找）。

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-expression \
    myapp.queries.top_users --host localhost --database test_db --user root --password password
```

专属参数：`-e EXAMPLE`、`--describe`、`--dry-run`、`--list`、`--force`、`--explain`、`--dialect-version`、`--param KEY=VALUE`。

## named-procedure — 执行命名过程

执行 **named-expression 框架**的命名过程（Python 类，**非 SQL 存储过程**）。

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-procedure \
    myapp.procedures.monthly_report --host localhost --database test_db --user root --password password \
    --param month=2026-03
```

> ClickHouse 不支持 SQL `CREATE PROCEDURE`/`CALL`（见 [不支持的功能](../capabilities/unsupported.md)）。`named-procedure` 是核心库 Python 层的可调用对象框架，与 SQL 存储过程无关。

专属参数：`--describe`、`--dry-run`、`--list`、`--transaction {auto,step,none}`（注意 ClickHouse 无事务，`--transaction` 仅控制执行编排，不提供回滚）、`--param`。

## named-procedure-graph — 执行命名过程图

执行由多个命名过程组成的过程图（DAG 编排）。参数同 `named-procedure`。

## named-migration — 执行命名迁移

执行命名迁移的 UP/DOWN（核心库迁移框架，DDL 版本管理）。

```bash
$ python -m rhosocial.activerecord.backend.impl.clickhouse named-migration \
    myapp.migrations.create_users --host localhost --database test_db --user root --password password
```

专属参数：`--describe`、`--dry-run`、`--list`、`--force`、`--explain`。

## 测试

CLI 黑盒测试在 `tests/rhosocial/activerecord_clickhouse_test/feature/backend/cli/test_cli_blackbox.py`，CI 已覆盖。

## 下一步

- [连接配置](../installation/configuration.md)
- [测试配置](../testing/README.md)
