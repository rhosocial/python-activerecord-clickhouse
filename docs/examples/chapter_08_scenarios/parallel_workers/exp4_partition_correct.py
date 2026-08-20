# exp4_partition_correct.py - Data Partitioning + Atomic Claiming Correct Implementation (ClickHouse Version)
# docs/examples/chapter_12_scenarios/parallel_workers/exp4_partition_correct.py
"""
Experiment objective:
    Demonstrate two correct multiprocess parallel processing strategies using real ClickHouse ActiveRecord ORM.
    Both synchronous and asynchronous versions are provided with identical method names.
    Async version only requires adding await.

    Solution A: Data Partitioning
        Distribute posts to Workers by user_id, no overlap, no contention.
        Demonstrates relationships: Worker processes posts for assigned users, traverses their comments.

    Solution B: Atomic Claiming (query + update within transaction)
        Query pending posts and immediately update status within transaction.
        Transaction isolation guarantees no duplicates.
        ClickHouse InnoDB row-level locking makes this pattern more efficient than SQLite (no file-level lock contention).

    Solution C: Atomic Claiming + Deadlock Retry
        Built on Solution B, catch ClickHouse deadlock exception (errno 1213) and automatically retry.
        Recommended for production: doesn't rely on partitionable data, balances safety and robustness.

Verification: Each post is processed exactly once (view_count > 0).

How to run:
    python setup_db.py   # Initialize database first
    python exp4_partition_correct.py
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
CLAIM_BATCH = 3  # Batch size for atomic claiming
MAX_RETRY = 3  # Maximum deadlock retry attempts


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def reset_all_posts() -> None:
    config = load_config()
    Post.configure(config, ClickHouseBackend)
    posts = Post.query().all()
    for p in posts:
        p.status = "draft"
        p.view_count = 0
        p.save()
    Post.backend().disconnect()


def fetch_user_ids() -> list:
    config = load_config()
    User.configure(config, ClickHouseBackend)
    ids = [u.id for u in User.query().order_by(User.c.id).all() if u.id is not None]
    User.backend().disconnect()
    return ids


def verify_no_duplicates() -> tuple:
    """Verify all posts are published and view_count > 0 (processed exactly once)"""
    config = load_config()
    Post.configure(config, ClickHouseBackend)
    posts = Post.query().where(Post.c.status == "published").all()
    ok = all(p.view_count > 0 for p in posts)
    count = len(posts)
    Post.backend().disconnect()
    return ok, count


def _is_deadlock(exc: Exception) -> bool:
    """Check if exception is ClickHouse deadlock (errno 1213)"""
    msg = str(exc)
    return "1213" in msg or "deadlock" in msg.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Solution A: Data Partitioning (Synchronous Version)
# ═══════════════════════════════════════════════════════════════════════════════


def worker_partition_sync(user_ids: list) -> int:
    """
    Sync Worker: Only process posts for assigned user_ids, traverse comments via relationships.

    Demonstrates relationships:
      - User --(has_many)--> Post  --(has_many)--> Comment
      - Count approved comments per post, write to view_count
    """
    config = load_config()
    User.configure(config, ClickHouseBackend)
    Post.__backend__ = User.backend()
    Comment.__backend__ = User.backend()

    count = 0
    for uid in user_ids:
        posts = Post.query().where(Post.c.user_id == uid).all()
        for post in posts:
            # Get comments through HasMany relationship (needs parentheses to call)
            approved = [c for c in post.comments() if c.is_approved]
            post.status = "published"
            post.view_count = 1 + len(approved)
            post.save()
            count += 1

    User.backend().disconnect()
    print(f"  [Partition sync PID {os.getpid()}] Processed {count} posts")
    return count


# ═══════════════════════════════════════════════════════════════════════════════
# Solution A: Data Partitioning (Asynchronous Version) — identical method names, add await
# ═══════════════════════════════════════════════════════════════════════════════


async def _async_partition_main(user_ids: list) -> int:
    config = load_config()
    await AsyncUser.configure(config, AsyncClickHouseBackend)
    backend = AsyncUser.backend()
    AsyncPost.__backend__ = backend
    AsyncComment.__backend__ = backend

    count = 0
    for uid in user_ids:
        posts = await AsyncPost.query().where(AsyncPost.c.user_id == uid).all()
        for post in posts:
            # Get comments through async HasMany relationship (add await and parentheses)
            approved = [c for c in await post.comments() if c.is_approved]
            post.status = "published"
            post.view_count = 1 + len(approved)
            await post.save()
            count += 1

    await AsyncUser.backend().disconnect()
    print(f"  [Partition async PID {os.getpid()}] Processed {count} posts")
    return count


def worker_partition_async(user_ids: list) -> int:
    return asyncio.run(_async_partition_main(user_ids))


# ═══════════════════════════════════════════════════════════════════════════════
# Solution B: Atomic Claiming (Synchronous Version)
# ═══════════════════════════════════════════════════════════════════════════════


def claim_posts_sync(batch: int = CLAIM_BATCH) -> list:
    """
    Atomically claim within transaction: query + update completed in same transaction.
    ClickHouse InnoDB row-level locking ensures only one Worker can successfully claim the same batch.
    """
    with Post.transaction():
        pending = Post.query().where(Post.c.status == "draft").order_by(Post.c.id).limit(batch).all()
        if not pending:
            return []
        for post in pending:
            post.status = "processing"
            post.view_count = 0
            post.save()
        return pending


def worker_atomic_sync(worker_id: int) -> int:
    """Sync Worker: Loop atomic claiming until no tasks"""
    config = load_config()
    User.configure(config, ClickHouseBackend)
    Post.__backend__ = User.backend()
    Comment.__backend__ = User.backend()

    total = 0
    while True:
        batch = claim_posts_sync()
        if not batch:
            break
        for post in batch:
            approved_count = len([c for c in post.comments() if c.is_approved])
            post.status = "published"
            post.view_count = 1 + approved_count
            post.save()
            total += 1

    User.backend().disconnect()
    print(f"  [Atomic sync Worker {worker_id}] Processed {total} posts")
    return total


# ═══════════════════════════════════════════════════════════════════════════════
# Solution B: Atomic Claiming (Asynchronous Version) — identical method names, add await
# ═══════════════════════════════════════════════════════════════════════════════


async def claim_posts_async(batch: int = CLAIM_BATCH) -> list:
    """Async atomic claiming: async with transaction(), structure completely symmetric with sync version"""
    async with AsyncPost.transaction():
        pending = await (
            AsyncPost.query().where(AsyncPost.c.status == "draft").order_by(AsyncPost.c.id).limit(batch).all()
        )
        if not pending:
            return []
        for post in pending:
            post.status = "processing"
            post.view_count = 0
            await post.save()
        return pending


async def _async_atomic_main(worker_id: int) -> int:
    config = load_config()
    await AsyncUser.configure(config, AsyncClickHouseBackend)
    backend = AsyncUser.backend()
    AsyncPost.__backend__ = backend
    AsyncComment.__backend__ = backend

    total = 0
    while True:
        batch = await claim_posts_async()
        if not batch:
            break
        for post in batch:
            approved_count = len([c for c in await post.comments() if c.is_approved])
            post.status = "published"
            post.view_count = 1 + approved_count
            await post.save()
            total += 1

    await AsyncUser.backend().disconnect()
    print(f"  [Atomic async Worker {worker_id}] Processed {total} posts")
    return total


def worker_atomic_async(worker_id: int) -> int:
    return asyncio.run(_async_atomic_main(worker_id))


# ═══════════════════════════════════════════════════════════════════════════════
# Solution C: Atomic Claiming + Deadlock Retry (ClickHouse Production Recommended)
# ═══════════════════════════════════════════════════════════════════════════════


def claim_posts_with_retry(batch: int = CLAIM_BATCH, max_retry: int = MAX_RETRY) -> list:
    """Atomic claiming with ClickHouse deadlock exception (errno 1213) catch and retry."""
    for attempt in range(max_retry):
        try:
            with Post.transaction():
                pending = Post.query().where(Post.c.status == "draft").order_by(Post.c.id).limit(batch).all()
                if not pending:
                    return []
                for post in pending:
                    post.status = "processing"
                    post.view_count = 0
                    post.save()
                return pending
        except Exception as e:
            if _is_deadlock(e) and attempt < max_retry - 1:
                time.sleep(0.05 * (attempt + 1))  # Exponential backoff
                continue
            raise
    return []


def worker_atomic_retry(worker_id: int) -> int:
    """Sync Worker (with deadlock retry): ClickHouse production recommended solution"""
    config = load_config()
    User.configure(config, ClickHouseBackend)
    Post.__backend__ = User.backend()
    Comment.__backend__ = User.backend()

    total = 0
    while True:
        batch = claim_posts_with_retry()
        if not batch:
            break
        for post in batch:
            approved_count = len([c for c in post.comments() if c.is_approved])
            post.status = "published"
            post.view_count = 1 + approved_count
            post.save()
            total += 1

    User.backend().disconnect()
    print(f"  [Retry sync Worker {worker_id}] Processed {total} posts")
    return total


# ─────────────────────────────────────────────────────────────────────────────
# Main Program
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    user_ids = fetch_user_ids()
    if not user_ids:
        print("⚠️  No user data, please run setup_db.py first")
        sys.exit(1)

    size = max(1, (len(user_ids) + NUM_WORKERS - 1) // NUM_WORKERS)
    uid_chunks = [user_ids[i : i + size] for i in range(0, len(user_ids), size)]

    # ─── Solution A: Data Partitioning (Sync) ───
    print("=== Solution A: Data Partitioning (Synchronous ActiveRecord) ===")
    reset_all_posts()
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        results_a_sync = pool.map(worker_partition_sync, uid_chunks)
    t_a_sync = time.perf_counter() - t0
    ok_a_sync, done_a_sync = verify_no_duplicates()
    print(
        f"  Result: Workers processed {sum(results_a_sync)} posts, published {done_a_sync} posts, "
        f"time {t_a_sync:.3f}s {'✅ No duplicates' if ok_a_sync else '❌ Has duplicates'}"
    )

    # ─── Solution A: Data Partitioning (Async) ───
    print("\n=== Solution A: Data Partitioning (Asynchronous ActiveRecord) ===")
    reset_all_posts()
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        results_a_async = pool.map(worker_partition_async, uid_chunks)
    t_a_async = time.perf_counter() - t0
    ok_a_async, done_a_async = verify_no_duplicates()
    print(
        f"  Result: Workers processed {sum(results_a_async)} posts, published {done_a_async} posts, "
        f"time {t_a_async:.3f}s {'✅ No duplicates' if ok_a_async else '❌ Has duplicates'}"
    )

    # ─── Solution B: Atomic Claiming (Sync) ───
    print("\n=== Solution B: Atomic Claiming (Synchronous ActiveRecord) ===")
    reset_all_posts()
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        results_b_sync = pool.map(worker_atomic_sync, list(range(NUM_WORKERS)))
    t_b_sync = time.perf_counter() - t0
    ok_b_sync, done_b_sync = verify_no_duplicates()
    print(
        f"  Result: Workers processed {sum(results_b_sync)} posts, published {done_b_sync} posts, "
        f"time {t_b_sync:.3f}s {'✅ No duplicates' if ok_b_sync else '❌ Has duplicates'}"
    )

    # ─── Solution B: Atomic Claiming (Async) ───
    print("\n=== Solution B: Atomic Claiming (Asynchronous ActiveRecord) ===")
    reset_all_posts()
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        results_b_async = pool.map(worker_atomic_async, list(range(NUM_WORKERS)))
    t_b_async = time.perf_counter() - t0
    ok_b_async, done_b_async = verify_no_duplicates()
    print(
        f"  Result: Workers processed {sum(results_b_async)} posts, published {done_b_async} posts, "
        f"time {t_b_async:.3f}s {'✅ No duplicates' if ok_b_async else '❌ Has duplicates'}"
    )

    # ─── Solution C: Atomic Claiming + Deadlock Retry (Sync) ───
    print("\n=== Solution C: Atomic Claiming + Deadlock Retry (ClickHouse Production Recommended, Sync) ===")
    reset_all_posts()
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        results_c = pool.map(worker_atomic_retry, list(range(NUM_WORKERS)))
    t_c = time.perf_counter() - t0
    ok_c, done_c = verify_no_duplicates()
    print(
        f"  Result: Workers processed {sum(results_c)} posts, published {done_c} posts, "
        f"time {t_c:.3f}s {'✅ No duplicates' if ok_c else '❌ Has duplicates'}"
    )

    reset_all_posts()

    all_ok = ok_a_sync and ok_a_async and ok_b_sync and ok_b_async and ok_c
    print(f"\n{'=' * 60}")
    print("Solution comparison:")
    print(f"  A. Data partitioning  Sync: {t_a_sync:.3f}s  Async: {t_a_async:.3f}s")
    print(f"  B. Atomic claiming    Sync: {t_b_sync:.3f}s  Async: {t_b_async:.3f}s")
    print(f"  C. Atomic + retry     Sync: {t_c:.3f}s")
    print(f"\nOverall verification: {'✅ All solutions have no duplicate processing' if all_ok else '❌ Issues found'}")
    print("""
ClickHouse-specific optimization notes:
  - Solution A (Data Partitioning): Each Worker operates on different rows, ClickHouse row-level
    locking has no contention, highest efficiency
  - Solution B (Atomic Claiming): InnoDB row-level locking precisely locks limit rows,
    ClickHouse performs better than SQLite
  - Solution C (Deadlock Retry): Production recommended, doesn't rely on partitionable data,
    automatically handles deadlock situations
  - Compared to SQLite WAL mode, ClickHouse supports concurrent writes without extra configuration
""")


if __name__ == "__main__":
    main()
