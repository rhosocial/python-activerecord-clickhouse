#!/usr/bin/env python3
# docs/examples/worker_isolation_experiment/exp1_shared_connection.py
"""
Experiment 1: Shared Global Connection (Anti-pattern)

This experiment demonstrates the DANGERS of sharing a single database connection
across multiple Worker processes. This is an ANTI-PATTERN that should NEVER be
used in production.

Symptoms you may observe:
- Connection corruption
- Inconsistent query results
- Deadlocks and timeouts
- Data corruption
- Random crashes

The purpose of this experiment is to DEMONSTRATE why process isolation is necessary.
"""

from __future__ import annotations

import multiprocessing
import os
import random
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from decimal import Decimal

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from config import load_scenario_config, get_backend_class, setup_database
from models import User, Order, Post, Comment, ALL_MODELS


@dataclass
class TaskResult:
    """Result of a worker task."""
    worker_id: int
    success: bool
    operations: int
    errors: List[str]
    duration: float
    connection_issues: int


def worker_task_shared_connection(worker_id: int, num_operations: int, config_dict: Dict[str, Any]) -> TaskResult:
    """
    Worker task using SHARED global connection (ANTI-PATTERN).

    This demonstrates what happens when multiple processes try to share
    the same database connection through class-level __backend__.

    WARNING: This will cause problems!
    """
    from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
    from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

    for model in ALL_MODELS:
        model.configure(ClickHouseConnectionConfig(**config_dict), ClickHouseBackend)

    start_time = time.time()
    errors = []
    operations = 0
    connection_issues = 0

    try:
        # Each worker tries to use the globally configured backend
        # This is the PROBLEM - they're all sharing the same connection!

        for i in range(num_operations):
            try:
                # Random operation type
                op_type = random.choice(['create', 'read', 'update', 'delete', 'transaction'])

                if op_type == 'create':
                    # Create a new user
                    username = f"worker{worker_id}_user{i}_{int(time.time()*1000)}"
                    email = f"{username}@test.com"
                    user = User(username=username, email=email, balance=random.uniform(0, 1000))
                    user.save()
                    operations += 1

                elif op_type == 'read':
                    # Read users
                    users = User.query().limit(10).all()
                    operations += 1

                elif op_type == 'update':
                    # Update a random user's balance
                    users = User.query().limit(1).all()
                    if users:
                        users[0].balance += random.uniform(-10, 10)
                        users[0].save()
                    operations += 1

                elif op_type == 'delete':
                    # Delete a user (if exists)
                    users = User.query().where(User.c.username.like(f"worker{worker_id}%")).limit(1).all()
                    if users:
                        users[0].delete()
                    operations += 1

                elif op_type == 'transaction':
                    # Transaction with multiple operations
                    backend = User.backend()
                    with backend.transaction():
                        user = User(username=f"tx_worker{worker_id}_{i}", email=f"tx{i}@test.com")
                        user.save()
                        order = Order(user_id=user.id, order_number=f"ORD-{int(time.time()*1000)}", total_amount=Decimal('99.99'))
                        order.save()
                    operations += 1

                # Small delay to simulate real work
                time.sleep(random.uniform(0.001, 0.01))

            except Exception as e:
                error_msg = str(e)
                errors.append(error_msg)

                # Track connection-related issues
                if any(keyword in error_msg.lower() for keyword in
                       ['connection', 'closed', 'timeout', 'lock', 'deadlock', 'cursor']):
                    connection_issues += 1

                # Continue trying other operations
                continue

    except Exception as e:
        errors.append(f"Worker crashed: {str(e)}")

    duration = time.time() - start_time

    return TaskResult(
        worker_id=worker_id,
        success=len(errors) == 0,
        operations=operations,
        errors=errors[:10],  # Limit error list size
        duration=duration,
        connection_issues=connection_issues
    )


def run_experiment(config_dict: Dict[str, Any], num_workers: int, ops_per_worker: int) -> Dict[str, Any]:
    """
    Run the shared connection experiment.

    This demonstrates the anti-pattern of configuring ActiveRecord globally
    and letting all worker processes share the same connection.
    """
    print(f"\n{'='*70}")
    print(f"Experiment 1: Shared Global Connection (ANTI-PATTERN)")
    print(f"{'='*70}")
    print(f"Workers: {num_workers}")
    print(f"Operations per worker: {ops_per_worker}")
    print(f"{'='*70}\n")

    # Configure globally ONCE (this is the anti-pattern)
    print("Step 1: Configuring ActiveRecord globally (shared connection)...")
    from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
    from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

    config = ClickHouseConnectionConfig(**config_dict)
    for model in ALL_MODELS:
        model.configure(config, ClickHouseBackend)

    # Verify all models share the same backend
    backends = [model.__backend__ for model in ALL_MODELS]
    print(f"  All models share backend: {all(b is backends[0] for b in backends)}")
    print(f"  Backend ID: {id(backends[0])}")

    # Setup database
    print("\nStep 2: Setting up database...")
    backend = User.backend()
    setup_database(backend, drop_existing=True)

    # Seed initial data
    print("  Seeding initial data...")
    for i in range(10):
        user = User(username=f"seed_user_{i}", email=f"seed{i}@test.com", balance=100.0)
        user.save()
    print(f"  Created 10 seed users")

    # Run workers with shared connection
    print(f"\nStep 3: Running {num_workers} workers with SHARED connection...")

    start_time = time.time()
    results: List[TaskResult] = []

    # Use ProcessPoolExecutor - each process will try to use the shared connection
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(worker_task_shared_connection, i, ops_per_worker, config_dict)
            for i in range(num_workers)
        ]

        for future in as_completed(futures):
            try:
                result = future.result(timeout=60)
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

    print(f"{'='*70}\n")

    # Cleanup
    print("Cleaning up...")
    try:
        backend.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in ['comments', 'orders', 'posts', 'users']:
            backend.execute(f"DROP TABLE IF EXISTS `{table}`")
        backend.execute("SET FOREIGN_KEY_CHECKS = 1")
    except:
        pass

    backend.disconnect()

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
    print("Worker Isolation Experiment - Exp 1: Shared Connection (ANTI-PATTERN)")
    print("="*70)
    print("\n⚠️  WARNING: This experiment demonstrates an ANTI-PATTERN!")
    print("   Do NOT use this approach in production!")
    print("   You may observe: connection errors, data corruption, deadlocks")
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
