# ClickHouse 后端的迁移

> **范围**：本章只讲在 ClickHouse 后端上运行 ActiveRecord 迁移时**特有**的事项。迁移系统本身——装饰器、执行器、版本记录、dry run、依赖校验、`migrate` 与 `named-migration` 命令行——都在核心库的
> [迁移章节](https://github.com/rhosocial/python-activerecord/blob/main/docs/zh_CN/migration/README.md)中说明。
> 请先阅读那一章；本章以其为前提。可运行的脚本位于
> [`docs/examples/migration/`](../../examples/migration/README.md)。

## 1. 仅支持同步——没有异步迁移

`clickhouse-connect` 是纯同步驱动。`ClickHouseBackend` 是真正的后端；`AsyncClickHouseBackend`
只是一个占位类，实例化时会抛出 `NotImplementedError`。因此：

- 使用 `run_migration_group`、`MigrationRunner` 和 `BatchMigrationRunner`。**不要**使用
  `run_migration_group_async` 或 `AsyncMigrationRunner`。
- 不要设置 `@migration(async_variant=...)`——同步函数在这里没有对应的异步伙伴。
- 不要给 `named-migration` 命令行传 `--async`；它会尝试构建占位后端并快速失败。
- `transaction_mode` 对回滚没有任何影响（见下面两节）。

## 2. 为迁移配置后端

```python
import os
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
    database=os.getenv("CLICKHOUSE_DATABASE", "test_db"),
    username=os.getenv("CLICKHOUSE_USER", "root"),
    password=os.getenv("CLICKHOUSE_PASSWORD", "password"),
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()  # negotiate server version and support switches
```

`ClickHouseConnectionConfig` 还带有 `settings`、`compress`、`connect_timeout`、
`send_receive_timeout`，以及 SSL/连接池/字符集/时区选项。当 DDL 依赖某些服务端参数时，
`settings` 就是放置 `mutations_sync` / `alter_sync` 这类参数的地方。连接也可以来自命名连接，
或来自模型的 `configure(config, ClickHouseBackend)`；两个命令行都接受常规的
`--host/--port/--database/--user/--password` 参数。

## 3. DDL 非事务性且自动生效

ClickHouse 没有 ACID 事务：`backend.transaction()` 退化为无操作的上下文管理器。迁移组外并没有
BEGIN/COMMIT/ROLLBACK 包裹。

- 每条语句在服务端接受后立即生效；没有可中止的"待提交"批次。
- 如果组中第三个函数失败，前两个已经改了表结构。执行器不会为失败的版本写版本记录——但这
  并不会撤销任何东西。你必须手工核对并修复现网表结构。
- 版本记录只是记账；修改它永远无法回滚 DDL。
- 实际结论：总是先用 `dry_run=True` 预览（见 §6）。

## 4. 许多 ALTER / MUTATION 语句是异步的

`CREATE` 和 `DROP` 基本是立即生效的，但 `ALTER TABLE ...` 与改动数据的 MUTATION 语句由
ClickHouse 排队执行。服务端可能在变更尚未完全应用到所有 part 和副本之前就返回成功。本后端自身
的 UPDATE/DELETE 路径强制使用 `mutations_sync=1`，但该设置并不自动覆盖迁移函数发出的任意 DDL。

因此，"迁移成功"（写入了版本记录，`result.applied == ["v..."]`）意味着**"语句已被接受"**，
而不是**"表结构或数据已经稳定"**。如果后续步骤依赖新列或新分区在所有地方都已就位：

- 在 `ClickHouseConnectionConfig.settings` 中设置相关的同步参数（例如 `mutations_sync`、
  `alter_sync`），或用 `SYSTEM` 命令显式等待，并且
- 在继续之前通过 `system.*` 自省进行确认。

把这些后续检查放在同一个迁移函数里，使其成为被记录步骤的一部分；并用表达式节点来组合 SQL，
而不要做字符串拼接（参见 [DDL 章节](../ddl/README.md)）。

## 5. 没有回滚——DOWN 是补偿语句

由于 DDL 无法回滚，`DOWN` 不是撤销操作，而是一个用于恢复到先前形态的新的正向动作。编写迁移时：

- 每个 UP 都需要显式的反向操作：`CREATE TABLE` ↔ `DROP TABLE IF EXISTS`、
  `ADD COLUMN` ↔ `DROP COLUMN IF EXISTS`、`CREATE VIEW` ↔ `DROP VIEW`。
- UP 优先使用 `if_not_exists`，DOWN 优先使用 `if_exists`，这样部分执行的组在手工修复后可以重跑。
- DOWN 仍然按组顺序的逆序执行（核心行为）；请让你的补偿语句与这个顺序保持一致。
- 不要依赖 `single_transaction=True` 来保证安全——对 ClickHouse 而言，它无法回滚已经生效的 DDL。

## 6. 版本记录与 dry run（ClickHouse 相关细节）

- 唯一内置的记录存储是 `JSONFileMigrationRecordStore`：一个本地文件，而不是 ClickHouse 表。
  请妥善备份与共享——它是已应用内容的唯一真实来源。
- Dry run 只渲染语句，不接触服务端。在非事务性后端上，它是 DDL 批次唯一安全的预览方式：
  先调用 `run_migration_group(..., dry_run=True)`，在真正执行前读取 `preview.dry_run_sql`。
- 使用类风格的 `MigrationRunner` 时，优先通过 `ctx.execute()` 调用命名表达式，这样 `--dry-run`
  才能正确渲染（参见核心章节中旧执行器的注意事项）。

## 7. 按版本控制的功能

方言会探测所连接服务端的版本，并据此设置 `supports_*` 开关——某些参数与函数只在新版本中存在
（CI 覆盖 25.8、26.3 和 26.7）。如果迁移用到了较新的 ClickHouse 功能：

- 用 `backend.dialect.supports_<capability>()` 做门控，在旧服务端上跳过或选择替代方案；
- 如果方言拒绝执行 DDL（`ProtocolNotImplementedError` / `UnsupportedFeatureError`），执行器会把它
  包装为 `MigrationDialectError` 抛出；
- 不要硬编码版本号——ClickHouse 采用日历版本号（`YY.M.patch`）。

## 8. 两种编写风格（同步）

两种风格在核心章节中都有完整说明；这里只展示它们与 ClickHouse 的接线方式。

函数风格（主 API）：

```python
from rhosocial.activerecord.backend.migration import migration, MigrationDirection, run_migration_group

@migration("f001_create_events")
def create_events(ctx):
    if ctx.direction == MigrationDirection.UP:
        ctx.apply(MigrationEvent.create_table_statement(backend=ctx.backend))
    else:
        ctx.apply(MigrationEvent.drop_table_statement(if_exists=True, backend=ctx.backend))

preview = run_migration_group(backend, ["migration_support:create_events"], dry_run=True)
```

类风格（兼容旧版）：

```python
from rhosocial.activerecord.backend.migration import NamedMigration, MigrationContext

class CreateEventsTable(NamedMigration):
    version = "c001_create_events"

    def up(self, ctx: MigrationContext) -> None:
        ctx.apply(MigrationEvent.create_table_statement(backend=ctx.backend))

    def down(self, ctx: MigrationContext) -> None:
        ctx.apply(MigrationEvent.drop_table_statement(if_exists=True, backend=ctx.backend))
```

命令行接线：

```bash
python -m rhosocial.activerecord.backend.impl.clickhouse named-migration \
    myapp.migrations.CreateEventsTable --host localhost --database test_db \
    --record-store ./migrations.json --dry-run
```

> 不要传 `--async`：本后端没有异步实现。
