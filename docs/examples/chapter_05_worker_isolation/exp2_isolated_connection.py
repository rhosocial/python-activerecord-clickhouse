#!/usr/bin/env python3
# docs/examples/worker_isolation_experiment/exp2_isolated_connection.py
"""
Experiment 2: Process-Isolated Connections (Correct Pattern)

This experiment demonstrates the CORRECT way to handle database connections
in a Worker pool environment. Each worker process:

1. Creates its own database connection
2. Binds models to that connection on entry
3. Releases the connection on exit

This ensures:
- No connection sharing between processes
- Thread-safe operations within each process
- Proper resource cleanup
- Predictable behavior
"""

from __future__ import annotations

import multiprocessing
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from decimal import Decimal

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from config import load_scenario_config, get_backend_class, SCHEMA_SQL


@dataclass
class TaskResult:
    """Result of a worker task."""
    worker_id: int
    success: bool
    operations: int
    errors: List[str]
    duration: float
    connection_issues: int


def _ensure_tables_exist(backend) -> None:
    """Ensure all required tables exist."""
    backend.execute("SET FOREIGN_KEY_CHECKS = 0")
    try:
        # Just create if not exists - don't drop
        for table, sql in SCHEMA_SQL.items():
            # Modify to CREATE IF NOT EXISTS
            sql_modified = sql.replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE IF NOT EXISTS")
            try:
                backend.execute(sql_modified)
            except Exception:
                pass  # Table might already exist
    finally:
        backend.execute("SET FOREIGN_KEY_CHECKS = 1")


def worker_task_isolated_connection(
    worker_id: int,
    num_operations: int,
    config_dict: Dict[str, Any]
) -> TaskResult:
    """
    Worker task with ISOLATED connection per process (CORRECT PATTERN).

    Each worker:
    1. Creates its own ClickHouse backend instance
    2. Connects to the database
    3. Binds models to its connection
    4. Performs operations
    5. Disconnects on exit (guaranteed by finally)

    This is the correct approach for process-based parallelism.
    """
    from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
    from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
    from models import User, Order, Post, Comment, ALL_MODELS

    start_time = time.time()
    errors = []
    operations = 0
    connection_issues = 0
    backend = None

    try:
        # === Phase 1: Create isolated connection ===
        config = ClickHouseConnectionConfig(**config_dict)
        backend = ClickHouseBackend(config)
        backend.connect()

        # Bind models to this process's backend
        for model in ALL_MODELS:
            model.__backend__ = backend

        # Ensure tables exist (idempotent)
        _ensure_tables_exist(backend)

        # === Phase 2: Perform operations ===
        for i in range(num_operations):
            try:
                op_type = random.choice(['create', 'read', 'update', 'delete', 'transaction', 'batch'])

                if op_type == 'create':
                    username = f"worker{worker_id}_user{i}_{int(time.time()*1000)}"
                    email = f"{username}@test.com"
                    user = User(username=username, email=email, balance=random.uniform(0, 1000))
                    user.save()
                    operations += 1

                elif op_type == 'read':
                    users = User.query().limit(10).all()
                    operations += 1

                elif op_type == 'update':
                    users = User.query().limit(1).all()
                    if users:
                        users[0].balance += random.uniform(-10, 10)
                        users[0].save()
                    operations += 1

                elif op_type == 'delete':
                    users = User.query().where(User.c.username.like(f"worker{worker_id}%")).limit(1).all()
                    if users:
                        users[0].delete()
                    operations += 1

                elif op_type == 'transaction':
                    with backend.transaction():
                        user = User(username=f"tx_worker{worker_id}_{i}", email=f"tx{i}@test.com")
                        user.save()
                        order = Order(
                            user_id=user.id,
                            order_number=f"ORD-{int(time.time()*1000)}",
                            total_amount=Decimal('99.99')
                        )
                        order.save()
                    operations += 1

                elif op_type == 'batch':
                    # Batch create users
                    batch_users = []
                    for j in range(5):
                        batch_users.append(User(
                            username=f"batch_w{worker_id}_{i}_{j}",
                            email=f"batch_{i}_{j}@test.com",
                            balance=random.uniform(0, 100)
                        ))
                    # Save each (could use bulk insert if available)
                    for u in batch_users:
                        u.save()
                    operations += 5

                time.sleep(random.uniform(0.001, 0.01))

            except Exception as e:
                error_msg = str(e)
                errors.append(error_msg)

                if any(keyword in error_msg.lower() for keyword in
                       ['connection', 'closed', 'timeout', 'lock', 'deadlock', 'cursor']):
                    connection_issues += 1

                continue

    except Exception as e:
        errors.append(f"Worker setup/teardown error: {str(e)}")

    finally:
        # === Phase 3: Cleanup (guaranteed) ===
        if backend:
            try:
                # Unbind models
                for model in ALL_MODELS:
                    model.__backend__ = None
                # Disconnect
                backend.disconnect()
            except:
                pass

    duration = time.time() - start_time

    return TaskResult(
        worker_id=worker_id,
        success=len(errors) == 0,
        operations=operations,
        errors=errors[:10],
        duration=duration,
        connection_issues=connection_issues
    )


def run_experiment(config_dict: Dict[str, Any], num_workers: int, ops_per_worker: int) -> Dict[str, Any]:
    """
    Run the isolated connection experiment.

    Each worker process creates its own connection and manages its lifecycle.
    """
    print(f"\n{'='*70}")
    print(f"Experiment 2: Process-Isolated Connections (CORRECT PATTERN)")
    print(f"{'='*70}")
    print(f"Workers: {num_workers}")
    print(f"Operations per worker: {ops_per_worker}")
    print(f"{'='*70}\n")

    # Setup initial database state (in main process)
    print("Step 1: Setting up database...")
    from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
    from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
    from models import User, ALL_MODELS
    from config import setup_database

    config = ClickHouseConnectionConfig(**config_dict)
    setup_backend = ClickHouseBackend(config)
    setup_backend.connect()
    setup_database(setup_backend, drop_existing=True)

    # Seed initial data
    print("  Seeding initial data...")
    for model in ALL_MODELS:
        model.__backend__ = setup_backend

    for i in range(10):
        user = User(username=f"seed_user_{i}", email=f"seed{i}@test.com", balance=100.0)
        user.save()

    for model in ALL_MODELS:
        model.__backend__ = None
    setup_backend.disconnect()
    print(f"  Created 10 seed users")

    # Run workers with isolated connections
    print(f"\nStep 2: Running {num_workers} workers with ISOLATED connections...")
    print(f"  Each worker creates its own database connection")

    start_time = time.time()
    results: List[TaskResult] = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(worker_task_isolated_connection, i, ops_per_worker, config_dict)
            for i in range(num_workers)
        ]

        for future in as_completed(futures):
            try:
                result = future.result(timeout=120)
                results.append(result)
                status = "✅" if result.success else "❌"
                print(f"  Worker {result.worker_id}: {status} "
                      f"{result.operations} ops in {result.duration:.2f}s "
                      f"(connection issues: {result.connection_issues})")
            except Exception as e:
                print(f"  Worker failed with exception: {e}")

    total_duration = time.time() - start_time

    # Aggregate results
    total_ops = sum(r.operations for r in results)
    total_errors = sum(len(r.errors) for r in results)
    total_conn_issues = sum(r.connection_issues for r in results)
    successful_workers = sum(1 for r in results if r.success)

    print(f"\n{'='*70}")
    print("Results Summary:")
    print(f"{'='*70}")
    print(f"  Total duration: {total_duration:.2f}s")
    print(f"  Successful workers: {successful_workers}/{num_workers}")
    print(f"  Total operations completed: {total_ops}")
    print(f"  Total errors: {total_errors}")
    print(f"  Connection-related issues: {total_conn_issues}")
    print(f"  Operations per second: {total_ops/total_duration:.2f}")

    # Show sample errors
    all_errors = [e for r in results for e in r.errors]
    if all_errors:
        print(f"\n  Sample errors (first 5):")
        for err in all_errors[:5]:
            print(f"    - {err[:100]}...")
    else:
        print(f"\n  ✅ No errors detected!")

    print(f"{'='*70}\n")

    # Cleanup
    print("Cleaning up...")
    try:
        cleanup_backend = ClickHouseBackend(config)
        cleanup_backend.connect()
        cleanup_backend.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in ['comments', 'orders', 'posts', 'users']:
            cleanup_backend.execute(f"DROP TABLE IF EXISTS `{table}`")
        cleanup_backend.execute("SET FOREIGN_KEY_CHECKS = 1")
        cleanup_backend.disconnect()
    except:
        pass

    return {
        "total_duration": total_duration,
        "successful_workers": successful_workers,
        "total_workers": num_workers,
        "total_operations": total_ops,
        "total_errors": total_errors,
        "connection_issues": total_conn_issues,
        "ops_per_second": total_ops/total_duration if total_duration > 0 else 0
    }


def main():
    """Main entry point."""
    print("\n" + "="*70)
    print("Worker Isolation Experiment - Exp 2: Isolated Connection (CORRECT)")
    print("="*70)
    print("\n✅ This experiment demonstrates the CORRECT pattern!")
    print("   Each worker process has its own isolated database connection.")
    print("   This ensures: no connection conflicts, proper cleanup, stability")
    print("="*70)

    # Load config
    try:
        config = load_scenario_config()
        print(f"\nUsing scenario: {os.getenv('CLICKHOUSE_SCENARIO', 'default')}")
    except Exception as e:
        print(f"Error loading config: {e}")
        print("Set CLICKHOUSE_SCENARIOS_CONFIG_PATH or CLICKHOUSE_SCENARIO environment variable")
        return

    # Convert config to dict for serialization
    config_dict = {
        "host": config.host,
        "port": config.port,
        "database": config.database,
        "username": config.username,
        "password": config.password,
        "charset": config.charset,
        "autocommit": config.autocommit,
    }

    # Run experiment
    run_experiment(
        config_dict=config_dict,
        num_workers=4,
        ops_per_worker=50
    )


if __name__ == "__main__":
    main()
