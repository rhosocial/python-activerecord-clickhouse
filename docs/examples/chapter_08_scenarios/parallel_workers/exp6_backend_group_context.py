# exp6_backend_group_context.py - BackendGroup + backend.context() for Thread Safety
# docs/examples/chapter_08_scenarios/parallel_workers/exp6_backend_group_context.py
"""
Experiment objective: Demonstrate correct usage of BackendGroup with backend.context()
for thread-safe database operations.

Key points:
- BackendGroup manages a shared backend instance across multiple model classes
- backend.context() provides "connect on demand, disconnect after use" lifecycle
- Each thread must manage its own connection lifecycle via context manager
- This is the recommended approach for ClickHouse (threadsafety=1, not suitable for BackendPool)

ClickHouse-specific notes:
- clickhouse-connector-python has threadsafety=1 (connections cannot be shared across threads)
- BackendPool is NOT suitable for ClickHouse - use BackendGroup + backend.context() instead
- Each thread's context() call creates an independent connection that auto-disconnects on exit

Comparison with exp5:
- exp5 showed multithreading + shared __backend__ is unsafe
- exp6 shows the correct solution using BackendGroup + context manager

How to run:
python setup_db.py  # Initialize database first
python exp6_backend_group_context.py
"""

from __future__ import annotations

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from rhosocial.activerecord.connection import BackendGroup
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

from config_loader import load_config
from models import Comment, Post, User

NUM_THREADS = 4
NUM_POSTS_PER_THREAD = 5


def init_test_data() -> None:
    """Create test tables and data if not exists"""
    config = load_config()
    backend = ClickHouseBackend(connection_config=config)
    backend.connect()
    
    # Create tables
    backend.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(64) NOT NULL,
            email VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    
    backend.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            body TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'published',
            view_count INT NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    
    backend.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            post_id INT NOT NULL,
            user_id INT NOT NULL,
            body TEXT,
            is_approved BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    
    # Insert test user if not exists
    result = backend.execute("SELECT COUNT(*) as cnt FROM users WHERE username = 'bot'")
    if result.data[0]['cnt'] == 0:
        backend.execute("""
            INSERT INTO users (username, email, is_active)
            VALUES ('bot', 'bot@example.com', TRUE)
        """)
    
    # Insert test posts if not enough
    result = backend.execute("SELECT COUNT(*) as cnt FROM posts")
    if result.data[0]['cnt'] < 20:
        user_result = backend.execute("SELECT id FROM users LIMIT 1")
        user_id = user_result.data[0]['id'] if user_result.data else 1
        
        for i in range(20):
            backend.execute(f"""
                INSERT INTO posts (user_id, title, body, status)
                VALUES ({user_id}, 'Test Post {i}', 'Body of test post {i}', 'published')
            """)
    
    backend.disconnect()


def reset_exp_data() -> None:
    """Delete comments inserted by this experiment"""
    config = load_config()
    try:
        Comment.configure(config, ClickHouseBackend)
        to_delete = Comment.query().where(Comment.c.body.like("[exp6]%")).all()
        for c in to_delete:
            c.delete()
        Comment.backend().disconnect()
    except Exception:
        # Table may not exist, ignore
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1: BackendGroup + backend.context() (✅ Thread-safe)
# ─────────────────────────────────────────────────────────────────────────────

def thread_worker_safe(group: BackendGroup, thread_id: int, post_ids: list) -> dict:
    """
    Thread-safe worker using BackendGroup + backend.context().
    
    Each thread:
    1. Gets the shared backend from group (not connected yet)
    2. Enters context() - connection established on demand
    3. Performs database operations
    4. Exits context() - connection automatically closed
    
    This ensures no cross-thread connection sharing.
    """
    backend = group.get_backend()
    results = {"thread_id": thread_id, "success": 0, "errors": []}
    
    try:
        # Enter context - connection established
        with backend.context():
            # All models in the group share this backend instance
            # Operations within this block use the thread-local connection
            bot = User.query().order_by(User.c.id).one()
            if bot is None:
                results["errors"].append("No bot user found")
                return results
            
            for post_id in post_ids:
                try:
                    post = Post.find_one(post_id)
                    if post is None:
                        continue
                    
                    # Create comment
                    comment = Comment(
                        post_id=post.id,
                        user_id=bot.id,
                        body=f"[exp6] Thread {thread_id} comment on post {post_id}",
                        is_approved=True
                    )
                    comment.save()
                    results["success"] += 1
                    
                except Exception as e:
                    results["errors"].append(f"Post {post_id}: {str(e)}")
    
    except Exception as e:
        results["errors"].append(f"Context error: {str(e)}")
    
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2: Without context() - Demonstrates the problem
# ─────────────────────────────────────────────────────────────────────────────

def thread_worker_unsafe(group: BackendGroup, thread_id: int, post_ids: list) -> dict:
    """
    Unsafe worker that manually connects without using context().
    
    This demonstrates why context() is important:
    - Manual connect() without proper lifecycle management
    - Connection may be reused across threads incorrectly
    - No automatic cleanup on errors
    """
    backend = group.get_backend()
    results = {"thread_id": thread_id, "success": 0, "errors": []}
    
    try:
        # Manual connect (not recommended)
        if not backend.is_connected():
            backend.connect()
        
        bot = User.query().order_by(User.c.id).one()
        if bot is None:
            results["errors"].append("No bot user found")
            return results
        
        for post_id in post_ids:
            try:
                post = Post.find_one(post_id)
                if post is None:
                    continue
                
                comment = Comment(
                    post_id=post.id,
                    user_id=bot.id,
                    body=f"[exp6-unsafe] Thread {thread_id} comment on post {post_id}",
                    is_approved=True
                )
                comment.save()
                results["success"] += 1
                
            except Exception as e:
                results["errors"].append(f"Post {post_id}: {str(e)}")
    
    except Exception as e:
        results["errors"].append(f"Connection error: {str(e)}")
    
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("BackendGroup + backend.context() Thread Safety Demo")
    print("=" * 60)
    
    # Initialize test data
    print("\nInitializing test data...")
    init_test_data()
    
    config = load_config()
    
    # Reset data
    print("Resetting experiment data...")
    reset_exp_data()
    
    # Create BackendGroup
    group = BackendGroup(
        name="exp6_group",
        models=[User, Post, Comment],
        config=config,
        backend_class=ClickHouseBackend
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Scenario 1: BackendGroup + backend.context() (Safe)
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "=" * 60)
    print("Scenario 1: BackendGroup + backend.context() (✅ Thread-safe)")
    print("=" * 60)
    
    # Configure the group (creates backend instance, doesn't connect)
    group.configure()
    
    # Get all post IDs
    backend = group.get_backend()
    with backend.context():
        posts = Post.query().all()
        all_post_ids = [p.id for p in posts if p.id is not None][:NUM_POSTS_PER_THREAD * NUM_THREADS]
    
    # Split into chunks
    chunk_size = max(1, len(all_post_ids) // NUM_THREADS)
    chunks = [all_post_ids[i:i + chunk_size] for i in range(0, len(all_post_ids), chunk_size)]
    
    # Run threads with context()
    start_time = time.time()
    results_safe = []
    
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = []
        for i, chunk in enumerate(chunks[:NUM_THREADS]):
            future = executor.submit(thread_worker_safe, group, i, chunk)
            futures.append(future)
        
        for future in futures:
            results_safe.append(future.result())
    
    safe_time = time.time() - start_time
    
    # Report results
    print(f"\nResults (with backend.context()):")
    total_success = 0
    total_errors = 0
    for r in results_safe:
        total_success += r["success"]
        total_errors += len(r["errors"])
        if r["errors"]:
            print(f"  Thread {r['thread_id']}: {r['success']} success, {len(r['errors'])} errors")
            for err in r["errors"][:3]:  # Show first 3 errors
                print(f"    - {err}")
        else:
            print(f"  Thread {r['thread_id']}: {r['success']} success ✓")
    
    print(f"\nTotal: {total_success} comments created, {total_errors} errors")
    print(f"Time: {safe_time:.3f}s")
    
    # Cleanup
    group.disconnect()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Scenario 2: Without context() (Unsafe - for comparison)
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "=" * 60)
    print("Scenario 2: Manual connect without context() (❌ Unsafe)")
    print("=" * 60)
    
    # Re-configure the group
    group.configure()
    
    start_time = time.time()
    results_unsafe = []
    
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = []
        for i, chunk in enumerate(chunks[:NUM_THREADS]):
            future = executor.submit(thread_worker_unsafe, group, i, chunk)
            futures.append(future)
        
        for future in futures:
            results_unsafe.append(future.result())
    
    unsafe_time = time.time() - start_time
    
    # Report results
    print(f"\nResults (without backend.context()):")
    total_success = 0
    total_errors = 0
    for r in results_unsafe:
        total_success += r["success"]
        total_errors += len(r["errors"])
        if r["errors"]:
            print(f"  Thread {r['thread_id']}: {r['success']} success, {len(r['errors'])} errors")
            for err in r["errors"][:3]:
                print(f"    - {err}")
        else:
            print(f"  Thread {r['thread_id']}: {r['success']} success")
    
    print(f"\nTotal: {total_success} comments created, {total_errors} errors")
    print(f"Time: {unsafe_time:.3f}s")
    
    # Cleanup
    group.disconnect()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Scenario 1 (with backend.context()): {sum(r['success'] for r in results_safe)} success")
    print(f"Scenario 2 (without context()):      {sum(r['success'] for r in results_unsafe)} success")
    
    print("\n" + "=" * 60)
    print("Conclusion:")
    print("=" * 60)
    print("""
BackendGroup + backend.context() is the recommended pattern for ClickHouse:
- BackendGroup: Manages shared backend instance across multiple model classes
- backend.context(): Provides thread-safe connection lifecycle
  - Automatically connects on entry
  - Automatically disconnects on exit
  - Each thread has its own connection scope

Why NOT BackendPool for ClickHouse:
- clickhouse-connector-python has threadsafety=1 (connections cannot be shared)
- BackendPool requires threadsafety>=2 (PostgreSQL, etc.)
- Use BackendGroup + backend.context() instead

Key principle:
- '随用随连、用完即断' (Connect on demand, disconnect after use)
- Context manager ensures proper cleanup even on exceptions
""")


if __name__ == "__main__":
    main()
