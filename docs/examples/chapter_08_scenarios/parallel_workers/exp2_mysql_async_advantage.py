# exp2_clickhouse_async_advantage.py - ClickHouse Async Features and Multiprocess Concurrent Writes
# docs/examples/chapter_12_scenarios/parallel_workers/exp2_clickhouse_async_advantage.py
"""
Experiment objective:
    Explain the single-connection limitation of clickhouse-connector-python async backend
    (AsyncClickHouseBackend), and how ClickHouse row-level locking enables multiprocess concurrent
    writes without extra configuration.

Experiment has two parts:

  Part 1 — Single-connection limitation (sync vs async within same process)
    Within a single process, synchronous serial vs asynchronous sequential (single-connection
    limitation: cannot use asyncio.gather for concurrency).
    clickhouse-connector-python async backend is single-connection, concurrent access raises RuntimeError.
    Conclusion: Under single-connection, async and sync have similar performance;
    concurrency advantage is realized across multiple processes.

  Part 2 — Multiprocess concurrent writes (no WAL mode configuration needed)
    ClickHouse InnoDB defaults to row-level locking, multiple processes writing to different
    rows won't block each other.
    Contrast with SQLite: default file locking serializes all writes, requires WAL mode
    for concurrency.
    Conclusion: ClickHouse supports true concurrent writes out of the box.

How to run:
    python setup_db.py   # Initialize database first
    python exp2_clickhouse_async_advantage.py
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
from models import AsyncPost, Post  # noqa: E402

NUM_WORKERS = 4


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def fetch_all_post_ids() -> list:
    config = load_config()
    Post.configure(config, ClickHouseBackend)
    ids = [p.id for p in Post.query().order_by(Post.c.id).all() if p.id is not None]
    Post.backend().disconnect()
    return ids


def split_chunks(items: list, n: int) -> list:
    size = max(1, (len(items) + n - 1) // n)
    return [items[i : i + size] for i in range(0, len(items), size)]


def reset_posts(all_ids: list) -> None:
    config = load_config()
    Post.configure(config, ClickHouseBackend)
    for post_id in all_ids:
        post = Post.find_one(post_id)
        if post:
            post.view_count = 0
            post.save()
    Post.backend().disconnect()


# ─────────────────────────────────────────────────────────────────────────────
# Part 1: Async concurrency within same process (compare with sync serial)
# ─────────────────────────────────────────────────────────────────────────────


def run_sync_sequential(post_ids: list) -> float:
    """Synchronous serial update of post view_count, with timing."""
    config = load_config()
    Post.configure(config, ClickHouseBackend)

    t0 = time.perf_counter()
    for post_id in post_ids:
        post = Post.find_one(post_id)
        if post:
            post.view_count += 1
            post.save()
    elapsed = time.perf_counter() - t0

    Post.backend().disconnect()
    return elapsed


async def _update_post_async(post_id: int) -> None:
    post = await AsyncPost.find_one(post_id)
    if post:
        post.view_count += 1
        await post.save()


async def run_async_concurrent(post_ids: list) -> float:
    """Asynchronous sequential update of post view_count, with timing.

    Note: rhosocial-activerecord's single-connection model means coroutines within
    the same process cannot access the database concurrently (asyncio.gather would
    cause "read() called while another coroutine is waiting" error).
    Async advantage is realized across multiple processes: each process holds an
    independent connection, enabling true concurrency between processes.
    """
    config = load_config()
    await AsyncPost.configure(config, AsyncClickHouseBackend)

    t0 = time.perf_counter()
    # Single connection: coroutines must execute sequentially, cannot run concurrently
    for pid in post_ids:
        await _update_post_async(pid)
    elapsed = time.perf_counter() - t0

    await AsyncPost.backend().disconnect()
    return elapsed


# ─────────────────────────────────────────────────────────────────────────────
# Part 2: Multiprocess concurrent writes (row-level locking, no WAL config needed)
# ─────────────────────────────────────────────────────────────────────────────


def sync_worker(post_ids: list) -> tuple:
    """Sync Worker: Update assigned posts, each process has independent connection."""
    config = load_config()
    Post.configure(config, ClickHouseBackend)

    t0 = time.perf_counter()
    count = 0
    for post_id in post_ids:
        post = Post.find_one(post_id)
        if post:
            post.view_count += 1
            post.save()
            count += 1
    elapsed = time.perf_counter() - t0

    Post.backend().disconnect()
    return count, elapsed


async def _async_worker_main(post_ids: list) -> tuple:
    config = load_config()
    await AsyncPost.configure(config, AsyncClickHouseBackend)
    # Single connection: coroutines execute sequentially (concurrency is across processes)
    t0 = time.perf_counter()
    for pid in post_ids:
        await _update_post_async(pid)
    elapsed = time.perf_counter() - t0
    await AsyncPost.backend().disconnect()
    return len(post_ids), elapsed


def async_worker(post_ids: list) -> tuple:
    return asyncio.run(_async_worker_main(post_ids))


# ─────────────────────────────────────────────────────────────────────────────
# Main Program
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    all_ids = fetch_all_post_ids()
    if not all_ids:
        print("⚠️  No post data, please run setup_db.py first")
        sys.exit(1)

    print(f"Experiment setup: {NUM_WORKERS} processes, {len(all_ids)} posts total\n")
    chunks = split_chunks(all_ids, NUM_WORKERS)

    # ─── Part 1: sync vs async within same process ───
    print("=" * 60)
    print("Part 1: Sync serial vs Async sequential within same process (single-connection limitation)")
    print("=" * 60)

    reset_posts(all_ids)
    t_sync_single = run_sync_sequential(all_ids)
    print(f"  Sync serial: {len(all_ids)} posts, time: {t_sync_single:.3f}s")

    reset_posts(all_ids)
    t_async_single = asyncio.run(run_async_concurrent(all_ids))
    print(f"  Async concurrent: {len(all_ids)} posts, time: {t_async_single:.3f}s")
    if t_async_single > 0:
        ratio = t_sync_single / t_async_single
        print(f"  Async/Sync ratio: {ratio:.2f}x (similar under single-connection, concurrency advantage across processes)")

    # ─── Part 2: Multiprocess concurrent writes ───
    print(f"\n{'=' * 60}")
    print("Part 2: Multiprocess concurrent writes (ClickHouse row-level locking, no WAL config needed)")
    print("=" * 60)

    reset_posts(all_ids)
    print(f"\n  Sync multiprocess ({NUM_WORKERS} processes):")
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        results_sync = pool.map(sync_worker, chunks)
    t_mp_sync = time.perf_counter() - t0
    total_sync = sum(r[0] for r in results_sync)
    print(f"  Processed {total_sync} posts, time: {t_mp_sync:.3f}s")

    reset_posts(all_ids)
    print(f"\n  Async multiprocess ({NUM_WORKERS} processes, asyncio sequential within each process):")
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        results_async = pool.map(async_worker, chunks)
    t_mp_async = time.perf_counter() - t0
    total_async = sum(r[0] for r in results_async)
    print(f"  Processed {total_async} posts, time: {t_mp_async:.3f}s")

    reset_posts(all_ids)

    print(f"\n{'=' * 60}")
    print("Summary:")
    print(f"  Part 1 — Same process sync serial: {t_sync_single:.3f}s  async sequential: {t_async_single:.3f}s")
    print(f"  Part 2 — Multiprocess sync: {t_mp_sync:.3f}s  Multiprocess async: {t_mp_async:.3f}s")
    print("""
Conclusion:
  rhosocial-activerecord uses a single-connection model (one ActiveRecord class bound to one connection).
  Single-connection limitation: Coroutines within same process cannot access database concurrently
  —asyncio.gather would cause conflicts.
  Concurrency is achieved across multiple processes: each process holds independent ClickHouse TCP connection,
  enabling true concurrency between processes.

  ClickHouse multiprocess concurrent writes require no extra configuration (no WAL, no journal_mode),
  InnoDB row-level locking by default allows multiple processes to write different rows without
  blocking each other.

  Async (AsyncClickHouseBackend) advantages:
  - await doesn't block event loop, can handle other tasks while waiting for I/O
  - Multiprocess + async combination is more efficient than pure multiprocess sync under high-latency networks
  - Note: Connection pooling is needed for true single-process concurrent queries (this project uses single-connection model)
""")


if __name__ == "__main__":
    main()
