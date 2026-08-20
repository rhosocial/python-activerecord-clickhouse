# 并行 Worker 场景实验（ClickHouse 版）

本目录包含《场景实战 — 并行 Worker》章节的完整可运行实验代码，所有示例均使用真实的 `rhosocial-activerecord` ORM 操作 ClickHouse 数据库，模型体系为：

```text
User --has_many--> Post --has_many--> Comment
User <--belongs_to-- Post
Post <--belongs_to-- Comment
User <--belongs_to-- Comment （评论作者）
```

每个模型提供**同步版**（继承 `ActiveRecord`）和**异步版**（继承 `AsyncActiveRecord`），方法名完全相同，异步版仅需加 `await`。

## 实验列表

| 文件 | 主题 | 类型 |
| ---- | ---- | ---- |
| `config_loader.py` | 从 YAML / 环境变量 / 默认值加载 ClickHouse 连接配置 | 工具 |
| `setup_db.py` | 初始化数据库和测试数据 | 工具 |
| `models.py` | 共享 ActiveRecord 模型定义（同步 + 异步） | 公共 |
| `exp1_basic_multiprocess.py` | 多进程正确用法 + 串行/并行耗时对比 | ✅ 正确示范 |
| `exp2_clickhouse_async_advantage.py` | ClickHouse 异步真正优势 + 并发写入能力 | ✅ 正确示范 |
| `exp3_deadlock_wrong.py` | 行锁顺序冲突导致 ClickHouse 死锁 | ❌ 反面教材 |
| `exp4_partition_correct.py` | 数据分区 + 原子领取 + 死锁重试 | ✅ 正确示范 |
| `exp5_multithread_warning.py` | 多线程共享 ClickHouse 连接的危险 | ❌ 反面教材 |

## ClickHouse vs SQLite 关键差异

| 特性 | SQLite | ClickHouse |
| ---- | ------ | ----- |
| 异步后端 | `aiosqlite`（线程池模拟，有额外开销） | `clickhouse-connector-python` 原生 async（网络 I/O） |
| 并发写入 | 需要 WAL 模式才能并发 | 默认行级锁，开箱即用并发 |
| 死锁检测 | 无自动检测，超时返回 locked | InnoDB 自动检测，回滚其中一方 |
| 线程安全 | `check_same_thread=True` 默认保护 | 无内置保护，官方明确说明不支持 |
| 连接方式 | 文件路径 | 网络 TCP 连接（host:port） |
| 同进程 asyncio.gather | 不支持（线程池单通道） | 不支持（单连接模型） |

## 依赖说明

本实验依赖 `clickhouse-connector-python`，版本要求因 Python 版本而异：

| Python 版本 | clickhouse-connector-python 版本  | 说明                           |
| ----------- | ---------------------------- | ------------------------------ |
| 3.8         | `==9.0.0`                    | 锁定版本（3.8 支持的最高版本） |
| 3.9+        | `>=9.1.0`（如 9.6.0）        | 使用更高版本                   |

安装示例：

```bash
# Python 3.8
pip install "clickhouse-connector-python==9.0.0"

# Python 3.9+（含 3.14）
pip install "clickhouse-connector-python>=9.1.0"
```

## 快速开始

### 1. 激活虚拟环境

```bash
# 在 python-activerecord-clickhouse 项目根目录
source .venv3.8-examples/bin/activate
# 或
source .venv3.14t-examples/bin/activate
```

### 2. 进入实验目录

```bash
cd docs/examples/chapter_12_scenarios/parallel_workers
```

### 3. 检查连接配置

实验脚本自动读取 `tests/config/clickhouse_scenarios.yaml`（如存在），优先使用 `clickhouse_80` 场景。
也可通过环境变量覆盖：

```bash
export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=3306
export CLICKHOUSE_DATABASE=test_db
export CLICKHOUSE_USER=root
export CLICKHOUSE_PASSWORD=your_password
```

或使用 `--scenario` 指定 YAML 场景名：

```bash
python setup_db.py --scenario clickhouse_84
```

### 4. 初始化数据库

**每次运行实验前必须先执行此步骤**（实验脚本会修改数据库状态）：

```bash
python setup_db.py          # 同步初始化（默认）
python setup_db.py --async  # 异步初始化（效果相同）
```

预期输出：

```text
=== 同步初始化模式 ===
连接信息：
  主机：${CLICKHOUSE_HOST:-localhost}:${CLICKHOUSE_PORT:-3306}
  数据库：test_db
  用户：root
  字符集：utf8mb4

删除旧表并重新建表…
建表完成，开始插入测试数据…
  User #1: user01
  ...
  共插入 20 篇文章
  共插入 60 条评论

✓ 同步初始化完成
  用户 5 / 文章 20 / 评论 60
```

### 5. 运行实验

各实验相互独立，每次运行前先执行 `setup_db.py` 重置数据库：

```bash
python setup_db.py && python exp1_basic_multiprocess.py
python setup_db.py && python exp2_clickhouse_async_advantage.py
python setup_db.py && python exp3_deadlock_wrong.py
python setup_db.py && python exp4_partition_correct.py
python setup_db.py && python exp5_multithread_warning.py
```

## 实验说明

### exp1：基础多进程用法

演示最核心的原则：**`configure()` 必须在子进程内调用**。

对比三种处理方式的耗时：

- **实验 A**：串行（单进程，同步 ActiveRecord）
- **实验 B**：4 进程并行（同步 ActiveRecord）
- **实验 C**：4 进程并行（异步 ActiveRecord，每进程内 asyncio 驱动）

同时演示 `BelongsTo` 关联遍历（`post.author()`）的正确用法。

ClickHouse 特别说明：父进程 `configure()` 建立 TCP 连接后 `fork`，子进程继承文件描述符，多进程共享同一 TCP socket，比 SQLite 共享文件句柄更危险。

### exp2：ClickHouse 异步特点与多进程并发写入

说明 `clickhouse-connector-python` 异步后端（单连接模型）的特点：

- **Part 1**：同进程内，同步串行 vs 异步顺序，说明单连接不能 `asyncio.gather` 并发
- **Part 2**：多进程并发写入，ClickHouse 行级锁无需 WAL 配置即支持并发

预期输出（参考）：

```text
Part 1：同进程内同步串行 vs 异步顺序（单连接限制）
  同步串行：20 篇，耗时 0.XXXs
  异步并发：20 篇，耗时 0.XXXs
  异步/同步比：X.XXx（单连接下两者相近，并发优势在多进程间体现）
```

> **注意**：`clickhouse-connector-python` 异步后端是单连接模型，同进程内协程不能并发（不同于连接池方案）。多进程间每进程独立连接，才是并发的体现。

### exp3：反面教材 — ClickHouse 死锁

故意展示不一致的行锁顺序导致 ClickHouse 死锁（errno 1213）的场景。

ClickHouse InnoDB 会**自动检测死锁**并回滚代价较小的事务，另一方继续执行。
被回滚的 Worker 收到 `OperationalError`，若不处理则工作丢失。

预期输出（参考）：

```text
=== 错误模式：不一致的锁顺序（ClickHouse 死锁演示）===
  Worker 0 (✅ 成功)：...
  Worker 1 (💀 死锁回滚)：...
  → 死锁（ClickHouse errno 1213）：...
```

### exp4：正确的并行方案（含 ClickHouse 特有方案 C）

提供五种生产可用的并行策略：

- **方案 A 同步/异步**：按 `user_id` 分区，遍历 `HasMany` 关联统计评论数
- **方案 B 同步/异步**：事务内原子领取（`with/async with Post.transaction()`）
- **方案 C 同步**：原子领取 + 死锁自动重试（**ClickHouse 生产环境推荐**）

预期输出（参考）：

```text
=== 方案 A：数据分区（同步 ActiveRecord）===
  结果：Worker 共处理 20 篇，发布 20 篇，耗时 X.XXXs ✅ 无重复

=== 方案 C：原子领取 + 死锁重试（ClickHouse 生产推荐，同步）===
  结果：Worker 共处理 20 篇，发布 20 篇，耗时 X.XXXs ✅ 无重复

总体验证：✅ 所有方案均无重复处理
```

### exp5：反面教材 — 多线程问题

展示 ClickHouse 多线程陷阱：

- **场景 1**：共享 `__backend__` — 游标状态被并发线程覆盖
- **场景 2**：每线程 `configure()` — 类属性互相覆盖，实际仍共享同一实例

ClickHouse 无 `check_same_thread` 保护，但官方同样明确不支持多线程并发共享连接。

## 关联关系访问说明

同步关联返回可调用函数，需要加 `()` 才能触发查询：

```python
# 同步 BelongsTo
author = post.author()          # ✅ 正确，返回 User 实例或 None
author = post.author            # ❌ 错误，返回函数对象

# 同步 HasMany
comments = post.comments()      # ✅ 正确，返回 list[Comment]
comments = post.comments        # ❌ 错误，返回函数对象

# 异步 BelongsTo（加 await + 括号）
author = await post.author()    # ✅ 正确
author = await post.author      # ❌ 错误

# 异步 HasMany
comments = await post.comments()  # ✅ 正确
comments = await post.comments    # ❌ 错误
```

## 常见问题

**Q: 运行实验时报连接拒绝（Connection refused），怎么处理？**

A: 检查 `tests/config/clickhouse_scenarios.yaml` 中的连接参数，或通过环境变量 `CLICKHOUSE_HOST` / `CLICKHOUSE_PORT` / `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` 配置本地 ClickHouse 服务器。

**Q: 报 `pyyaml` 未安装，怎么处理？**

A: 运行 `pip install pyyaml`，或通过环境变量直接配置连接参数（无需 YAML 文件）。

**Q: exp3 每次运行都触发了死锁吗？**

A: 不一定。死锁依赖时序，`sleep(0.01)` 已增大窗口，多运行几次可复现。exp4 方案 C 的重试机制可以自动处理此情况。

**Q: exp2 中异步比同步快多少？**

A: 取决于网络延迟和并发数。ClickHouse 服务器在本地时差异较小；远程服务器网络延迟较大时，异步加速效果更明显。与 SQLite（异步通常更慢）完全相反。

**Q: 为什么 exp4 的 view_count 验证用 `> 0` 而不是 `== 1`？**

A: `view_count = 1 + len(approved_comments)`，大多数文章有 1-2 条已审核评论，实际值为 2 或 3，因此验证 `> 0` 即可确认"被处理过一次"。

## Windows 测试结果

以下测试结果在 Windows 11 上验证通过：

### 测试环境

| 组件 | 版本 |
|------|------|
| 操作系统 | Windows 11 Pro 25H2 (Build 26200) |
| Python | 3.8.10 / 3.14.3 |
| pytest | 8.3.5 (Python 3.8) / 8.4.2 (Python 3.14) |
| ClickHouse | 8.0.45 |

### exp1: 基础多进程用法

```
=== Experiment A: Serial Processing (Single Process, Synchronous ActiveRecord) ===
Serial completed 20 posts, time: 0.364s

=== Experiment B: 4 Processes Parallel (Synchronous ActiveRecord) ===
Parallel completed 20 posts, time: 1.116s
Speedup: 0.3x (theoretical max 4x)

=== Experiment C: 4 Processes Parallel (Asynchronous ActiveRecord) ===
Parallel completed 20 posts, time: 1.096s
Speedup: 0.3x (theoretical max 4x)
```

### exp2: ClickHouse 异步特点与多进程并发写入

```
Part 1: Same process sync serial vs async sequential (single-connection limitation)
Sync serial: 0.210s, async sequential: 0.212s

Part 2: Multiprocess concurrent writes (ClickHouse row-level locking)
Sync multiprocess (4 processes): 1.025s
Async multiprocess (4 processes): 1.096s
```

### exp3: 死锁演示

```
Results: 2 Workers succeeded, 2 deadlocked, 0 other errors
⚠️ Found 2 Workers rolled back due to deadlock by ClickHouse!
All posts have view_count=1 (correct values after rollback)
```

### exp4: 正确的并行方案

```
Solution A: Data Partitioning
Sync: 1.006s, Async: 1.108s ✓ No duplicates

Solution B: Atomic Claiming
Sync: 1.428s, Async: 1.199s ✓ No duplicates

Solution C: Atomic + Deadlock Retry (Production Recommended)
Sync: 1.629s ✓ No duplicates
```

### exp5: 多线程警告

```
Scenario 1: Shared __backend__
⚠️ Found 2 errors (proves multithreaded connection sharing is unsafe)

Scenario 2: Each thread calls configure()
Actual backend instance count: 1 (Expected 4)
✗ All threads share the same backend instance
```

### Windows 特殊说明

在 Windows 上运行异步测试时，子进程需要设置 `WindowsSelectorEventLoopPolicy`：

```python
import asyncio
import sys

def worker_async(post_ids: list) -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(async_worker_main(post_ids))
```

这是因为 Windows 默认使用 `ProactorEventLoop`，而 `clickhouse-connector-python` 的异步后端需要 `SelectorEventLoop`。
