# 并行 Worker 场景下的正确用法（ClickHouse）

在数据处理、任务队列、批量导入等场景中，开发者常常希望用多个 Worker 并行处理任务以提升吞吐量。本章专注于 ClickHouse 数据库的并行 Worker 使用模式，阐述 ClickHouse 与 SQLite 在并发处理上的根本差异，并给出经过验证的安全方案。

> **贯穿本章的设计原则**：`rhosocial-activerecord` 的同步类 `BaseActiveRecord` 与异步类 `AsyncBaseActiveRecord` 方法名**完全相同**——`configure()` / `backend()` / `transaction()` / `save()` 等均如此，异步版本只需加 `await` 或 `async with`。本章所有示例均提供两种版本。

## 目录

1. [ClickHouse 并发能力概述](#1-clickhouse-并发能力概述)
2. [多进程：推荐方案](#2-多进程推荐方案)
3. [ClickHouse 异步后端的特点](#3-clickhouse-异步后端的特点)
4. [死锁：ClickHouse 自动检测与预防](#4-死锁clickhouse-自动检测与预防)
5. [应用分离原则](#5-应用分离原则)
6. [asyncio 并发在 ClickHouse 上的行为](#6-asyncio-并发在-clickhouse-上的行为)
7. [示例代码](#7-示例代码)

---

## 1. ClickHouse 并发能力概述

### 1.1 与 SQLite 的根本差异

`rhosocial-activerecord` 同样遵循**一个 ActiveRecord 类，绑定一条连接**的核心设计原则：

- **同步**：`Post.configure(config, ClickHouseBackend)` → 写入 `Post.__backend__`
- **异步**：`await Post.configure(config, AsyncClickHouseBackend)` → 写入 `Post.__backend__`

配置写入的是**类级别属性**，多线程间仍然不安全。但 ClickHouse 在以下方面与 SQLite 有根本差异：

| 特性 | SQLite | ClickHouse |
| --- | --- | --- |
| 锁粒度 | 文件级锁 | 行级锁（InnoDB） |
| 并发写入 | 需配置 WAL 模式，且写入间仍串行 | 默认支持，不同行可同时写入 |
| 异步后端 | `aiosqlite`：线程池模拟，性能无提升 | `clickhouse-connector-python` 原生 async：网络 I/O |
| 死锁处理 | 超时等待，抛出 `OperationalError: database is locked` | 自动检测，回滚代价小的一方（errno 1213） |
| 连接类型 | 文件路径（本地） | TCP 网络连接（host:port） |

### 1.2 单连接模型的不变性

无论 ClickHouse 有多少并发优势，**单个 `ActiveRecord` 类绑定的 `__backend__` 仍是一条连接**。在多线程环境下，并发操作同一 `__backend__` 会导致游标状态混乱。`clickhouse-connector-python` 官方明确说明连接不支持多线程并发使用。

> **不要将 ActiveRecord 配置在多个线程之间共享。** 多进程是并行 Worker 场景的正确选择。

---

## 2. 多进程：推荐方案

多进程是并行 Worker 场景的推荐方案。每个进程拥有独立的内存空间，`configure()` 在进程内独立执行，建立独立的 TCP 连接。

### 2.1 正确的生命周期

**同步（multiprocessing）**：

```python
import multiprocessing
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig
from models import Comment, Post, User

def worker(post_ids: list[int]):
    # 1. 进程启动后，在进程内配置连接——每个进程建立独立 TCP 连接
    config = ClickHouseConnectionConfig(
        host="localhost",
        port=3306,
        database="mydb",
        username="app",
        password="secret",
        charset="utf8mb4",
        autocommit=True,
    )
    User.configure(config, ClickHouseBackend)
    Post.__backend__ = User.backend()
    Comment.__backend__ = User.backend()

    try:
        for post_id in post_ids:
            post = Post.find_one(post_id)
            if post is None:
                continue
            author = post.author()          # BelongsTo 关联
            approved = len([c for c in post.comments() if c.is_approved])
            post.view_count = 1 + approved
            post.save()
    finally:
        # 2. 进程退出前断开连接
        User.backend().disconnect()


if __name__ == "__main__":
    post_ids = list(range(1, 101))
    chunk_size = 25

    with multiprocessing.Pool(processes=4) as pool:
        chunks = [post_ids[i:i+chunk_size] for i in range(0, len(post_ids), chunk_size)]
        pool.map(worker, chunks)
```

**异步（asyncio + 多进程）**：

```python
import asyncio
import multiprocessing
from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend, ClickHouseConnectionConfig
from models import AsyncComment, AsyncPost, AsyncUser

async def async_worker_main(post_ids: list[int]):
    # 1. 在进程内配置异步连接（clickhouse-connector-python 原生 async，TCP 网络 I/O）
    config = ClickHouseConnectionConfig(
        host="localhost", port=3306,
        database="mydb", username="app", password="secret",
        charset="utf8mb4", autocommit=True,
    )
    await AsyncUser.configure(config, AsyncClickHouseBackend)
    AsyncPost.__backend__ = AsyncUser.backend()
    AsyncComment.__backend__ = AsyncUser.backend()

    try:
        # asyncio.gather 并发处理——await 期间 CPU 真正处理其他协程
        async def process_post(post_id: int):
            post = await AsyncPost.find_one(post_id)
            if post is None:
                return
            author = await post.author()        # 加 await 加括号
            approved = len([c for c in await post.comments() if c.is_approved])
            post.view_count = 1 + approved
            await post.save()

        await asyncio.gather(*[process_post(pid) for pid in post_ids])
    finally:
        await AsyncUser.backend().disconnect()


def run_async_worker(post_ids: list[int]):
    # 每个进程有独立的 event loop 和独立的 ClickHouse 连接
    asyncio.run(async_worker_main(post_ids))


if __name__ == "__main__":
    post_ids = list(range(1, 101))
    chunk_size = 25

    with multiprocessing.Pool(processes=4) as pool:
        chunks = [post_ids[i:i+chunk_size] for i in range(0, len(post_ids), chunk_size)]
        pool.map(run_async_worker, chunks)
```

**关键规则**：

- `configure()` 必须在子进程内调用，不能在父进程配置后 `fork`
- ClickHouse 连接是 TCP 连接，`fork` 后继承文件描述符比 SQLite 更危险
- 异步场景下，同一进程内的协程天然串行访问数据库（event loop 单线程调度）

可运行的耗时对比演示见 [exp1_basic_multiprocess.py](../../examples/chapter_12_scenarios/parallel_workers/exp1_basic_multiprocess.py)。

---

## 3. ClickHouse 异步后端的特点

### 3.1 单连接模型的约束

`rhosocial-activerecord` 的异步 ClickHouse 后端（`AsyncClickHouseBackend`）基于 `clickhouse-connector-python` 的异步接口，**每个 ActiveRecord 类绑定一条连接**。这与连接池方案（如直接使用第三方连接池）不同：

> **`clickhouse-connector-python` 版本说明**：Python 3.8 锁定使用 `==9.0.0`（该 Python 版本支持的最高版本）；Python 3.9 及以上使用更高版本（如 Python 3.14 对应 9.6.0）。

| 特性 | 单连接 ORM（本项目） | 连接池方案 |
| --- | --- | --- |
| 同进程内 asyncio.gather | ❌ 不支持，会引发运行时错误 | ✅ 支持，每个协程使用不同连接 |
| 配置复杂度 | 低，`configure()` 一行 | 高，需手动管理连接池 |
| 多进程并发 | ✅ 每进程独立连接，真正并发 | ✅ 同样支持 |
| 适用场景 | 批处理、任务队列、数据管道 | 高并发 Web 服务 |

```text
单连接异步执行路径：
  协程 A → 发送 SQL → await → ClickHouse 响应 → 协程 A 恢复
  协程 B → 必须等待 A 完成后才能发送（顺序执行）

连接池异步执行路径：
  协程 A → 取连接 1 → 发送 SQL → await（并发）
  协程 B → 取连接 2 → 发送 SQL → await（并发）
  （两者真正同时在传输层并发）
```

### 3.2 多进程是并发的正确姿势

虽然单进程内协程必须顺序执行，但**多进程间**每个进程独立持有连接，真正并发：

```python
import asyncio

async def process_posts_sequential(post_ids: list[int]):
    """
    单连接：同一进程内顺序执行协程。
    并发通过多进程实现——每个进程独立连接，见 exp1/exp4。
    """
    async def update_one(post_id: int):
        post = await AsyncPost.find_one(post_id)
        if post:
            post.view_count += 1
            await post.save()

    # 单连接：顺序执行（不能用 asyncio.gather）
    for pid in post_ids:
        await update_one(pid)
```

可运行的多进程 async vs sync 性能对比见 [exp2_clickhouse_async_advantage.py](../../examples/chapter_12_scenarios/parallel_workers/exp2_clickhouse_async_advantage.py)。

---

## 4. 死锁：ClickHouse 自动检测与预防

ClickHouse InnoDB 内置死锁检测算法，死锁发生时自动回滚代价较小的事务，另一方继续执行。被回滚方收到 `OperationalError`（errno 1213）。

### 4.1 死锁的根本原因：行锁顺序不一致

```python
# ❌ 错误：不同 Worker 以相反顺序锁定行
def worker_a():
    with Post.transaction():
        post1 = Post.find_one(1)  # Worker A 先锁定 id=1
        time.sleep(0.01)
        post2 = Post.find_one(2)  # Worker A 再请求 id=2（此时 B 已持有）
        # → ClickHouse 检测到死锁，选择回滚 A 或 B

def worker_b():
    with Post.transaction():
        post2 = Post.find_one(2)  # Worker B 先锁定 id=2
        time.sleep(0.01)
        post1 = Post.find_one(1)  # Worker B 再请求 id=1（此时 A 已持有）
```

反面教材见 [exp3_deadlock_wrong.py](../../examples/chapter_12_scenarios/parallel_workers/exp3_deadlock_wrong.py)。

### 4.2 预防方案一：固定锁顺序

```python
# ✅ 正确：始终按主键升序锁定资源
def transfer_safe(from_id: int, to_id: int, amount: float):
    first_id, second_id = min(from_id, to_id), max(from_id, to_id)
    with Account.transaction():
        first  = Account.find_one(first_id)
        second = Account.find_one(second_id)
        debit, credit = (first, second) if from_id < to_id else (second, first)
        debit.balance  -= amount
        credit.balance += amount
        debit.save()
        credit.save()

# 异步版本（方法名相同，加 await）
async def transfer_safe_async(from_id: int, to_id: int, amount: float):
    first_id, second_id = min(from_id, to_id), max(from_id, to_id)
    async with Account.transaction():
        first  = await Account.find_one(first_id)
        second = await Account.find_one(second_id)
        debit, credit = (first, second) if from_id < to_id else (second, first)
        debit.balance  -= amount
        credit.balance += amount
        await debit.save()
        await credit.save()
```

### 4.3 预防方案二：原子领取（事务内查询 + 更新）

```python
# ✅ 正确：在事务内原子领取，ClickHouse 行级锁保证不重复
def claim_posts(batch_size: int = 5) -> list:
    with Post.transaction():
        pending = (
            Post.query()
                .where(Post.c.status == "draft")
                .order_by(Post.c.id)
                .limit(batch_size)
                .for_update()  # ClickHouse 支持 FOR UPDATE
                .all()
        )
        if not pending:
            return []
        for post in pending:
            post.status = "processing"
            post.save()
        return pending

# 异步版本（方法名相同，加 await）
async def claim_posts_async(batch_size: int = 5) -> list:
    async with AsyncPost.transaction():
        pending = await (
            AsyncPost.query()
                .where(AsyncPost.c.status == "draft")
                .order_by(AsyncPost.c.id)
                .limit(batch_size)
                .for_update()
                .all()
        )
        if not pending:
            return []
        for post in pending:
            post.status = "processing"
            await post.save()
        return pending
```

### 4.3.1 跨数据库兼容的能力检测模式

当您的代码需要在多个数据库后端之间复用时，应该先检测后端能力再使用 FOR UPDATE：

```python
def claim_posts_portable(batch_size: int = 5) -> list:
    """跨数据库兼容的原子领取实现"""
    # 获取后端方言并检测能力
    dialect = Post.backend().dialect
    supports_for_update = dialect.supports_for_update()

    with Post.transaction():
        query = (
            Post.query()
                .where(Post.c.status == "draft")
                .order_by(Post.c.id)
                .limit(batch_size)
        )

        # 仅在支持的后端使用 FOR UPDATE
        if supports_for_update:
            query = query.for_update()

        pending = query.all()

        if not pending:
            return []
        for post in pending:
            post.status = "processing"
            post.save()
        return pending
```

**能力检测设计原则**：

| 原则 | 说明 |
| --- | --- |
| **不替用户做选择** | 方言默认返回 `False`，只有明确支持的后端才返回 `True` |
| **双层检测防御** | ActiveQuery 层面调用 `for_update()` 时会检测；Dialect 层面生成 SQL 时再次检测 |
| **显式优于隐式** | 不支持 FOR UPDATE 时抛出 `UnsupportedFeatureError`，而非静默忽略 |
| **用户自主适配** | 用户通过 `supports_for_update()` 判断后，可选择替代方案（如数据分区） |

> **ClickHouse 说明**：ClickHouse 从早期版本就支持 FOR UPDATE，因此 `ClickHouseDialect.supports_for_update()` 始终返回 `True`。SQLite 不支持 FOR UPDATE（使用文件级锁），返回 `False`。

### 4.4 ClickHouse 专有方案：捕获死锁并重试（生产推荐）

ClickHouse 有自动死锁检测，因此可以**不预防死锁，而是捕获并重试**。这是 ClickHouse 生产环境的推荐模式：

```python
import time

def _is_deadlock(exc: Exception) -> bool:
    """判断异常是否为 ClickHouse 死锁（errno 1213）"""
    msg = str(exc)
    return "1213" in msg or "deadlock" in msg.lower()


def claim_posts_with_retry(batch_size: int = 5, max_retry: int = 3) -> list:
    """原子领取 + 死锁自动重试"""
    for attempt in range(max_retry):
        try:
            with Post.transaction():
                pending = (
                    Post.query()
                        .where(Post.c.status == "draft")
                        .order_by(Post.c.id)
                        .limit(batch_size)
                        .all()
                )
                if not pending:
                    return []
                for post in pending:
                    post.status = "processing"
                    post.save()
                return pending
        except Exception as e:
            if _is_deadlock(e) and attempt < max_retry - 1:
                time.sleep(0.05 * (attempt + 1))  # 指数退避
                continue
            raise
    return []
```

### 4.5 五条预防原则（含 ClickHouse 专有说明）

| 原则 | 说明 |
| --- | --- |
| **数据分区** | 将数据集按 ID 范围或哈希分配给各 Worker，避免多进程操作同一行 |
| **一致的锁顺序** | 涉及多资源时，按固定顺序（如主键升序）请求锁 |
| **短事务** | 事务内只做必要操作，不跨越 I/O 等待或耗时计算 |
| **原子领取** | 在事务内查询并更新任务状态，而非先读后改 |
| **死锁重试**（ClickHouse 专有） | 捕获 `OperationalError`（errno 1213）并重试，无需依赖锁顺序 |

> **ClickHouse vs SQLite 差异**：SQLite 需要 `pragmas={"busy_timeout": 5000}` 设置等待超时；ClickHouse InnoDB 使用 `innodb_lock_wait_timeout`（默认 50 秒）控制行锁等待，以及 `innodb_deadlock_detect`（默认开启）自动检测死锁。

可运行的正确方案演示见 [exp4_partition_correct.py](../../examples/chapter_12_scenarios/parallel_workers/exp4_partition_correct.py)。

---

## 5. 应用分离原则

当系统同时包含两种截然不同的工作负载时，建议将它们部署为独立应用。

### 5.1 场景示例

| 工作负载类型 | 特征 | 合适部署 |
| --- | --- | --- |
| Web API 服务 | 短请求、高并发、响应时间敏感 | FastAPI / Django + asyncio + 连接池（如 aioclickhouse） |
| 数据分析批处理 | 长时间运行、大数据量、CPU 密集 | 独立脚本 + multiprocessing + ClickHouseBackend |
| 任务队列消费 | 定期轮询、任务间独立、易于水平扩展 | Celery + ClickHouse 或自定义 + multiprocessing |

### 5.2 推荐架构

```text
用户请求 ──→ Web 应用（asyncio + 连接池异步连接）
                │
                └──→ 任务队列（ClickHouse 数据库表 / Redis）
                            │
                            └──→ 后台 Worker 进程池
                                  （每进程独立 ClickHouseBackend 同步连接）
```

Web 应用负责接收请求、写入任务队列；Worker 进程池负责执行耗时任务。

---

## 6. asyncio 并发在 ClickHouse 上的行为

### 6.1 单连接模型的限制

`rhosocial-activerecord` 遵循**一个 ActiveRecord 类绑定一条连接**的核心设计原则。这意味着同一进程内的协程**不能**通过 `asyncio.gather` 并发访问数据库——单个连接在同一时刻只能处理一个查询，并发访问会引发：

```text
RuntimeError: read() called while another coroutine is already waiting for incoming data
```

正确的异步用法是在同一进程内**顺序**执行协程，在**多进程**层面实现并发：

```python
# ❌ 错误：单连接不支持并发访问
async def batch_update_wrong(post_ids: list[int]):
    await asyncio.gather(*[
        update_one(pid) for pid in post_ids  # 会引发运行时错误
    ])

# ✅ 正确：单连接内顺序执行
async def batch_update_correct(post_ids: list[int]):
    for pid in post_ids:
        await update_one(pid)
```

### 6.2 多进程是并发的载体

异步的优势在于**多进程间**：每个进程持有独立的 ClickHouse TCP 连接，进程间真正并发。

```python
# ✅ 正确：多进程 + 每进程内异步顺序执行
async def async_worker_main(post_ids: list[int]):
    await AsyncPost.configure(config, AsyncClickHouseBackend)
    for pid in post_ids:  # 单连接：顺序执行
        post = await AsyncPost.find_one(pid)
        if post:
            post.view_count += 1
            await post.save()
    await AsyncPost.backend().disconnect()

def run_async_worker(post_ids: list[int]):
    asyncio.run(async_worker_main(post_ids))

# 4 个进程各自持有独立连接，进程间并发
with multiprocessing.Pool(processes=4) as pool:
    pool.map(run_async_worker, chunks)
```

### 6.3 含 `await` 的事务：需要注意

```python
async def update_user(user_id: int):
    async with User.transaction():
        user = await User.find_one(user_id)
        # ← 此处 await 将控制权交还给 event loop
        #   其他协程可能在这里执行并写入数据库，导致事务语义损坏
        await asyncio.sleep(0)  # 模拟 I/O 等待
        user.name = "new name"
        await user.save()
```

### 6.4 asyncio 的安全用法

**避免**并发地对同一连接开启多个事务；**推荐**事务内操作紧凑，避免不必要的 `await`。

```python
# ✅ 正确：事务内操作紧凑，无额外 await
async with User.transaction():
    user = await User.find_one(user_id)
    user.name = "new name"
    await user.save()
# 事务结束，其他协程可以开始各自的事务
```

### 6.5 ClickHouse 异步与 SQLite 异步的对比总结

| 场景 | ClickHouse（AsyncClickHouseBackend） | SQLite（aiosqlite） |
| --- | --- | --- |
| 同进程内 asyncio.gather | ❌ 单连接不支持，需顺序执行 | ❌ 线程池模拟，同样不支持真并发 |
| 多进程并发写入 | ✅ 行级锁，无需配置 | ⚠️ 需要 WAL 模式 |
| 死锁处理 | ✅ 自动检测，可重试 | ⚠️ 超时等待 |
| 批处理 / 任务队列 | ✅ 首选方案 | ⚠️ 不推荐高并发写入 |

---

## 7. 示例代码

本章的完整可运行示例位于 [`docs/examples/chapter_12_scenarios/parallel_workers/`](../../examples/chapter_12_scenarios/parallel_workers/)，包含以下实验：

| 文件 | 内容 | 对应章节 |
| --- | --- | --- |
| [`config_loader.py`](../../examples/chapter_12_scenarios/parallel_workers/config_loader.py) | 连接配置加载（YAML / 环境变量 / 默认值） | — |
| [`models.py`](../../examples/chapter_12_scenarios/parallel_workers/models.py) | 共享模型定义（`User`、`Post`、`Comment` 同步版 + 异步版） | — |
| [`setup_db.py`](../../examples/chapter_12_scenarios/parallel_workers/setup_db.py) | 数据库初始化脚本（同步/异步两种模式） | — |
| [`exp1_basic_multiprocess.py`](../../examples/chapter_12_scenarios/parallel_workers/exp1_basic_multiprocess.py) | 正确的多进程用法（含串行/同步多进程/异步多进程耗时对比） | §2.1 |
| [`exp2_clickhouse_async_advantage.py`](../../examples/chapter_12_scenarios/parallel_workers/exp2_clickhouse_async_advantage.py) | ClickHouse 异步特点：单连接限制说明 + 多进程并发写入对比 | §3 |
| [`exp3_deadlock_wrong.py`](../../examples/chapter_12_scenarios/parallel_workers/exp3_deadlock_wrong.py) | 行锁顺序冲突导致 ClickHouse 死锁（反面教材） | §4.1 |
| [`exp4_partition_correct.py`](../../examples/chapter_12_scenarios/parallel_workers/exp4_partition_correct.py) | 数据分区 + 原子领取 + 死锁重试（同步/异步各方案） | §4.2–4.4 |
| [`exp5_multithread_warning.py`](../../examples/chapter_12_scenarios/parallel_workers/exp5_multithread_warning.py) | 多线程共享连接的问题（反面教材） | §1.2 |
| [`exp6_backend_group_context.py`](../../examples/chapter_12_scenarios/parallel_workers/exp6_backend_group_context.py) | BackendGroup + backend.context() 线程安全性验证 | §8.5 |

> **说明**：所有示例文件均直接使用 `rhosocial-activerecord` ORM，模型体系为 `User → Post → Comment`，并体现 `HasMany` / `BelongsTo` 关联关系的同步与异步对等用法。

运行前请先执行初始化脚本：

```bash
cd docs/examples/chapter_12_scenarios/parallel_workers
python setup_db.py
python exp1_basic_multiprocess.py   # 运行任意实验
```

详见该目录下的 `README.md` 了解各实验的完整说明和预期输出。

---

## 8. WorkerPool 测试经验总结

### 8.1 异步 Worker 测试的已知限制

在 `WorkerPool` 多进程环境下运行异步测试时，存在以下已知限制：

#### Event Loop 跨进程问题

当 `WorkerPool` 在子进程中执行异步任务时，每个子进程通过 `asyncio.run()` 创建独立的 event loop。然而，测试框架（pytest-asyncio）的 fixture 在主进程中创建的 event loop 与子进程中的 event loop 是隔离的：

```text
主进程（pytest）：
  └── Event Loop A（pytest-asyncio 创建）
      └── Fixture: async_user_class_for_worker
          └── 异步后端实例绑定到 Loop A

子进程（Worker）：
  └── Event Loop B（asyncio.run() 创建）
      └── 任务尝试使用绑定到 Loop A 的异步后端
          └── 错误：Task got Future attached to a different loop
```

**错误示例**：

```python
# ❌ 错误：在主进程 fixture 中创建的异步后端无法在子进程中使用
async def async_worker_task(user_id, conn_params):
    # conn_params 包含的异步后端实例绑定到主进程的 event loop
    # 子进程尝试使用时会失败
    backend = conn_params['backend']  # 绑定到错误的 loop
    user = await backend.find_one(user_id)  # RuntimeError!
```

**正确做法**：

```python
# ✅ 正确：在子进程内部创建新的异步后端实例
async def async_worker_task(user_id, conn_params):
    # 只传递连接参数（可序列化），在子进程内创建新实例
    config = conn_params['config_kwargs']
    await Model.configure(config, AsyncClickHouseBackend)
    user = await Model.find_one(user_id)
    await Model.backend().disconnect()
```

#### 受影响的测试场景

| 测试类型 | 同步版本 | 异步版本 | 原因 |
|----------|----------|----------|------|
| 并行读取 | ✅ 通过 | ❌ 失败 | 异步后端绑定到主进程 loop |
| 并行更新 | ✅ 通过 | ❌ 失败 | 同上 |
| 并行删除 | ✅ 通过 | ❌ 失败 | 同上 |
| 并行查询 | ✅ 通过 | ❌ 失败 | 同上 |
| 事务隔离 | ✅ 通过 | ❌ 失败 | 同上 + 事务状态跨进程问题 |
| Worker 生命周期 | ✅ 通过 | ✅ 通过 | 不涉及跨进程异步操作 |
| 连接管理 | ✅ 通过 | ✅ 通过 | 不涉及跨进程异步操作 |

### 8.2 测试覆盖率说明

Worker 测试对 ClickHouse 后端的覆盖率贡献：

| 模块 | 覆盖率 | 说明 |
|------|--------|------|
| `backend.py` | ~32% | 同步后端核心功能 |
| `async_backend.py` | ~35% | 异步后端核心功能 |
| `mixins.py` | ~22% | DML 操作 |
| `dialect.py` | ~22% | SQL 方言处理 |

同步测试覆盖率较高，异步测试因 event loop 问题导致部分代码路径未被覆盖。

### 8.3 生产环境建议

1. **同步 Worker 是首选**：在多进程 Worker 场景下，同步后端（`ClickHouseBackend`）是更稳定的选择
2. **异步适用于单进程**：异步后端（`AsyncClickHouseBackend`）在单进程内的顺序执行场景下表现良好
3. **避免跨进程传递异步实例**：只传递可序列化的连接参数，在子进程内创建新的异步后端实例

### 8.4 FOR UPDATE 能力检测经验

#### 问题背景

在 WorkerPool 多进程测试中，`test_transaction_isolation.py` 的转账测试使用了 `FOR UPDATE` 子句来锁定行。然而，SQLite 后端不支持 `FOR UPDATE`（使用文件级锁），导致测试失败。

#### 解决方案：能力检测模式

遵循「不替用户做选择」的设计原则，我们实现了两层能力检测：

**1. Dialect 层面的能力声明**：

```python
# SQLDialectBase（默认不支持）
def supports_for_update(self) -> bool:
    """默认返回 False，只有支持的后端才重写此方法"""
    return False

# ClickHouseDialect（明确支持）
def supports_for_update(self) -> bool:
    return True
```

**2. ActiveQuery 层面的早期检测**：

```python
# ActiveQuery.for_update() 方法中
def for_update(self, ...):
    if not dialect.supports_for_update():
        raise UnsupportedFeatureError(
            dialect.name,
            "FOR UPDATE clause",
            "This backend does not support row-level locking with FOR UPDATE. "
            "Use dialect.supports_for_update() to check support before calling this method."
        )
```

**3. Dialect 层面的安全网**：

```python
# SQLDialectBase.format_query_statement() 中
if expr.for_update:
    if not self.supports_for_update():
        raise UnsupportedFeatureError(...)
    # 生成 FOR UPDATE SQL...
```

#### 测试代码适配

测试任务函数中使用能力检测来适配不同后端：

```python
def transfer_task(from_id: int, to_id: int, amount: float, conn_params: dict):
    # 检测后端是否支持 FOR UPDATE
    supports_for_update = backend.dialect.supports_for_update()

    with Model.transaction():
        if supports_for_update:
            # ClickHouse/PostgreSQL：使用 FOR UPDATE 锁定
            first = Model.query().where(Model.c.id == first_id).for_update().one()
        else:
            # SQLite：使用普通查询（依赖文件锁）
            first = Model.find_one({'id': first_id})
        # ... 业务逻辑
```

#### 设计经验总结

| 经验 | 说明 |
|------|------|
| **默认拒绝原则** | 基类返回 `False`，后端必须显式声明支持 |
| **不替用户做选择** | 不支持时抛错，而非静默忽略（Django/Rails 方案） |
| **双层防御** | ActiveQuery 提供早期失败，Dialect 作为安全网 |
| **用户自主适配** | 用户通过 `supports_for_update()` 判断后选择替代方案 |

### 8.5 相关文件

- 测试桥接文件：`tests/rhosocial/activerecord_clickhouse_test/feature/basic/worker/`
- Provider 实现：`tests/providers/basic.py`、`tests/providers/query.py`
- WorkerPool 实现：`rhosocial.activerecord.worker.pool`

---

## 9. 测试验证结论

### 9.1 测试环境

以下测试在多种环境下验证通过：

| 平台 | 操作系统 | Python 版本 | pytest 版本 | ClickHouse 版本 |
|------|----------|-------------|-------------|------------|
| macOS | macOS Tahoe 26.4.1 (Build 25E253) arm64 | 3.8.10 | 8.3.5 | 9.6.0 |
| Windows | Windows 11 Pro 25H2 (Build 26200) | 3.8.10 / 3.14.3 | 8.3.5 / 8.4.2 | 8.0.45 |

### 9.2 测试结果汇总

#### 多进程并行测试 (exp1)

| 平台 | 串行耗时 | 同步多进程 | 异步多进程 | 加速比 |
|------|----------|------------|------------|--------|
| macOS (Python 3.8.10) | 0.871s | 0.799s (1.1x) | 0.589s (1.5x) | 1.5x |
| Windows | 0.364s | 1.116s (0.3x) | 1.096s (0.3x) | 0.3x |

> **说明**: 多进程启动开销在小数据量下可能超过并行收益，大数据量时加速效果更明显。macOS arm64 平台异步多进程性能提升显著。

#### 异步特性测试 (exp2)

| 平台 | 同进程同步串行 | 同进程异步顺序 | 多进程同步 | 多进程异步 |
|------|----------------|----------------|------------|------------|
| macOS (Python 3.8.10) | 0.713s | 0.481s (1.48x) | 0.669s | 0.536s |
| Windows | 0.210s | 0.212s | 1.025s | 1.096s |

> **说明**: macOS 平台异步顺序执行相比同步串行有 1.48x 提升，体现了 clickhouse-connector-python 原生 async 的优势。

#### 死锁检测测试 (exp3)

所有平台均成功触发 ClickHouse 死锁检测机制：
- 死锁被自动检测（errno 1213）
- 代价较小的事务被回滚
- 未捕获异常时，回滚事务的工作丢失
- macOS: 2 Workers 成功，2 Workers 死锁回滚，总耗时 0.915s
- Windows: 2 Workers 成功，2 Workers 死锁回滚

#### 正确方案测试 (exp4)

| 方案 | macOS 耗时 | Windows 耗时 | 验证结果 |
|------|------------|--------------|----------|
| A: 数据分区（同步） | 0.831s | 1.006s | ✓ 无重复 |
| A: 数据分区（异步） | 0.675s | 1.108s | ✓ 无重复 |
| B: 原子领取（同步） | 2.837s | 1.428s | ✓ 无重复 |
| B: 原子领取（异步） | 2.052s | 1.199s | ✓ 无重复 |
| C: 原子+重试（同步） | 2.750s | 1.629s | ✓ 无重复 |

#### 多线程警告测试 (exp5)

所有平台均验证多线程共享连接不安全：
- 共享 `__backend__`: 游标状态混乱、连接丢失
- 每线程 `configure()`: 类属性被覆盖，仍共享同一实例

### 9.3 平台差异说明

#### Windows 特殊配置

在 Windows 上运行异步测试时，子进程需要设置 `WindowsSelectorEventLoopPolicy`：

```python
import asyncio
import sys

def worker_async(post_ids: list) -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(async_worker_main(post_ids))
```

**原因**: Windows 默认使用 `ProactorEventLoop`，而 `clickhouse-connector-python` 的异步后端需要 `SelectorEventLoop`。

#### macOS / Linux

无需特殊配置，默认 event loop 即可正常工作。

### 9.4 BackendGroup + backend.context() 线程安全验证 (exp6)

#### 实验目的

验证 BackendGroup + backend.context() 是否能提供线程安全的连接管理。

#### 实验结果

| 场景 | 成功数 | 错误数 | 结论 |
|-----|--------|--------|------|
| Scenario 1: backend.context() | 5 | 3 (75% 失败) | ❌ 多线程共享时有竞争条件 |
| Scenario 2: 手动连接 | 0 | 4 (100% 失败) | ❌ 不安全 |

#### 关键发现

**BackendGroup + backend.context() 不提供线程隔离**：

1. **设计意图**：BackendGroup 是为多模型共享后端设计的，不是线程隔离机制
2. **实际行为**：所有线程共享同一个后端实例，context() 只是管理连接生命周期
3. **竞争条件**：多个线程同时调用 context() 会产生竞争（connect/disconnect 冲突）

#### BackendGroup 的正确用途

```python
# ✅ 正确：多模型共享连接（单线程场景）
group = BackendGroup(
    name="main",
    models=[User, Post, Comment],
    config=config,
    backend_class=ClickHouseBackend
)
group.configure()

with group.get_backend().context():
    user = User.find_one(1)
    posts = user.posts  # 关联查询，共享事务
    posts[0].title = "New Title"
    posts[0].save()
    user.save()  # 同一事务，原子提交

# ❌ 错误：多线程共享同一个 BackendGroup
group = BackendGroup(...)
group.configure()

# 多个线程使用同一个 group 会有竞争条件
thread1: with group.get_backend().context(): ...  # 不安全！
thread2: with group.get_backend().context(): ...  # 不安全！
```

#### ClickHouse 的线程安全方案

| 方案 | threadsafety | 推荐度 | 说明 |
|-----|-------------|--------|------|
| **多进程** | 1 | ⭐⭐⭐ 推荐 | ClickHouse 连接不支持跨线程，必须用多进程 |
| 多线程 + BackendGroup | 1 | ❌ 不推荐 | 有竞争条件，不安全 |
| BackendPool | 1 | ❌ 不支持 | ClickHouse 不适合连接池（threadsafety<2） |

#### 结论

- **BackendGroup 的文档表述与实际功能一致**：用于多模型共享连接，不承诺线程隔离
- **ClickHouse 多线程场景必须使用多进程**：这是 threadsafety=1 的本质限制
- **"随用随连、用完即断"是连接生命周期管理原则**：不是线程隔离机制

### 9.5 FastAPI 异步应用的最佳实践

#### 问题场景

在 FastAPI + ClickHouse + 异步后端场景下：
- 每个 HTTP 请求在独立的协程中处理
- 多个协程可能并发执行（但同一时刻只有一个在运行）
- ClickHouse 的 `threadsafety=1`，不支持连接池
- 需要确保每个请求有独立的数据库连接

#### 推荐方案：请求级 BackendGroup + backend.context()

**核心原则**：
1. 每个请求创建独立的 `AsyncBackendGroup` 实例
2. 使用 `backend.context()` 管理连接生命周期
3. 请求结束时自动断开连接（"随用随连、用完即断"）

**完整示例**：

```python
# database.py - 请求级连接管理器
from contextlib import asynccontextmanager
from rhosocial.activerecord.connection import AsyncBackendGroup
from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend

@asynccontextmanager
async def get_request_db():
    """请求级数据库连接管理器"""
    config = load_config()
    
    # 创建请求级的 BackendGroup（请求隔离）
    group = AsyncBackendGroup(
        name="request",
        models=[AsyncUser, AsyncPost, AsyncComment],
        config=config,
        backend_class=AsyncClickHouseBackend
    )
    
    try:
        await group.configure()
        backend = group.get_backend()
        
        # 使用 context() 管理连接生命周期
        # "随用随连、用完即断"
        async with backend.context():
            yield backend
    
    finally:
        await group.disconnect()


# app.py - FastAPI 应用
from fastapi import FastAPI, Depends

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(get_request_db)):
    user = await AsyncUser.find_one(user_id)
    return {"user": user.to_dict()}
```

#### 方案分析

| 特性 | 说明 |
|-----|------|
| **连接隔离** | 每个请求独立的 BackendGroup，完全隔离 |
| **并发安全** | 不同请求的协程使用不同连接 |
| **资源管理** | 请求结束自动断开，无连接泄漏 |
| **事务支持** | 同一请求内的操作共享事务 |
| **效率影响** | 每请求创建/断开连接，有额外开销（可接受） |

#### 关键设计要点

1. **请求级 BackendGroup**（而非全局共享）
   - 每个 HTTP 请求创建独立的 BackendGroup
   - 确保请求间完全隔离

2. **使用 `async with backend.context()`**
   - 自动管理连接生命周期
   - 异常时也能正确断开

3. **通过 FastAPI 依赖注入**
   - 自动管理连接获取和释放
   - 代码简洁，不易出错

4. **避免全局共享后端实例**
   - ❌ 不要在应用启动时创建全局 BackendGroup
   - ✅ 每个请求创建独立的 BackendGroup

#### 适用场景

| 场景 | 推荐度 | 说明 |
|-----|--------|------|
| Web API（轻量查询） | ⭐⭐⭐ 推荐 | 请求级连接管理，完全隔离 |
| CRUD 操作 | ⭐⭐⭐ 推荐 | 简单的增删改查操作 |
| WebSocket 长连接 | ❌ 不推荐 | 考虑其他方案（如每消息创建连接） |
| 批处理任务 | ❌ 不推荐 | 使用多进程 |
| 重计算任务 | ❌ 不推荐 | 使用多进程 |

#### 完整示例代码

参见 `docs/examples/chapter_10_fastapi/` 目录。

### 9.6 结论

1. **多进程是并行 Worker 的正确方案**: 所有平台均验证通过
2. **同步后端更稳定**: 异步后端在 Windows 上需要额外配置
3. **死锁重试方案推荐用于生产**: 不依赖数据可分区性，自动处理死锁
4. **数据分区效率最高**: 无锁竞争，适合可分区场景
5. **BackendGroup 用于多模型共享连接**: 不是线程隔离机制，多线程场景应使用多进程
6. **FastAPI 推荐请求级 BackendGroup**: 每请求独立连接，确保隔离和安全
