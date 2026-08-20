# exp1_basic_multiprocess.py - Correct Multiprocess Usage (with Timing Comparison)
# docs/examples/chapter_12_scenarios/parallel_workers/exp1_basic_multiprocess.py
"""
Experiment objective: Demonstrate correct approach to multiprocess parallel processing
using real ClickHouse ActiveRecord ORM.

Key points:
  - configure() must be called within child processes, not sharing connections in parent
  - Each process independently owns its own database connection
  - Demonstrates both synchronous (BaseActiveRecord) and asynchronous (AsyncBaseActiveRecord) usage
  - Demonstrates relationships: User --(has_many)--> Post, Post --(has_many)--> Comment

ClickHouse-specific notes:
  - ClickHouse connections are network connections, each configure() establishes a new TCP connection
  - If parent process calls configure() then forks, child processes inherit connection file
    descriptors, causing write corruption
  - Correct approach: fork first (Pool creation), then configure() within child processes

Comparison experiments:
  A. Serial: Single process adds a comment to each post sequentially
  B. Multiprocess (sync): 4 processes process in parallel
  C. Multiprocess (async): 4 processes, each using asyncio coroutines

How to run:
    python setup_db.py   # Initialize database first
    python exp1_basic_multiprocess.py
"""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import sys
import time

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from rhosocial.activerecord.backend.impl.clickhouse import (  # noqa: E402
    AsyncClickHouseBackend,
    ClickHouseBackend,
)

from config_loader import load_config  # noqa: E402
from models import AsyncComment, AsyncPost, AsyncUser, Comment, Post, User  # noqa: E402

NUM_WORKERS = 4


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Get list of published post IDs
# ─────────────────────────────────────────────────────────────────────────────


def fetch_published_post_ids() -> list:
    config = load_config()
    Post.configure(config, ClickHouseBackend)
    posts = Post.query().where(Post.c.status == "published").all()
    Post.backend().disconnect()
    return [p.id for p in posts if p.id is not None]


def split_chunks(items: list, n: int) -> list:
    size = max(1, (len(items) + n - 1) // n)
    return [items[i : i + size] for i in range(0, len(items), size)]


def reset_exp_comments() -> None:
    """Delete comments inserted by this experiment (body starts with '[exp1]')"""
    config = load_config()
    Comment.configure(config, ClickHouseBackend)
    to_delete = Comment.query().where(Comment.c.body.like("[exp1]%")).all()
    for c in to_delete:
        c.delete()
    Comment.backend().disconnect()


# ─────────────────────────────────────────────────────────────────────────────
# Experiment A: Serial (Single Process)
# ─────────────────────────────────────────────────────────────────────────────


def run_serial(post_ids: list) -> int:
    """Single process serial: Add a system comment to each post"""
    config = load_config()
    User.configure(config, ClickHouseBackend)
    Post.__backend__ = User.backend()
    Comment.__backend__ = User.backend()

    bot = User.query().order_by(User.c.id).one()
    if bot is None:
        return 0

    count = 0
    for post_id in post_ids:
        post = Post.find_one(post_id)
        if post is None:
            continue
        c = Comment(
            post_id=post.id,
            user_id=bot.id,
            body=f"[exp1] Serial comment post#{post.id} by pid={os.getpid()}",
            is_approved=True,
        )
        c.save()
        count += 1

    User.backend().disconnect()
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Experiment B: Multiprocess (Synchronous ActiveRecord)
# ─────────────────────────────────────────────────────────────────────────────


def worker_sync(post_ids: list) -> int:
    """
    Child process Worker (synchronous version):
    1. Call configure() within the process, establishing independent ClickHouse network connection
    2. Use relationships to query author and add comments
    """
    # ✅ configure() called in child process, each process establishes independent TCP connection
    config = load_config()
    User.configure(config, ClickHouseBackend)
    Post.__backend__ = User.backend()
    Comment.__backend__ = User.backend()

    bot = User.query().order_by(User.c.id).one()
    if bot is None:
        return 0

    count = 0
    for post_id in post_ids:
        post = Post.find_one(post_id)
        if post is None:
            continue
        # Get author through relationship (BelongsTo descriptor, needs parentheses to call)
        author = post.author()
        author_name = author.username if author else "unknown"

        c = Comment(
            post_id=post.id,
            user_id=bot.id,
            body=f"[exp1] Multiprocess sync comment post#{post.id} (author: {author_name}) by pid={os.getpid()}",
            is_approved=True,
        )
        c.save()
        count += 1

    User.backend().disconnect()
    print(f"  [sync PID {os.getpid()}] Completed {count} posts")
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Experiment C: Multiprocess (Asynchronous ActiveRecord)
# ─────────────────────────────────────────────────────────────────────────────


async def async_process_post(post_id: int, bot_id: int) -> bool:
    """Asynchronously process a single post: query post + get related author + insert comment"""
    post = await AsyncPost.find_one(post_id)
    if post is None:
        return False
    # Get author through async relationship (AsyncBelongsTo descriptor, needs parentheses to call)
    author = await post.author()
    author_name = author.username if author else "unknown"

    c = AsyncComment(
        post_id=post.id,
        user_id=bot_id,
        body=f"[exp1] Multiprocess async comment post#{post.id} (author: {author_name}) by pid={os.getpid()}",
        is_approved=True,
    )
    await c.save()
    return True


async def async_worker_main(post_ids: list) -> int:
    """
    Async Worker main function:
    Call configure() within process, then process post list sequentially with async/await.
    Note: Coroutines within a single connection cannot run concurrently—asyncio.gather
    would cause "read() called while another coroutine is waiting" error.
    Concurrency is achieved across multiple processes: each process holds an independent
    ClickHouse connection. True single-process concurrent queries example in exp2_clickhouse_async_advantage.py.
    """
    config = load_config()
    # ✅ Async configure() also called in child process (identical method name to sync version, add await)
    await AsyncUser.configure(config, AsyncClickHouseBackend)
    backend = AsyncUser.backend()
    AsyncPost.__backend__ = backend
    AsyncComment.__backend__ = backend

    bot = await AsyncUser.query().order_by(AsyncUser.c.id).one()
    if bot is None:
        return 0

    # Single connection sequential execution: coroutines within same process share same backend
    # connection, cannot run concurrently
    # Concurrency is achieved across multiple processes with independent connections
    count = 0
    for pid in post_ids:
        if await async_process_post(pid, bot.id):
            count += 1

    await AsyncUser.backend().disconnect()
    print(f"  [async PID {os.getpid()}] Completed {count} posts")
    return count


def worker_async(post_ids: list) -> int:
    """Child process entry: Each process independently creates its own event loop"""
    return asyncio.run(async_worker_main(post_ids))


# ─────────────────────────────────────────────────────────────────────────────
# Main Program
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    post_ids = fetch_published_post_ids()
    if not post_ids:
        print("⚠️  No posts with 'published' status, please run setup_db.py first")
        sys.exit(1)

    print(f"Found {len(post_ids)} published posts\n")
    chunks = split_chunks(post_ids, NUM_WORKERS)

    # ─── Experiment A: Serial ───
    print("=== Experiment A: Serial Processing (Single Process, Synchronous ActiveRecord) ===")
    t0 = time.perf_counter()
    serial_count = run_serial(post_ids)
    t_serial = time.perf_counter() - t0
    print(f"Serial completed {serial_count} posts, time: {t_serial:.3f}s")

    reset_exp_comments()

    # ─── Experiment B: Multiprocess Sync ───
    print(f"\n=== Experiment B: {NUM_WORKERS} Processes Parallel (Synchronous ActiveRecord) ===")
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        results_b = pool.map(worker_sync, chunks)
    t_sync = time.perf_counter() - t0
    total_b = sum(results_b)
    print(f"Parallel completed {total_b} posts, time: {t_sync:.3f}s")
    if t_sync > 0:
        print(f"Speedup: {t_serial / t_sync:.1f}x (theoretical max {NUM_WORKERS}x)")

    reset_exp_comments()

    # ─── Experiment C: Multiprocess Async ───
    print(f"\n=== Experiment C: {NUM_WORKERS} Processes Parallel (Asynchronous ActiveRecord) ===")
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        results_c = pool.map(worker_async, chunks)
    t_async = time.perf_counter() - t0
    total_c = sum(results_c)
    print(f"Parallel completed {total_c} posts, time: {t_async:.3f}s")
    if t_async > 0:
        print(f"Speedup: {t_serial / t_async:.1f}x (theoretical max {NUM_WORKERS}x)")

    reset_exp_comments()

    print(f"\n{'=' * 55}")
    print("Conclusion:")
    print(f"  Serial (sync): {t_serial:.3f}s")
    print(f"  Multiprocess sync: {t_sync:.3f}s  ({t_serial / t_sync:.1f}x)")
    print(f"  Multiprocess async: {t_async:.3f}s  ({t_serial / t_async:.1f}x)")
    print("""
Key principle: configure() must be called within child processes, applies to both
sync and async versions with identical method names.

Important differences between ClickHouse and SQLite:
  - configure() establishes real TCP network connections, inheriting connection file
    descriptors after fork is more dangerous
  - Async backend (clickhouse-connector-python native async) is based on real TCP network I/O,
    unlike SQLite's aiosqlite thread simulation
  - Experiment C's async version typically shows more speedup than SQLite async
    version (see exp2)
""")


if __name__ == "__main__":
    main()
