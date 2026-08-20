# Parallel Workers: Best Practices (ClickHouse)

In data processing, task queues, and bulk import scenarios, developers often run multiple workers in parallel to improve throughput. This chapter focuses on parallel worker patterns for ClickHouse, explains the fundamental differences between ClickHouse and SQLite for concurrent processing, and provides validated, safe solutions.

> **Design principle throughout this chapter**: The synchronous `BaseActiveRecord` and asynchronous `AsyncBaseActiveRecord` have **identical method names** — `configure()`, `backend()`, `transaction()`, `save()`, and so on. The async version simply requires `await` or `async with`. All examples in this chapter provide both versions.

## Table of Contents

1. [ClickHouse Concurrency Overview](#1-clickhouse-concurrency-overview)
2. [Multi-process: The Recommended Approach](#2-multi-process-the-recommended-approach)
3. [ClickHouse Async Backend Characteristics](#3-clickhouse-async-backend-characteristics)
4. [Deadlocks: ClickHouse Auto-detection and Prevention](#4-deadlocks-clickhouse-auto-detection-and-prevention)
5. [Application Separation Principle](#5-application-separation-principle)
6. [asyncio Concurrency Behavior with ClickHouse](#6-asyncio-concurrency-behavior-with-clickhouse)
7. [Example Code](#7-example-code)

---

## 1. ClickHouse Concurrency Overview

### 1.1 Fundamental Differences from SQLite

`rhosocial-activerecord` still follows the core design principle of **one ActiveRecord class bound to one connection**:

- **Sync**: `Post.configure(config, ClickHouseBackend)` → writes to `Post.__backend__`
- **Async**: `await Post.configure(config, AsyncClickHouseBackend)` → writes to `Post.__backend__`

The configuration writes to a **class-level attribute**, which is still unsafe across threads. However, ClickHouse differs fundamentally from SQLite in several ways:

| Feature | SQLite | ClickHouse |
| --- | --- | --- |
| Lock granularity | File-level lock | Row-level lock (InnoDB) |
| Concurrent writes | Requires WAL mode; writes still serialized | Supported by default; different rows write simultaneously |
| Async backend | `aiosqlite`: thread-pool simulation, no performance gain | `clickhouse-connector-python` native async: network I/O |
| Deadlock handling | Timeout wait, raises `OperationalError: database is locked` | Auto-detection, rolls back the cheaper transaction (errno 1213) |
| Connection type | File path (local) | TCP network connection (host:port) |

### 1.2 The Immutability of the Single-Connection Model

Regardless of ClickHouse's concurrency advantages, **a single `ActiveRecord` class's `__backend__` remains a single connection**. In a multi-threaded environment, concurrent access to the same `__backend__` corrupts cursor state. The `clickhouse-connector-python` documentation explicitly states that connections do not support concurrent multi-threaded use.

> **Do not share an ActiveRecord configuration across multiple threads.** Multi-process is the correct choice for parallel worker scenarios.

---

## 2. Multi-process: The Recommended Approach

Multi-process is the recommended approach for parallel worker scenarios. Each process has its own isolated memory space; `configure()` executes independently within each process, establishing a separate TCP connection.

### 2.1 Correct Lifecycle

**Sync (multiprocessing)**:

```python
import multiprocessing
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig
from models import Comment, Post, User

def worker(post_ids: list[int]):
    # 1. After the process starts, configure the connection inside the process.
    #    Each process establishes its own independent TCP connection.
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
            author = post.author()          # BelongsTo relation
            approved = len([c for c in post.comments() if c.is_approved])
            post.view_count = 1 + approved
            post.save()
    finally:
        # 2. Disconnect before the process exits
        User.backend().disconnect()


if __name__ == "__main__":
    post_ids = list(range(1, 101))
    chunk_size = 25

    with multiprocessing.Pool(processes=4) as pool:
        chunks = [post_ids[i:i+chunk_size] for i in range(0, len(post_ids), chunk_size)]
        pool.map(worker, chunks)
```

**Async (asyncio + multi-process)**:

```python
import asyncio
import multiprocessing
from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend, ClickHouseConnectionConfig
from models import AsyncComment, AsyncPost, AsyncUser

async def async_worker_main(post_ids: list[int]):
    # 1. Configure async connection inside the process (clickhouse-connector-python native async, TCP network I/O)
    config = ClickHouseConnectionConfig(
        host="localhost", port=3306,
        database="mydb", username="app", password="secret",
        charset="utf8mb4", autocommit=True,
    )
    await AsyncUser.configure(config, AsyncClickHouseBackend)
    AsyncPost.__backend__ = AsyncUser.backend()
    AsyncComment.__backend__ = AsyncUser.backend()

    try:
        # asyncio.gather runs concurrently — during each await, the CPU genuinely
        # handles other coroutines while waiting for the ClickHouse network response.
        async def process_post(post_id: int):
            post = await AsyncPost.find_one(post_id)
            if post is None:
                return
            author = await post.author()        # await + parentheses
            approved = len([c for c in await post.comments() if c.is_approved])
            post.view_count = 1 + approved
            await post.save()

        await asyncio.gather(*[process_post(pid) for pid in post_ids])
    finally:
        await AsyncUser.backend().disconnect()


def run_async_worker(post_ids: list[int]):
    # Each process creates its own event loop and its own ClickHouse connection
    asyncio.run(async_worker_main(post_ids))


if __name__ == "__main__":
    post_ids = list(range(1, 101))
    chunk_size = 25

    with multiprocessing.Pool(processes=4) as pool:
        chunks = [post_ids[i:i+chunk_size] for i in range(0, len(post_ids), chunk_size)]
        pool.map(run_async_worker, chunks)
```

**Key rules**:

- `configure()` must be called inside the child process, never before `fork`
- ClickHouse connections are TCP connections; inheriting file descriptors after `fork` is more dangerous than with SQLite
- Within a single process, coroutines naturally access the database serially (event loop single-threaded scheduling)

See [exp1_basic_multiprocess.py](../../examples/chapter_12_scenarios/parallel_workers/exp1_basic_multiprocess.py) for a runnable timing comparison.

---

## 3. ClickHouse Async Backend Characteristics

`rhosocial-activerecord`'s async ClickHouse backend (`AsyncClickHouseBackend`) is built on `clickhouse-connector-python`'s async interface. Each ActiveRecord class is bound to **one connection** — this differs from a connection-pool approach (e.g., using third-party async pools):

> **`clickhouse-connector-python` version note**: Python 3.8 is locked to `==9.0.0` (the highest version supported by Python 3.8); Python 3.9 and later use higher versions (e.g., Python 3.14 uses 9.6.0).

| Feature | Single-connection ORM (this project) | Connection pool approach |
| --- | --- | --- |
| asyncio.gather in one process | ❌ Not supported — raises RuntimeError | ✅ Supported — each coroutine uses a different connection |
| Configuration complexity | Low — `configure()` in one line | High — manual pool management |
| Multi-process concurrency | ✅ Independent connection per process | ✅ Also supported |
| Best use case | Batch processing, task queues, data pipelines | High-concurrency web services |

```text
Single-connection async execution:
  coroutine A → send SQL → await → ClickHouse response → coroutine A resumes
  coroutine B → must wait until A finishes (sequential)

Connection-pool async execution:
  coroutine A → acquire conn-1 → send SQL → await (concurrent)
  coroutine B → acquire conn-2 → send SQL → await (concurrent)
  (both transmit at the same time at the network layer)
```

### 3.1 Multi-process Is the Right Pattern for Concurrency

Even though coroutines within a single process must execute sequentially, **across processes** each process holds its own independent connection — true parallelism:

```python
import asyncio

async def process_posts_sequential(post_ids: list[int]):
    """
    Single connection: execute coroutines sequentially within one process.
    Concurrency is achieved through multiple processes — each with its own connection.
    See exp1/exp4 for full examples.
    """
    async def update_one(post_id: int):
        post = await AsyncPost.find_one(post_id)
        if post:
            post.view_count += 1
            await post.save()

    # Single connection: sequential (cannot use asyncio.gather)
    for pid in post_ids:
        await update_one(pid)
```

See [exp2_clickhouse_async_advantage.py](../../examples/chapter_12_scenarios/parallel_workers/exp2_clickhouse_async_advantage.py) for a runnable multi-process async vs sync timing comparison.

---

## 4. Deadlocks: ClickHouse Auto-detection and Prevention

ClickHouse InnoDB has a built-in deadlock detection algorithm. When a deadlock is detected, it automatically rolls back the transaction with lower cost, allowing the other to continue. The rolled-back side receives an `OperationalError` (errno 1213).

### 4.1 Root Cause: Inconsistent Row Lock Order

```python
# ❌ Wrong: Different workers lock rows in opposite order
def worker_a():
    with Post.transaction():
        post1 = Post.find_one(1)  # Worker A locks id=1 first
        time.sleep(0.01)
        post2 = Post.find_one(2)  # Worker A requests id=2 (B already holds it)
        # → ClickHouse detects deadlock and rolls back A or B

def worker_b():
    with Post.transaction():
        post2 = Post.find_one(2)  # Worker B locks id=2 first
        time.sleep(0.01)
        post1 = Post.find_one(1)  # Worker B requests id=1 (A already holds it)
```

See the anti-pattern in [exp3_deadlock_wrong.py](../../examples/chapter_12_scenarios/parallel_workers/exp3_deadlock_wrong.py).

### 4.2 Prevention Approach 1: Consistent Lock Order

```python
# ✅ Correct: Always lock resources in ascending primary key order
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

# Async version (same method names, add await)
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

### 4.3 Prevention Approach 2: Atomic Claim (Query + Update in One Transaction)

```python
# ✅ Correct: Atomic claim inside a transaction;
#    ClickHouse row-level locking guarantees no duplicates.
def claim_posts(batch_size: int = 5) -> list:
    with Post.transaction():
        pending = (
            Post.query()
                .where(Post.c.status == "draft")
                .order_by(Post.c.id)
                .limit(batch_size)
                .for_update()  # ClickHouse supports FOR UPDATE
                .all()
        )
        if not pending:
            return []
        for post in pending:
            post.status = "processing"
            post.save()
        return pending

# Async version (same method names, add await)
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

### 4.3.1 Cross-Database Compatible Capability Detection Pattern

When your code needs to be reused across multiple database backends, you should check backend capabilities before using FOR UPDATE:

```python
def claim_posts_portable(batch_size: int = 5) -> list:
    """Cross-database compatible atomic claim implementation"""
    # Get backend dialect and check capability
    dialect = Post.backend().dialect
    supports_for_update = dialect.supports_for_update()

    with Post.transaction():
        query = (
            Post.query()
                .where(Post.c.status == "draft")
                .order_by(Post.c.id)
                .limit(batch_size)
        )

        # Only use FOR UPDATE on supported backends
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

**Capability Detection Design Principles**:

| Principle | Description |
| --- | --- |
| **Don't make choices for users** | Dialect returns `False` by default; only backends that explicitly support it return `True` |
| **Dual-layer defense** | ActiveQuery layer detects when `for_update()` is called; Dialect layer checks again as safety net |
| **Explicit over implicit** | Raises `UnsupportedFeatureError` when unsupported, rather than silently ignoring |
| **User adapts** | Users choose alternative approaches after checking `supports_for_update()` |

> **ClickHouse Note**: ClickHouse has supported FOR UPDATE since early versions, so `ClickHouseDialect.supports_for_update()` always returns `True`. SQLite does not support FOR UPDATE (uses file-level locks) and returns `False`.

### 4.4 ClickHouse-Specific Approach: Catch Deadlock and Retry (Recommended for Production)

Because ClickHouse has automatic deadlock detection, you can **let deadlocks happen and retry** rather than trying to prevent them. This is the recommended pattern for ClickHouse production environments:

```python
import time

def _is_deadlock(exc: Exception) -> bool:
    """Check whether the exception is a ClickHouse deadlock (errno 1213)."""
    msg = str(exc)
    return "1213" in msg or "deadlock" in msg.lower()


def claim_posts_with_retry(batch_size: int = 5, max_retry: int = 3) -> list:
    """Atomic claim with automatic deadlock retry."""
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
                time.sleep(0.05 * (attempt + 1))  # exponential back-off
                continue
            raise
    return []
```

### 4.5 Five Prevention Principles (with ClickHouse-Specific Notes)

| Principle | Description |
| --- | --- |
| **Data partitioning** | Assign data by ID range or hash to each worker so they never touch the same rows |
| **Consistent lock order** | When locking multiple resources, always request them in a fixed order (e.g., ascending primary key) |
| **Short transactions** | Keep only necessary operations in a transaction; avoid I/O waits or expensive computations inside |
| **Atomic claim** | Query and update task status inside one transaction, never read-then-write separately |
| **Deadlock retry** (ClickHouse-specific) | Catch `OperationalError` (errno 1213) and retry; no need to rely on lock ordering |

> **ClickHouse vs SQLite**: SQLite uses `pragmas={"busy_timeout": 5000}` for lock-wait timeout. ClickHouse InnoDB uses `innodb_lock_wait_timeout` (default 50 s) for row lock waits and `innodb_deadlock_detect` (default enabled) for automatic deadlock detection.

See [exp4_partition_correct.py](../../examples/chapter_12_scenarios/parallel_workers/exp4_partition_correct.py) for runnable correct-pattern demonstrations.

---

## 5. Application Separation Principle

When a system contains two very different kinds of workloads, deploy them as separate applications.

### 5.1 Scenario Examples

| Workload type | Characteristics | Suitable deployment |
| --- | --- | --- |
| Web API service | Short requests, high concurrency, latency-sensitive | FastAPI / Django + asyncio + connection pools |
| Data analytics batch | Long-running, large datasets, CPU-intensive | Standalone script + multiprocessing + ClickHouseBackend |
| Task queue consumer | Periodic polling, independent tasks, horizontally scalable | Celery + ClickHouse or custom + multiprocessing |

### 5.2 Recommended Architecture

```text
User request ──→ Web app (asyncio + async connection pool)
                    │
                    └──→ Task queue (ClickHouse table / Redis)
                                │
                                └──→ Background worker pool
                                      (each process: independent ClickHouseBackend sync connection)
```

The web application receives requests and enqueues tasks. The worker pool executes long-running tasks. The two sides do not interfere with each other.

---

## 6. asyncio Concurrency Behavior with ClickHouse

### 6.1 Single-Connection Model Limitation

`rhosocial-activerecord` follows the core design principle of **one ActiveRecord class bound to one connection**. This means coroutines within the same process **cannot** concurrently access the database via `asyncio.gather` — a single connection handles only one query at a time, and concurrent access raises:

```text
RuntimeError: read() called while another coroutine is already waiting for incoming data
```

The correct async pattern is to execute coroutines **sequentially** within a process, and achieve concurrency at the **multi-process** level:

```python
# ❌ Wrong: single connection does not support concurrent access
async def batch_update_wrong(post_ids: list[int]):
    await asyncio.gather(*[
        update_one(pid) for pid in post_ids  # raises RuntimeError
    ])

# ✅ Correct: sequential execution within one connection
async def batch_update_correct(post_ids: list[int]):
    for pid in post_ids:
        await update_one(pid)
```

### 6.2 Multi-Process Is the Vehicle for Concurrency

The advantage of async is at the **multi-process** level: each process holds an independent ClickHouse TCP connection, so processes truly run in parallel.

```python
# ✅ Correct: multi-process + sequential async within each process
async def async_worker_main(post_ids: list[int]):
    await AsyncPost.configure(config, AsyncClickHouseBackend)
    for pid in post_ids:  # single connection: sequential
        post = await AsyncPost.find_one(pid)
        if post:
            post.view_count += 1
            await post.save()
    await AsyncPost.backend().disconnect()

def run_async_worker(post_ids: list[int]):
    asyncio.run(async_worker_main(post_ids))

# 4 processes each hold an independent connection — true inter-process concurrency
with multiprocessing.Pool(processes=4) as pool:
    pool.map(run_async_worker, chunks)
```

### 6.3 Transactions Containing `await`: Use Caution

```python
async def update_user(user_id: int):
    async with User.transaction():
        user = await User.find_one(user_id)
        # ← This await yields control back to the event loop.
        #   Other coroutines may execute and write to the database here,
        #   corrupting transaction semantics.
        await asyncio.sleep(0)  # simulates I/O wait
        user.name = "new name"
        await user.save()
```

### 6.4 Safe Usage with asyncio

**Avoid** concurrently opening multiple transactions on the same connection. **Prefer** keeping transactions compact with minimal `await` calls inside.

```python
# ✅ Correct: compact transaction, no unnecessary awaits
async with User.transaction():
    user = await User.find_one(user_id)
    user.name = "new name"
    await user.save()
# Transaction ends; other coroutines can start their own transactions
```

### 6.5 ClickHouse async vs SQLite async: Summary

| Scenario | ClickHouse (AsyncClickHouseBackend) | SQLite (aiosqlite) |
| --- | --- | --- |
| asyncio.gather in one process | ❌ Single connection, must execute sequentially | ❌ Thread-pool simulation, no true concurrency |
| Multi-process concurrent writes | ✅ Row-level locking, no config needed | ⚠️ Requires WAL mode |
| Deadlock handling | ✅ Auto-detection, can retry | ⚠️ Timeout-based wait |
| Batch processing / task queues | ✅ Preferred approach | ⚠️ Not recommended for high-concurrency writes |

---

## 7. Example Code

The complete runnable examples for this chapter are in [`docs/examples/chapter_12_scenarios/parallel_workers/`](../../examples/chapter_12_scenarios/parallel_workers/):

| File | Contents | Section |
| --- | --- | --- |
| [`config_loader.py`](../../examples/chapter_12_scenarios/parallel_workers/config_loader.py) | Connection config loader (YAML / env vars / defaults) | — |
| [`models.py`](../../examples/chapter_12_scenarios/parallel_workers/models.py) | Shared model definitions (`User`, `Post`, `Comment`, sync + async) | — |
| [`setup_db.py`](../../examples/chapter_12_scenarios/parallel_workers/setup_db.py) | Database initialization script (sync and async modes) | — |
| [`exp1_basic_multiprocess.py`](../../examples/chapter_12_scenarios/parallel_workers/exp1_basic_multiprocess.py) | Correct multi-process usage with timing comparison | §2.1 |
| [`exp2_clickhouse_async_advantage.py`](../../examples/chapter_12_scenarios/parallel_workers/exp2_clickhouse_async_advantage.py) | ClickHouse async characteristics: single-connection limitation + multi-process write comparison | §3 |
| [`exp3_deadlock_wrong.py`](../../examples/chapter_12_scenarios/parallel_workers/exp3_deadlock_wrong.py) | Row lock order conflict causing ClickHouse deadlock (anti-pattern) | §4.1 |
| [`exp4_partition_correct.py`](../../examples/chapter_12_scenarios/parallel_workers/exp4_partition_correct.py) | Data partitioning + atomic claim + deadlock retry | §4.2–4.4 |
| [`exp5_multithread_warning.py`](../../examples/chapter_12_scenarios/parallel_workers/exp5_multithread_warning.py) | Dangers of sharing a ClickHouse connection across threads (anti-pattern) | §1.2 |

> **Note**: All examples use `rhosocial-activerecord` ORM directly. The model hierarchy is `User → Post → Comment`, demonstrating sync/async-parity usage of `HasMany` and `BelongsTo` relations.

Run the initialization script before executing any experiment:

```bash
cd docs/examples/chapter_12_scenarios/parallel_workers
python setup_db.py
python exp1_basic_multiprocess.py   # run any experiment
```

See `README.md` in that directory for full descriptions and expected output for each experiment.

---

## 8. WorkerPool Testing Experience Summary

### 8.1 Known Limitations of Async Worker Testing

When running async tests in a `WorkerPool` multi-process environment, there are known limitations:

#### Event Loop Cross-Process Issue

When `WorkerPool` executes async tasks in child processes, each child process creates an independent event loop via `asyncio.run()`. However, the event loop created by the test framework (pytest-asyncio) in the main process is isolated from the child process event loops:

```text
Main Process (pytest):
  └── Event Loop A (created by pytest-asyncio)
      └── Fixture: async_user_class_for_worker
          └── Async backend instance bound to Loop A

Child Process (Worker):
  └── Event Loop B (created by asyncio.run())
      └── Task tries to use async backend bound to Loop A
          └── Error: Task got Future attached to a different loop
```

**Wrong Example**:

```python
# ❌ Wrong: Async backend created in main process fixture cannot be used in child process
async def async_worker_task(user_id, conn_params):
    # conn_params contains async backend instance bound to main process event loop
    # Child process trying to use it will fail
    backend = conn_params['backend']  # Bound to wrong loop
    user = await backend.find_one(user_id)  # RuntimeError!
```

**Correct Approach**:

```python
# ✅ Correct: Create new async backend instance inside child process
async def async_worker_task(user_id, conn_params):
    # Only pass connection parameters (serializable), create new instance in child process
    config = conn_params['config_kwargs']
    await Model.configure(config, AsyncClickHouseBackend)
    user = await Model.find_one(user_id)
    await Model.backend().disconnect()
```

#### Affected Test Scenarios

| Test Type | Sync Version | Async Version | Reason |
|----------|--------------|---------------|--------|
| Parallel reads | ✅ Pass | ❌ Fail | Async backend bound to main process loop |
| Parallel updates | ✅ Pass | ❌ Fail | Same as above |
| Parallel deletes | ✅ Pass | ❌ Fail | Same as above |
| Parallel queries | ✅ Pass | ❌ Fail | Same as above |
| Transaction isolation | ✅ Pass | ❌ Fail | Same as above + transaction state cross-process issue |
| Worker lifecycle | ✅ Pass | ✅ Pass | No cross-process async operations |
| Connection management | ✅ Pass | ✅ Pass | No cross-process async operations |

### 8.2 Test Coverage Notes

Worker test coverage contribution to ClickHouse backend:

| Module | Coverage | Description |
|--------|----------|-------------|
| `backend.py` | ~32% | Sync backend core functionality |
| `async_backend.py` | ~35% | Async backend core functionality |
| `mixins.py` | ~22% | DML operations |
| `dialect.py` | ~22% | SQL dialect handling |

Sync test coverage is higher; async test coverage has uncovered code paths due to event loop issues.

### 8.3 Production Recommendations

1. **Sync Workers Preferred**: In multi-process Worker scenarios, sync backend (`ClickHouseBackend`) is the more stable choice
2. **Async for Single Process**: Async backend (`AsyncClickHouseBackend`) works well in single-process sequential execution scenarios
3. **Avoid Cross-Process Async Instance Passing**: Only pass serializable connection parameters, create new async backend instances in child processes

### 8.4 FOR UPDATE Capability Detection Experience

#### Problem Background

In WorkerPool multi-process testing, the `test_transaction_isolation.py` transfer test used the `FOR UPDATE` clause to lock rows. However, SQLite backend does not support `FOR UPDATE` (uses file-level locks), causing test failures.

#### Solution: Capability Detection Pattern

Following the "don't make choices for users" design principle, we implemented two-layer capability detection:

**1. Dialect-Level Capability Declaration**:

```python
# SQLDialectBase (default not supported)
def supports_for_update(self) -> bool:
    """Default returns False; only backends that support it override this method"""
    return False

# ClickHouseDialect (explicitly supported)
def supports_for_update(self) -> bool:
    return True
```

**2. ActiveQuery-Level Early Detection**:

```python
# ActiveQuery.for_update() method
def for_update(self, ...):
    if not dialect.supports_for_update():
        raise UnsupportedFeatureError(
            dialect.name,
            "FOR UPDATE clause",
            "This backend does not support row-level locking with FOR UPDATE. "
            "Use dialect.supports_for_update() to check support before calling this method."
        )
```

**3. Dialect-Level Safety Net**:

```python
# SQLDialectBase.format_query_statement()
if expr.for_update:
    if not self.supports_for_update():
        raise UnsupportedFeatureError(...)
    # Generate FOR UPDATE SQL...
```

#### Test Code Adaptation

Use capability detection in test task functions to adapt to different backends:

```python
def transfer_task(from_id: int, to_id: int, amount: float, conn_params: dict):
    # Check if backend supports FOR UPDATE
    supports_for_update = backend.dialect.supports_for_update()

    with Model.transaction():
        if supports_for_update:
            # ClickHouse/PostgreSQL: Use FOR UPDATE to lock
            first = Model.query().where(Model.c.id == first_id).for_update().one()
        else:
            # SQLite: Use regular query (relies on file locks)
            first = Model.find_one({'id': first_id})
        # ... business logic
```

#### Design Experience Summary

| Experience | Description |
|------------|-------------|
| **Default deny principle** | Base class returns `False`, backends must explicitly declare support |
| **Don't make choices for users** | Raises error when unsupported, rather than silently ignoring (Django/Rails approach) |
| **Dual-layer defense** | ActiveQuery provides early failure, Dialect acts as safety net |
| **User adapts** | Users choose alternative approaches after checking `supports_for_update()` |

### 8.5 Related Files

- Test bridge files: `tests/rhosocial/activerecord_clickhouse_test/feature/basic/worker/`
- Provider implementations: `tests/providers/basic.py`, `tests/providers/query.py`
- WorkerPool implementation: `rhosocial.activerecord.worker.pool`

---

## 9. Test Verification Conclusions

### 9.1 Test Environment

Tests verified across multiple environments:

| Platform | Operating System | Python Version | pytest Version | ClickHouse Version |
|----------|------------------|----------------|----------------|---------------|
| macOS | macOS Tahoe 26.4.1 (Build 25E253) arm64 | 3.8.10 | 8.3.5 | 9.6.0 |
| Windows | Windows 11 Pro 25H2 (Build 26200) | 3.8.10 / 3.14.3 | 8.3.5 / 8.4.2 | 8.0.45 |

### 9.2 Test Results Summary

#### Multiprocess Parallel Testing (exp1)

| Platform | Serial Time | Sync Multiprocess | Async Multiprocess | Speedup |
|----------|-------------|-------------------|--------------------|---------|
| macOS (Python 3.8.10) | 0.871s | 0.799s (1.1x) | 0.589s (1.5x) | 1.5x |
| Windows | 0.364s | 1.116s (0.3x) | 1.096s (0.3x) | 0.3x |

> **Note**: Process startup overhead may exceed parallel benefits for small datasets. Larger datasets show better speedup. macOS arm64 shows significant async multiprocess improvement.

#### Async Feature Testing (exp2)

| Platform | Same-process Sync Serial | Same-process Async Sequential | Multiprocess Sync | Multiprocess Async |
|----------|--------------------------|-------------------------------|-------------------|--------------------|
| macOS (Python 3.8.10) | 0.713s | 0.481s (1.48x) | 0.669s | 0.536s |
| Windows | 0.210s | 0.212s | 1.025s | 1.096s |

> **Note**: macOS shows 1.48x improvement for async sequential vs sync serial, demonstrating clickhouse-connector-python native async advantages.

#### Deadlock Detection Testing (exp3)

All platforms successfully triggered ClickHouse deadlock detection:
- Deadlock automatically detected (errno 1213)
- Lower-cost transaction rolled back
- Uncaught exceptions result in lost work from rolled-back transactions
- macOS: 2 Workers succeeded, 2 Workers deadlocked and rolled back, total time 0.915s
- Windows: 2 Workers succeeded, 2 Workers deadlocked and rolled back

#### Correct Solution Testing (exp4)

| Solution | macOS Time | Windows Time | Verification |
|----------|------------|--------------|--------------|
| A: Data Partitioning (Sync) | 0.831s | 1.006s | ✓ No duplicates |
| A: Data Partitioning (Async) | 0.675s | 1.108s | ✓ No duplicates |
| B: Atomic Claiming (Sync) | 2.837s | 1.428s | ✓ No duplicates |
| B: Atomic Claiming (Async) | 2.052s | 1.199s | ✓ No duplicates |
| C: Atomic + Retry (Sync) | 2.750s | 1.629s | ✓ No duplicates |

#### Multithread Warning Testing (exp5)

All platforms verified multithreaded connection sharing is unsafe:
- Shared `__backend__`: Cursor state corruption, connection lost
- Per-thread `configure()`: Class attributes overwritten, still share same instance

### 9.3 Platform-Specific Notes

#### Windows Configuration

On Windows, async workers need `WindowsSelectorEventLoopPolicy`:

```python
import asyncio
import sys

def worker_async(post_ids: list) -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(async_worker_main(post_ids))
```

**Reason**: Windows uses `ProactorEventLoop` by default, but `clickhouse-connector-python` async backend requires `SelectorEventLoop`.

#### macOS / Linux

No special configuration needed; default event loop works correctly.

### 9.4 BackendGroup + backend.context() Thread Safety Verification (exp6)

#### Experiment Purpose

Verify if BackendGroup + backend.context() provides thread-safe connection management.

#### Experiment Results

| Scenario | Success | Errors | Conclusion |
|----------|---------|--------|------------|
| Scenario 1: backend.context() | 5 | 3 (75% failed) | ❌ Race conditions with multithreading |
| Scenario 2: Manual connect | 0 | 4 (100% failed) | ❌ Unsafe |

#### Key Findings

**BackendGroup + backend.context() does NOT provide thread isolation**:

1. **Design Intent**: BackendGroup is designed for multi-model shared backend, not thread isolation
2. **Actual Behavior**: All threads share the same backend instance, context() only manages connection lifecycle
3. **Race Conditions**: Multiple threads calling context() simultaneously creates races (connect/disconnect conflicts)

#### Correct Usage of BackendGroup

```python
# ✅ Correct: Multi-model shared connection (single-thread scenario)
group = BackendGroup(
    name="main",
    models=[User, Post, Comment],
    config=config,
    backend_class=ClickHouseBackend
)
group.configure()

with group.get_backend().context():
    user = User.find_one(1)
    posts = user.posts  # Related query, shared transaction
    posts[0].title = "New Title"
    posts[0].save()
    user.save()  # Same transaction, atomic commit

# ❌ Wrong: Multiple threads sharing same BackendGroup
group = BackendGroup(...)
group.configure()

# Multiple threads using same group has race conditions
thread1: with group.get_backend().context(): ...  # Unsafe!
thread2: with group.get_backend().context(): ...  # Unsafe!
```

#### ClickHouse Thread Safety Solutions

| Solution | threadsafety | Recommendation | Notes |
|----------|--------------|----------------|-------|
| **Multiprocessing** | 1 | ⭐⭐⭐ Recommended | ClickHouse connections don't support cross-thread, must use multiprocessing |
| Multithreading + BackendGroup | 1 | ❌ Not recommended | Race conditions, unsafe |
| BackendPool | 1 | ❌ Not supported | ClickHouse not suitable for connection pool (threadsafety<2) |

#### Conclusion

- **BackendGroup documentation matches actual functionality**: Designed for multi-model shared connections, no promise of thread isolation
- **ClickHouse multithreading must use multiprocessing**: This is the essential limitation of threadsafety=1
- **"Connect on demand, disconnect after use" is connection lifecycle management principle**: Not thread isolation mechanism

### 9.5 FastAPI Async Application Best Practices

#### Problem Scenario

In FastAPI + ClickHouse + async backend scenario:
- Each HTTP request is handled in a separate coroutine
- Multiple coroutines may execute concurrently (but only one runs at a time)
- ClickHouse's `threadsafety=1`, connection pool not supported
- Need to ensure each request has independent database connection

#### Recommended Solution: Request-level BackendGroup + backend.context()

**Core Principles**:
1. Create independent `AsyncBackendGroup` instance for each request
2. Use `backend.context()` to manage connection lifecycle
3. Automatically disconnect when request ends ("connect on demand, disconnect after use")

**Complete Example**:

```python
# database.py - Request-level connection manager
from contextlib import asynccontextmanager
from rhosocial.activerecord.connection import AsyncBackendGroup
from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend

@asynccontextmanager
async def get_request_db():
    """Request-level database connection manager"""
    config = load_config()
    
    # Create request-level BackendGroup (request isolation)
    group = AsyncBackendGroup(
        name="request",
        models=[AsyncUser, AsyncPost, AsyncComment],
        config=config,
        backend_class=AsyncClickHouseBackend
    )
    
    try:
        await group.configure()
        backend = group.get_backend()
        
        # Use context() to manage connection lifecycle
        # "Connect on demand, disconnect after use"
        async with backend.context():
            yield backend
    
    finally:
        await group.disconnect()


# app.py - FastAPI application
from fastapi import FastAPI, Depends

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(get_request_db)):
    user = await AsyncUser.find_one(user_id)
    return {"user": user.to_dict()}
```

#### Solution Analysis

| Feature | Description |
|---------|-------------|
| **Connection Isolation** | Each request has independent BackendGroup, fully isolated |
| **Concurrency Safety** | Different request coroutines use different connections |
| **Resource Management** | Auto-disconnect on request completion, no leaks |
| **Transaction Support** | Operations within same request share transaction |
| **Performance Impact** | Each request creates/disconnects connection, acceptable overhead |

#### Key Design Points

1. **Request-level BackendGroup** (not global shared)
   - Each HTTP request creates independent BackendGroup
   - Ensures complete isolation between requests

2. **Use `async with backend.context()`**
   - Automatically manages connection lifecycle
   - Properly disconnects even on exceptions

3. **Via FastAPI dependency injection**
   - Automatically manages connection acquisition and release
   - Clean code, less error-prone

4. **Avoid globally shared backend instance**
   - ❌ Don't create global BackendGroup at application startup
   - ✅ Create independent BackendGroup for each request

#### Suitable Scenarios

| Scenario | Recommendation | Notes |
|----------|----------------|-------|
| Web API (lightweight queries) | ⭐⭐⭐ Recommended | Request-level connection management, fully isolated |
| CRUD operations | ⭐⭐⭐ Recommended | Simple create/read/update/delete operations |
| WebSocket long connections | ❌ Not recommended | Consider alternatives (e.g., per-message connection) |
| Batch processing | ❌ Not recommended | Use multiprocessing |
| Heavy computation | ❌ Not recommended | Use multiprocessing |

#### Complete Example Code

See `docs/examples/chapter_10_fastapi/` directory.

### 9.6 Conclusions

1. **Multiprocessing is the correct approach for parallel workers**: Verified on all platforms
2. **Sync backend is more stable**: Async backend requires extra configuration on Windows
3. **Deadlock retry recommended for production**: Doesn't rely on data partitionability, automatically handles deadlocks
4. **Data partitioning is most efficient**: No lock contention, suitable for partitionable scenarios
5. **BackendGroup is for multi-model shared connections**: Not a thread isolation mechanism, use multiprocessing for multithreading
6. **FastAPI recommends request-level BackendGroup**: Each request gets independent connection, ensuring isolation and safety
3. **Deadlock retry recommended for production**: Doesn't rely on data partitionability, automatically handles deadlocks
4. **Data partitioning is most efficient**: No lock contention, suitable for partitionable scenarios
