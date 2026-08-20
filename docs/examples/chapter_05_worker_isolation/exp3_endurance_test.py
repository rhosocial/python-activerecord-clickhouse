#!/usr/bin/env python3
# docs/examples/worker_isolation_experiment/exp3_endurance_test.py
"""
Experiment 3: Endurance Test (Durability Verification)

This experiment runs for an extended period to verify the stability of
process-isolated connections vs shared connections.

It performs continuous CRUD operations with multiple workers to:
1. Detect memory leaks
2. Identify connection exhaustion issues
3. Verify consistent behavior over time
4. Measure performance degradation (if any)

Run this experiment for at least 10-30 minutes to observe behavior.

Note: This experiment uses the rhosocial.activerecord.worker_pool module
      from the core package for process-isolated task execution.
"""

from __future__ import annotations

import argparse
import gc
import multiprocessing
import os
import random
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
import threading

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from config import load_scenario_config, get_backend_class, SCHEMA_SQL

# Import from core package worker_pool module
from rhosocial.activerecord.worker_pool import (
    TaskDefinition,
    TaskResult,
    TaskMode,
    TaskPriority,
    register_handler,
    WorkerPool,
)


@dataclass
class WorkerStats:
    """Statistics from a single worker run."""
    worker_id: int
    round_num: int
    operations: int
    errors: int
    duration: float
    success: bool
    error_types: Dict[str, int] = field(default_factory=dict)


@dataclass
class ExperimentStats:
    """Aggregated experiment statistics."""
    total_operations: int = 0
    total_errors: int = 0
    total_duration: float = 0.0
    rounds_completed: int = 0
    connection_issues: int = 0
    error_breakdown: Dict[str, int] = field(default_factory=dict)
    ops_per_round: List[int] = field(default_factory=list)
    errors_per_round: List[int] = field(default_factory=list)


def worker_task(
    worker_id: int,
    round_num: int,
    num_operations: int,
    config_dict: Dict[str, Any],
    use_isolated: bool = True
) -> WorkerStats:
    """
    Worker task for endurance testing.

    Args:
        worker_id: Worker identifier
        round_num: Current round number
        num_operations: Number of operations to perform
        config_dict: Database configuration
        use_isolated: If True, use isolated connection (correct pattern)
                     If False, use shared connection (anti-pattern)
    """
    from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
    from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
    from models import User, Order, Post, Comment, ALL_MODELS

    start_time = time.time()
    operations = 0
    errors = 0
    error_types: Dict[str, int] = {}
    backend = None

    def record_error(error_msg: str):
        nonlocal errors
        errors += 1
        # Categorize error
        error_category = "unknown"
        lower_msg = error_msg.lower()
        if "connection" in lower_msg or "closed" in lower_msg:
            error_category = "connection"
        elif "timeout" in lower_msg:
            error_category = "timeout"
        elif "deadlock" in lower_msg or "lock" in lower_msg:
            error_category = "lock"
        elif "cursor" in lower_msg:
            error_category = "cursor"
        error_types[error_category] = error_types.get(error_category, 0) + 1

    try:
        if use_isolated:
            # Correct pattern: Create isolated connection
            config = ClickHouseConnectionConfig(**config_dict)
            backend = ClickHouseBackend(config)
            backend.connect()
            for model in ALL_MODELS:
                model.__backend__ = backend
        else:
            # Anti-pattern: Try to use shared connection
            # This will fail in ProcessPoolExecutor since each process
            # has its own memory space
            pass

        # Perform operations
        for i in range(num_operations):
            try:
                op_type = random.choices(
                    ['create', 'read', 'update', 'delete', 'transaction'],
                    weights=[0.2, 0.4, 0.2, 0.1, 0.1]
                )[0]

                if op_type == 'create':
                    username = f"endurance_w{worker_id}_r{round_num}_{i}"
                    user = User(username=username, email=f"{username}@test.com")
                    user.save()
                    operations += 1

                elif op_type == 'read':
                    users = User.query().order_by(User.c.id.desc()).limit(10).all()
                    operations += 1

                elif op_type == 'update':
                    users = User.query().limit(1).all()
                    if users:
                        users[0].balance = random.uniform(0, 1000)
                        users[0].save()
                    operations += 1

                elif op_type == 'delete':
                    # Delete random user (not seed users)
                    users = User.query().where(User.c.username.like("endurance_%")).limit(1).all()
                    if users:
                        users[0].delete()
                    operations += 1

                elif op_type == 'transaction':
                    if backend:
                        with backend.transaction():
                            user = User(
                                username=f"tx_w{worker_id}_r{round_num}_{i}",
                                email=f"tx_{i}@test.com"
                            )
                            user.save()
                            order = Order(
                                user_id=user.id,
                                order_number=f"TX-{int(time.time()*1000000)}",
                                total_amount=Decimal(str(random.uniform(10, 100)))
                            )
                            order.save()
                    operations += 1

                # Variable delay
                time.sleep(random.uniform(0.001, 0.005))

            except Exception as e:
                record_error(str(e))

    except Exception as e:
        record_error(f"Worker error: {str(e)}")

    finally:
        if use_isolated and backend:
            try:
                for model in ALL_MODELS:
                    model.__backend__ = None
                backend.disconnect()
            except:
                pass

    duration = time.time() - start_time

    return WorkerStats(
        worker_id=worker_id,
        round_num=round_num,
        operations=operations,
        errors=errors,
        duration=duration,
        success=(errors == 0),
        error_types=error_types
    )


def run_endurance_test(
    config_dict: Dict[str, Any],
    num_workers: int,
    ops_per_round: int,
    num_rounds: int,
    use_isolated: bool
) -> ExperimentStats:
    """Run the endurance test."""

    pattern_name = "ISOLATED (Correct)" if use_isolated else "SHARED (Anti-pattern)"
    print(f"\n{'='*70}")
    print(f"Endurance Test: {pattern_name}")
    print(f"{'='*70}")
    print(f"Workers: {num_workers}")
    print(f"Operations per round: {ops_per_round}")
    print(f"Rounds: {num_rounds}")
    print(f"Total expected operations: {num_workers * ops_per_round * num_rounds}")
    print(f"{'='*70}\n")

    stats = ExperimentStats()

    # Setup database
    from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
    from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
    from models import User, ALL_MODELS
    from config import setup_database

    config = ClickHouseConnectionConfig(**config_dict)
    setup_backend = ClickHouseBackend(config)
    setup_backend.connect()
    setup_database(setup_backend, drop_existing=True)

    # Seed data
    for model in ALL_MODELS:
        model.__backend__ = setup_backend
    for i in range(20):
        User(username=f"seed_{i}", email=f"seed{i}@test.com", balance=100.0).save()
    for model in ALL_MODELS:
        model.__backend__ = None
    setup_backend.disconnect()

    print("Starting endurance test...")
    start_time = time.time()

    for round_num in range(1, num_rounds + 1):
        round_start = time.time()

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(
                    worker_task,
                    i, round_num, ops_per_round, config_dict, use_isolated
                )
                for i in range(num_workers)
            ]

            round_ops = 0
            round_errors = 0

            for future in as_completed(futures):
                try:
                    result = future.result(timeout=120)
                    stats.total_operations += result.operations
                    stats.total_errors += result.errors
                    round_ops += result.operations
                    round_errors += result.errors

                    for error_type, count in result.error_types.items():
                        stats.error_breakdown[error_type] = stats.error_breakdown.get(error_type, 0) + count
                        if error_type == "connection":
                            stats.connection_issues += count

                except Exception as e:
                    stats.total_errors += 1
                    stats.error_breakdown["executor"] = stats.error_breakdown.get("executor", 0) + 1

        round_duration = time.time() - round_start
        stats.rounds_completed = round_num
        stats.ops_per_round.append(round_ops)
        stats.errors_per_round.append(round_errors)

        # Progress report
        if round_num % 5 == 0 or round_num == num_rounds:
            elapsed = time.time() - start_time
            avg_ops = stats.total_operations / round_num if round_num > 0 else 0
            print(f"  Round {round_num}/{num_rounds}: "
                  f"{round_ops} ops, {round_errors} errors, "
                  f"{round_duration:.2f}s, "
                  f"Total: {stats.total_operations} ops, {stats.total_errors} errors, "
                  f"Elapsed: {elapsed:.1f}s")

    stats.total_duration = time.time() - start_time

    # Print summary
    print(f"\n{'='*70}")
    print("Endurance Test Results:")
    print(f"{'='*70}")
    print(f"  Pattern: {pattern_name}")
    print(f"  Total duration: {stats.total_duration:.2f}s")
    print(f"  Rounds completed: {stats.rounds_completed}")
    print(f"  Total operations: {stats.total_operations}")
    print(f"  Total errors: {stats.total_errors}")
    print(f"  Connection issues: {stats.connection_issues}")
    print(f"  Operations per second: {stats.total_operations/stats.total_duration:.2f}")
    print(f"  Success rate: {(1 - stats.total_errors/(stats.total_operations+1))*100:.2f}%")

    if stats.error_breakdown:
        print(f"\n  Error breakdown:")
        for error_type, count in sorted(stats.error_breakdown.items()):
            print(f"    {error_type}: {count}")

    # Performance trend
    if len(stats.ops_per_round) > 1:
        first_half = stats.ops_per_round[:len(stats.ops_per_round)//2]
        second_half = stats.ops_per_round[len(stats.ops_per_round)//2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        trend = "stable" if abs(avg_second - avg_first) / avg_first < 0.1 else \
                "degrading" if avg_second < avg_first else "improving"
        print(f"\n  Performance trend: {trend}")
        print(f"    First half avg: {avg_first:.0f} ops/round")
        print(f"    Second half avg: {avg_second:.0f} ops/round")

    print(f"{'='*70}\n")

    # Cleanup
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

    return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Worker Isolation Endurance Test")
    parser.add_argument(
        "--pattern",
        choices=["isolated", "shared", "both"],
        default="isolated",
        help="Connection pattern to test"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker processes"
    )
    parser.add_argument(
        "--ops-per-round",
        type=int,
        default=100,
        help="Operations per worker per round"
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=10,
        help="Number of rounds to run"
    )
    args = parser.parse_args()

    print("\n" + "="*70)
    print("Worker Isolation Experiment - Endurance Test")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Pattern: {args.pattern}")
    print(f"  Workers: {args.workers}")
    print(f"  Operations per round: {args.ops_per_round}")
    print(f"  Rounds: {args.rounds}")
    print("="*70)

    # Load config
    try:
        config = load_scenario_config()
        print(f"\nUsing scenario: {os.getenv('CLICKHOUSE_SCENARIO', 'default')}")
    except Exception as e:
        print(f"Error loading config: {e}")
        return

    config_dict = {
        "host": config.host,
        "port": config.port,
        "database": config.database,
        "username": config.username,
        "password": config.password,
        "charset": config.charset,
        "autocommit": config.autocommit,
    }

    results = {}

    if args.pattern in ["isolated", "both"]:
        print("\n" + "="*70)
        print("Running ISOLATED connection test...")
        print("="*70)
        results["isolated"] = run_endurance_test(
            config_dict, args.workers, args.ops_per_round, args.rounds,
            use_isolated=True
        )

    if args.pattern in ["shared", "both"]:
        print("\n" + "="*70)
        print("Running SHARED connection test (anti-pattern)...")
        print("="*70)
        results["shared"] = run_endurance_test(
            config_dict, args.workers, args.ops_per_round, args.rounds,
            use_isolated=False
        )

    # Comparison
    if len(results) == 2:
        print("\n" + "="*70)
        print("Comparison Summary:")
        print("="*70)
        iso = results["isolated"]
        shr = results["shared"]

        print(f"\n{'Metric':<30} {'Isolated':>15} {'Shared':>15}")
        print("-" * 60)
        print(f"{'Total operations':<30} {iso.total_operations:>15} {shr.total_operations:>15}")
        print(f"{'Total errors':<30} {iso.total_errors:>15} {shr.total_errors:>15}")
        print(f"{'Connection issues':<30} {iso.connection_issues:>15} {shr.connection_issues:>15}")
        print(f"{'Success rate':<30} {(1-iso.total_errors/(iso.total_operations+1))*100:>14.2f}% {(1-shr.total_errors/(shr.total_operations+1))*100:>14.2f}%")
        print(f"{'Ops/second':<30} {iso.total_operations/iso.total_duration:>15.2f} {shr.total_operations/shr.total_duration:>15.2f}")

        print("\nConclusion:")
        if iso.total_errors < shr.total_errors:
            print("  ✅ Isolated connections are MORE STABLE than shared connections")
        elif iso.total_errors > shr.total_errors:
            print("  ⚠️  Unexpected: Shared connections performed better (investigate!)")
        else:
            print("  ⚖️  Both patterns showed similar error rates")

        print("="*70)


if __name__ == "__main__":
    main()
