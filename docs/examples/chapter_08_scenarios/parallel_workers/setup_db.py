# setup_db.py - ClickHouse Parallel Worker Experiment Database Initialization Script
# docs/examples/chapter_12_scenarios/parallel_workers/setup_db.py
"""
Initialize test database (drop old tables → create tables → insert test data).

Usage:
    python setup_db.py               # Synchronous initialization (default)
    python setup_db.py --async       # Asynchronous initialization (same effect)
    python setup_db.py --scenario clickhouse_84   # Specify YAML scenario

Note:
  - Run this script before each experiment to reset the database
  - Drops and recreates users / posts / comments tables
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from rhosocial.activerecord.backend.impl.clickhouse import (  # noqa: E402
    AsyncClickHouseBackend,
    ClickHouseBackend,
)

from config_loader import load_config, show_active_config  # noqa: E402
from models import (  # noqa: E402
    AsyncComment,
    AsyncPost,
    AsyncUser,
    Comment,
    Post,
    SCHEMA_SQL,
    User,
)

NUM_USERS = 5
NUM_POSTS_PER_USER = 4  # Total 20 posts
NUM_COMMENTS_PER_POST = 3  # Total 60 comments


# ─────────────────────────────────────────────────────────────────────────────
# Synchronous Initialization
# ─────────────────────────────────────────────────────────────────────────────


def init_sync(scenario: str = None) -> None:
    """Initialize database synchronously and insert test data."""
    config = load_config(scenario)
    print("=== Synchronous Initialization Mode ===")
    print("Connection info:")
    show_active_config(config)
    print()

    User.configure(config, ClickHouseBackend)
    Post.__backend__ = User.backend()
    Comment.__backend__ = User.backend()

    # Create tables (execute statement by statement, ClickHouse doesn't support batch multi-statement execute)
    print("Dropping old tables and creating new ones...")
    backend = User.backend()
    for statement in SCHEMA_SQL.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            backend.execute(stmt)
    print("Tables created, inserting test data...")

    users = []
    for i in range(1, NUM_USERS + 1):
        u = User(
            username=f"user{i:02d}",
            email=f"user{i:02d}@example.com",
            is_active=True,
        )
        u.save()
        users.append(u)
        print(f"  User #{u.id}: {u.username}")

    post_count = 0
    comment_count = 0
    for u in users:
        for j in range(1, NUM_POSTS_PER_USER + 1):
            p = Post(
                user_id=u.id,
                title=f"{u.username}'s post #{j}",
                body=f"This is the body of {u.username}'s post #{j}.",
                status="published",
                view_count=0,
            )
            p.save()
            post_count += 1
            for k in range(1, NUM_COMMENTS_PER_POST + 1):
                c = Comment(
                    post_id=p.id,
                    user_id=users[(k - 1) % len(users)].id,
                    body=f"Comment #{k} on post #{p.id}",
                    is_approved=(k % 2 == 1),  # Odd comments are approved
                )
                c.save()
                comment_count += 1

    print(f"\n  Inserted {post_count} posts")
    print(f"  Inserted {comment_count} comments")

    User.backend().disconnect()
    print("\n✓ Synchronous initialization complete")
    print(f"  Users {NUM_USERS} / Posts {post_count} / Comments {comment_count}")


# ─────────────────────────────────────────────────────────────────────────────
# Asynchronous Initialization
# ─────────────────────────────────────────────────────────────────────────────


async def init_async(scenario: str = None) -> None:
    """Initialize database asynchronously and insert test data (identical method name to sync version, add await)."""
    config = load_config(scenario)
    print("=== Asynchronous Initialization Mode ===")
    print("Connection info:")
    show_active_config(config)
    print()

    await AsyncUser.configure(config, AsyncClickHouseBackend)
    AsyncPost.__backend__ = AsyncUser.backend()
    AsyncComment.__backend__ = AsyncUser.backend()

    print("Dropping old tables and creating new ones...")
    backend = AsyncUser.backend()
    for statement in SCHEMA_SQL.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            await backend.execute(stmt)
    print("Tables created, inserting test data...")

    users = []
    for i in range(1, NUM_USERS + 1):
        u = AsyncUser(
            username=f"user{i:02d}",
            email=f"user{i:02d}@example.com",
            is_active=True,
        )
        await u.save()
        users.append(u)
        print(f"  User #{u.id}: {u.username}")

    post_count = 0
    comment_count = 0
    for u in users:
        for j in range(1, NUM_POSTS_PER_USER + 1):
            p = AsyncPost(
                user_id=u.id,
                title=f"{u.username}'s post #{j}",
                body=f"This is the body of {u.username}'s post #{j}.",
                status="published",
                view_count=0,
            )
            await p.save()
            post_count += 1
            for k in range(1, NUM_COMMENTS_PER_POST + 1):
                c = AsyncComment(
                    post_id=p.id,
                    user_id=users[(k - 1) % len(users)].id,
                    body=f"Comment #{k} on post #{p.id}",
                    is_approved=(k % 2 == 1),
                )
                await c.save()
                comment_count += 1

    print(f"\n  Inserted {post_count} posts")
    print(f"  Inserted {comment_count} comments")

    await AsyncUser.backend().disconnect()
    print("\n✓ Asynchronous initialization complete")
    print(f"  Users {NUM_USERS} / Posts {post_count} / Comments {comment_count}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize parallel worker experiment database (ClickHouse)")
    parser.add_argument("--async", dest="use_async", action="store_true", help="Use asynchronous initialization mode")
    parser.add_argument("--scenario", default=None, help="Specify YAML scenario name (e.g., clickhouse_80)")
    args = parser.parse_args()

    if args.use_async:
        asyncio.run(init_async(args.scenario))
    else:
        init_sync(args.scenario)

    print("\nNext steps (run this script before each experiment to reset data):")
    print("  python setup_db.py && python exp1_basic_multiprocess.py")
    print("  python setup_db.py && python exp2_clickhouse_async_advantage.py")
    print("  python setup_db.py && python exp3_deadlock_wrong.py")
    print("  python setup_db.py && python exp4_partition_correct.py")
    print("  python setup_db.py && python exp5_multithread_warning.py")


if __name__ == "__main__":
    main()
