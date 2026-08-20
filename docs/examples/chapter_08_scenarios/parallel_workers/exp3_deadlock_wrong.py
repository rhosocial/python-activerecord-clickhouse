# exp3_deadlock_wrong.py - Row Lock Order Conflict Causing Deadlock (Anti-pattern)
# docs/examples/chapter_12_scenarios/parallel_workers/exp3_deadlock_wrong.py
"""
Experiment objective:
    Demonstrate that when multiprocess concurrent writes have inconsistent lock ordering,
    ClickHouse detects deadlock and forcibly rolls back one of the transactions (raises
    OperationalError/DatabaseError, errno=1213).

Deadlock scenario:
    Two groups of Workers update the same set of posts in opposite order:
    - Worker group A (even Workers): Lock rows with smaller IDs first, then larger IDs
    - Worker group B (odd Workers): Lock rows with larger IDs first, then smaller IDs

    When A holds lock on row 1 and waits for row 2, while B holds lock on row 2 and
    waits for row 1, ClickHouse InnoDB automatically detects the deadlock and rolls back
    one transaction, allowing the other to proceed.

Note:
    - This is an anti-pattern demonstrating unsafe lock ordering
    - ClickHouse deadlock detection is automatic, the rolled-back process receives OperationalError
    - Correct solution see exp4_partition_correct.py: Always lock resources in ascending order

How to run:
    python setup_db.py   # Initialize database first
    python exp3_deadlock_wrong.py
"""

from __future__ import annotations

import multiprocessing
import os
import sys
import time

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend  # noqa: E402

from config_loader import load_config  # noqa: E402
from models import Post  # noqa: E402

NUM_WORKERS = 4
# Number of post IDs each Worker competes for (intentionally overlapping to create deadlock opportunity)
BATCH_IDS = [1, 2, 3, 4, 5]  # All Workers try to update these rows


def worker_wrong_order(args: tuple) -> dict:
    """
    ❌ Anti-pattern: Worker decides lock order based on worker_id parity.
    Even Workers use ascending order (1→2→3…), odd Workers use descending order (…3→2→1).
    Inconsistent lock ordering makes deadlock highly likely with concurrent Workers.
    """
    worker_id, post_ids = args
    config = load_config()
    Post.configure(config, ClickHouseBackend)
    Post.__backend__ = Post.backend()

    # Odd Workers reverse order to create lock order conflict with even Workers
    if worker_id % 2 == 1:
        ordered_ids = list(reversed(post_ids))
    else:
        ordered_ids = list(post_ids)

    result = {
        "worker_id": worker_id,
        "success": [],
        "deadlock": False,
        "error": None,
    }

    try:
        with Post.transaction():
            for post_id in ordered_ids:
                post = Post.find_one(post_id)
                if post is None:
                    continue
                # Simulate processing time to increase deadlock window
                time.sleep(0.01)
                post.view_count += 1
                post.save()
                result["success"].append(post_id)
    except Exception as e:
        err_str = str(e)
        # ClickHouse deadlock error code is 1213
        if "1213" in err_str or "deadlock" in err_str.lower():
            result["deadlock"] = True
            result["error"] = f"Deadlock (ClickHouse errno 1213): {err_str[:80]}"
        else:
            result["error"] = f"Other error: {err_str[:80]}"
    finally:
        try:
            Post.backend().disconnect()
        except Exception:
            pass

    status = "💀 Deadlock rollback" if result["deadlock"] else ("✅ Success" if not result["error"] else "❌ Error")
    print(f"  Worker {worker_id} ({status}): order={ordered_ids[:3]}…, succeeded={len(result['success'])} posts")
    if result["error"]:
        print(f"    → {result['error']}")
    return result


def verify_results() -> dict:
    """Count final results: view_count > 0 indicates successfully processed."""
    config = load_config()
    Post.configure(config, ClickHouseBackend)
    posts = Post.query().where(Post.c.id.in_(BATCH_IDS)).all()
    stats = {p.id: p.view_count for p in posts}
    Post.backend().disconnect()
    return stats


def main() -> None:
    print("=== Anti-pattern: Inconsistent Lock Order (ClickHouse Deadlock Demo) ===\n")
    print(f"All {NUM_WORKERS} Workers compete for the same post IDs: {BATCH_IDS}")
    print("Even Workers lock in ascending order, odd Workers in descending order, creating deadlock conditions\n")

    args = [(i, BATCH_IDS) for i in range(NUM_WORKERS)]

    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(worker_wrong_order, args)
    elapsed = time.perf_counter() - t0

    # Statistics
    deadlock_count = sum(1 for r in results if r["deadlock"])
    success_count = sum(1 for r in results if not r["error"])
    error_count = sum(1 for r in results if r["error"] and not r["deadlock"])

    print(f"\nTime elapsed: {elapsed:.3f}s")
    print(f"Results: {success_count} Workers succeeded, {deadlock_count} deadlocked, {error_count} other errors")

    if deadlock_count > 0:
        print(f"\n⚠️  Found {deadlock_count} Workers rolled back due to deadlock by ClickHouse!")
        print("   All operations of rolled-back Workers did not take effect (transaction atomicity guarantee)")
    else:
        print("\n  No deadlock triggered in this run (timing factor, run multiple times to reproduce)")

    view_counts = verify_results()
    print("\nFinal view_count (ideal value should be 1, but some Workers rolled back causing possible 0):")
    for pid, vc in sorted(view_counts.items()):
        mark = "✅" if vc > 0 else "❌"
        print(f"  Post #{pid}: view_count={vc} {mark}")

    print("""
Conclusion (anti-pattern):
  - ClickHouse InnoDB automatically detects deadlocks (deadlock detection algorithm, enabled by default)
  - When deadlock occurs, ClickHouse chooses the lower-cost transaction to roll back, allowing the other to proceed
  - Rolled-back Worker receives OperationalError (errno=1213)
  - If this exception is not caught and retried, all work from the rolled-back Worker is lost

Correct solutions:
  1. Always lock resources in fixed order (e.g., primary key ascending) → see exp4 Solution A
  2. Catch deadlock exception and retry → doesn't rely on order, but requires retry logic
  3. Data partitioning, each Worker processes non-overlapping datasets → see exp4 Solution B
""")


if __name__ == "__main__":
    main()
