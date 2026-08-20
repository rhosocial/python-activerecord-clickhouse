# exp5_multithread_warning.py - Issues with Multithreaded ClickHouse Connection Sharing (Anti-pattern)
# docs/examples/chapter_12_scenarios/parallel_workers/exp5_multithread_warning.py
"""
Experiment objective:
    Demonstrate the danger of multithreaded ClickHouse connection sharing, and that
    per-thread configure() doesn't solve the problem.

Key differences from SQLite version:
    SQLite has check_same_thread=True protection, cross-thread access directly raises error.
    ClickHouse (clickhouse-connector-python) doesn't have this protection,
    but connection objects are also not thread-safe—concurrent operations cause cursor state corruption.

Scenario descriptions:
    Scenario 1: Shared __backend__ (dangerous)
        Multiple threads share the same ClickHouseBackend instance, concurrent queries/writes cause cursor corruption.
        clickhouse-connector-python explicitly states connections don't support multi-threaded concurrent use.

    Scenario 2: Each thread calls configure() (❌ Doesn't work)
        configure() writes to class attribute __backend__, later ones overwrite earlier ones.
        All threads actually share the last configure()'s created backend instance.
        Demonstrate by collecting id(Post.backend()) from each thread to prove instances aren't independent.

Conclusion:
    Multithreading cannot solve connection sharing problem, correct solution is multiprocessing
    (each process has independent connection).

How to run:
    python setup_db.py   # Initialize database first
    python exp5_multithread_warning.py
"""

from __future__ import annotations

import sys
import os
import threading
import time
from typing import List

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend  # noqa: E402

from config_loader import load_config  # noqa: E402
from models import Post  # noqa: E402

NUM_THREADS = 4


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1: Shared __backend__ (dangerous, possible cursor corruption)
# ─────────────────────────────────────────────────────────────────────────────


def scenario_1_shared_backend() -> None:
    """❌ Dangerous: Multiple threads share the same ClickHouseBackend instance."""
    print("=== Scenario 1: Shared __backend__ (❌ Dangerous) ===")

    # Initialize in main thread (analogous to parent process configure then fork)
    config = load_config()
    Post.configure(config, ClickHouseBackend)
    shared_backend_id = id(Post.backend())
    print(f"  Main thread backend id: {shared_backend_id}")

    errors: List[str] = []
    lock = threading.Lock()

    def thread_worker(thread_id: int) -> None:
        # All threads share the same backend, concurrent operations may cause cursor state corruption
        try:
            # Two threads execute queries simultaneously, cursor may be overwritten by another thread
            posts = Post.query().where(Post.c.id > 0).limit(3).all()
            time.sleep(0.01)  # Increase concurrency window
            # Query again, check if results are consistent
            posts2 = Post.query().where(Post.c.id > 0).limit(3).all()
            if len(posts) != len(posts2):
                with lock:
                    errors.append(f"Thread {thread_id}: Inconsistent query results ({len(posts)} vs {len(posts2)})")
        except Exception as e:
            with lock:
                errors.append(f"Thread {thread_id} exception: {e!s:.80}")

    threads = [threading.Thread(target=thread_worker, args=(i,)) for i in range(NUM_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errors:
        print(f"  ⚠️  Found {len(errors)} errors or inconsistencies (proves multithreaded connection sharing is unsafe):")
        for err in errors[:3]:
            print(f"    - {err}")
    else:
        print("  No errors in this run (timing factor, run multiple times to reproduce cursor corruption)")
        print("  Note: clickhouse-connector-python explicitly states connections don't support multi-threaded concurrent use")

    try:
        Post.backend().disconnect()
    except Exception:
        pass
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2: Each thread calls configure() (❌ Doesn't work, class attribute overwritten)
# ─────────────────────────────────────────────────────────────────────────────


def scenario_2_per_thread_configure() -> None:
    """❌ Doesn't work: Each thread calls configure(), but __backend__ is a class attribute, later overwrites earlier."""
    print("=== Scenario 2: Each thread calls configure() (❌ Doesn't work, class attributes overwrite each other) ===")

    backend_ids: List[int] = []
    lock = threading.Lock()

    def thread_worker(thread_id: int) -> None:
        config = load_config()
        # Each thread calls configure(), appears to be independent
        Post.configure(config, ClickHouseBackend)
        time.sleep(0.02)  # Wait for all threads to complete configure
        # Collect backend instance id
        with lock:
            backend_ids.append(id(Post.backend()))

    threads = [threading.Thread(target=thread_worker, args=(i,)) for i in range(NUM_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    unique_ids = set(backend_ids)
    print(f"  {NUM_THREADS} threads each called configure(), actual backend instance count: {len(unique_ids)}")
    print(f"  (Expected {NUM_THREADS}, got {len(unique_ids)})")
    if len(unique_ids) == 1:
        print("  ❌ All threads share the same backend instance — class attribute __backend__ overwritten by last configure()")
    else:
        print("  ⚠️  Multiple instances exist (timing factor), but still unstable, should not rely on this behavior")

    try:
        Post.backend().disconnect()
    except Exception:
        pass
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main Program
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    print("ClickHouse Multithreaded Connection Sharing Issue Demo (Anti-pattern)")
    print("Note: ClickHouse doesn't have SQLite's check_same_thread protection, but also doesn't support concurrent connection sharing\n")

    scenario_1_shared_backend()
    scenario_2_per_thread_configure()

    print("=" * 60)
    print("Conclusion:")
    print("""
  clickhouse-connector-python official documentation clearly states:
    "A Connection object is not thread-safe. Queries in multiple threads
     must each use their own connection."

  Multithreading + shared __backend__ is undefined behavior, may cause:
    - Cursor state corruption (one thread's query results overwritten by another)
    - Transaction boundary confusion (BEGIN/COMMIT order mixed)
    - Connection state corruption (auth info, encoding settings overwritten)

  Per-thread configure() doesn't solve the problem:
    - __backend__ is a class attribute, all threads share the same class, later overwrites earlier
    - Even if each configure() succeeds, other threads immediately use the same backend

  Correct solution: Multiprocessing
    - Each process has independent memory space, __backend__ not shared
    - Each process calls configure() to establish independent ClickHouse TCP connection
    - Processes coordinate task distribution via multiprocessing.Pool / Queue
    - See exp1_basic_multiprocess.py and exp4_partition_correct.py
""")


if __name__ == "__main__":
    main()
