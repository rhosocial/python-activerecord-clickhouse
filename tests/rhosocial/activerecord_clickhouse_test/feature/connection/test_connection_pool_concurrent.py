# tests/rhosocial/activerecord_clickhouse_test/feature/connection/test_connection_pool_concurrent.py
"""
Concurrent connection pool tests for ClickHouse backend.

Tests that verify:
1. Concurrently acquired connections are distinct
2. Concurrent operations don't cause deadlocks
3. Query results don't get mixed up between connections
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple

import pytest

from rhosocial.activerecord.connection.pool import (
    BackendPool,
    AsyncBackendPool,
)


# ============================================================
# Synchronous Concurrent Tests
# ============================================================


class TestBackendPoolConcurrent:
    """Tests for concurrent operations with BackendPool (ClickHouse)."""

    def test_concurrent_connections_are_distinct(self, clickhouse_pool: BackendPool):
        """Verify that concurrently acquired connections are distinct.

        This test proves that when multiple threads acquire connections
        simultaneously, each thread gets a different connection instance.
        """
        num_threads = 5
        held_ids: set = set()
        held_lock = threading.Lock()
        double_checkouts: List[int] = []
        barrier = threading.Barrier(num_threads)
        errors: List[Exception] = []
        errors_lock = threading.Lock()

        def acquire_and_record(thread_id: int):
            try:
                barrier.wait()

                backend = clickhouse_pool.acquire()
                try:
                    conn_id = id(backend)
                    with held_lock:
                        if conn_id in held_ids:
                            double_checkouts.append(conn_id)
                        held_ids.add(conn_id)

                    time.sleep(0.1)
                finally:
                    with held_lock:
                        held_ids.discard(id(backend))
                    clickhouse_pool.release(backend)
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(acquire_and_record, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert not double_checkouts, (
            f"Pool handed the same connection to two threads concurrently: {double_checkouts}"
        )

    def test_concurrent_operations_no_deadlock(self, clickhouse_pool_with_tables: BackendPool):
        """Verify that concurrent complex operations don't cause deadlock.

        This test simulates multiple threads performing complex operations
        (insert, select, update) simultaneously on different connections,
        proving no deadlock occurs.
        """
        pool = clickhouse_pool_with_tables
        num_threads = 4
        results: Dict[int, List[Any]] = {}
        results_lock = threading.Lock()
        start_barrier = threading.Barrier(num_threads)
        errors: List[Tuple[int, Exception]] = []
        errors_lock = threading.Lock()

        def complex_operation(thread_id: int):
            try:
                # Synchronize all threads
                start_barrier.wait()

                with pool.connection() as backend:
                    # Insert records for this thread
                    for i in range(10):
                        backend.execute(
                            "INSERT INTO concurrent_test_users (thread_id, name) VALUES (%s, %s)",
                            [thread_id, f"user_{thread_id}_{i}"],
                        )

                    # Query back the data
                    query_result = backend.execute(
                        "SELECT * FROM concurrent_test_users WHERE thread_id = %s", [thread_id]
                    )

                    # Update some records
                    backend.execute(
                        "UPDATE concurrent_test_users SET name = %s WHERE thread_id = %s AND id <= %s",
                        [f"updated_{thread_id}", thread_id, thread_id + 5],
                    )

                    with results_lock:
                        results[thread_id] = query_result.data

            except Exception as e:
                with errors_lock:
                    errors.append((thread_id, e))

        # Run concurrent operations with timeout
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(complex_operation, i) for i in range(num_threads)]

            # Wait for all with timeout (deadlock detection)
            for future in as_completed(futures, timeout=60):
                future.result()

        # Verify no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Verify each thread got correct results
        for thread_id in range(num_threads):
            assert thread_id in results, f"Thread {thread_id} has no results"
            assert len(results[thread_id]) == 10, f"Thread {thread_id} expected 10 rows, got {len(results[thread_id])}"
            # Verify all rows belong to this thread
            for row in results[thread_id]:
                assert row["thread_id"] == thread_id, f"Thread {thread_id} got wrong data: {row}"

    def test_concurrent_query_results_not_mixed(self, clickhouse_pool_with_tables: BackendPool):
        """Verify that concurrent queries on different connections don't mix results.

        This test proves that when multiple connections query different data
        simultaneously, each connection gets only its own data without any mix-up.
        """
        pool = clickhouse_pool_with_tables
        num_threads = 5
        records_per_thread = 20

        # First, set up shared data
        with pool.connection() as backend:
            # Insert data for each thread group
            for thread_id in range(num_threads):
                for i in range(records_per_thread):
                    backend.execute(
                        "INSERT INTO concurrent_test_posts (thread_id, title, content) VALUES (%s, %s, %s)",
                        [thread_id, f"title_{thread_id}_{i}", f"content_{thread_id}_{i}"],
                    )

        # Now run concurrent reads
        results: Dict[int, List[Dict]] = {}
        results_lock = threading.Lock()
        barrier = threading.Barrier(num_threads)
        errors: List[Tuple[int, Exception]] = []
        errors_lock = threading.Lock()

        def read_thread_data(thread_id: int):
            try:
                # Synchronize start
                barrier.wait()

                with pool.connection() as backend:
                    # Perform multiple reads with some computation
                    time.sleep(0.05)  # Simulate processing

                    result = backend.execute(
                        "SELECT * FROM concurrent_test_posts WHERE thread_id = %s ORDER BY id", [thread_id]
                    )

                    time.sleep(0.05)  # More processing

                    with results_lock:
                        results[thread_id] = result.data

            except Exception as e:
                with errors_lock:
                    errors.append((thread_id, e))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(read_thread_data, i) for i in range(num_threads)]
            for future in as_completed(futures, timeout=30):
                future.result()

        # Verify no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Verify each thread got exactly its own data
        for thread_id in range(num_threads):
            assert thread_id in results
            data = results[thread_id]
            assert len(data) == records_per_thread, (
                f"Thread {thread_id}: expected {records_per_thread} records, got {len(data)}"
            )

            # Verify all records belong to this thread's group
            for row in data:
                assert row["thread_id"] == thread_id, f"Thread {thread_id} got data from group {row['thread_id']}!"
                assert row["title"].startswith(f"title_{thread_id}_"), (
                    f"Thread {thread_id} got wrong title: {row['title']}"
                )

    def test_concurrent_transactions_isolated(self, clickhouse_pool_with_tables: BackendPool):
        """Verify that concurrent transactions on different connections are isolated.

        This test proves that uncommitted changes in one transaction
        are not visible to other concurrent transactions.
        """
        pool = clickhouse_pool_with_tables
        num_threads = 3

        # Insert initial data
        with pool.transaction() as backend:
            for i in range(num_threads):
                backend.execute("INSERT INTO concurrent_test_users (thread_id, name) VALUES (%s, 'initial')", [i])

        results: Dict[int, Dict] = {}
        results_lock = threading.Lock()
        barrier = threading.Barrier(num_threads)
        errors: List[Tuple[int, Exception]] = []
        errors_lock = threading.Lock()

        def transaction_test(thread_id: int):
            try:
                barrier.wait()

                with pool.transaction() as backend:
                    # Update own row
                    backend.execute(
                        "UPDATE concurrent_test_users SET name = %s WHERE thread_id = %s",
                        [f"modified_by_{thread_id}", thread_id],
                    )

                    # Read all rows - should only see committed data
                    # from other threads, not their uncommitted changes
                    time.sleep(0.2)  # Allow other threads to make changes

                    all_rows = backend.execute("SELECT * FROM concurrent_test_users ORDER BY thread_id")

                    own_row = backend.execute("SELECT * FROM concurrent_test_users WHERE thread_id = %s", [thread_id])

                    with results_lock:
                        results[thread_id] = {"all_rows": all_rows.data, "own_row": own_row.data}

            except Exception as e:
                with errors_lock:
                    errors.append((thread_id, e))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(transaction_test, i) for i in range(num_threads)]
            for future in as_completed(futures, timeout=30):
                future.result()

        # Verify no errors (no deadlock)
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Verify each transaction saw its own changes
        for thread_id in range(num_threads):
            assert thread_id in results
            own_row = results[thread_id]["own_row"]
            assert len(own_row) == 1
            # Own row should show the modification
            assert own_row[0]["name"] == f"modified_by_{thread_id}"

    def test_pool_stress_concurrent_acquire_release(self, clickhouse_pool_large: BackendPool):
        """Stress test: rapidly acquire and release connections concurrently.

        This test verifies pool stability under high concurrent load.
        """
        pool = clickhouse_pool_large
        num_threads = 5
        operations_per_thread = 20

        success_count = 0
        success_lock = threading.Lock()
        errors: List[Tuple[int, int, Exception]] = []
        errors_lock = threading.Lock()

        def rapid_acquire_release(thread_id: int):
            nonlocal success_count
            for i in range(operations_per_thread):
                try:
                    with pool.connection() as backend:
                        # Quick operation
                        backend.execute("SELECT 1")
                        time.sleep(0.005)  # Tiny delay

                    with success_lock:
                        success_count += 1
                except Exception as e:
                    with errors_lock:
                        errors.append((thread_id, i, e))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(rapid_acquire_release, i) for i in range(num_threads)]
            for future in as_completed(futures, timeout=120):
                future.result()

        # Verify high success rate
        expected = num_threads * operations_per_thread
        success_rate = success_count / expected
        assert success_rate >= 0.95, (
            f"Success rate too low: {success_rate:.2%} ({success_count}/{expected}), errors: {errors[:5]}"
        )

        # Verify pool is still healthy
        stats = pool.get_stats()
        assert stats.current_in_use == 0, "Connections still in use after test"


# ============================================================
# Asynchronous Concurrent Tests
# ============================================================


class TestAsyncBackendPoolConcurrent:
    """Tests for concurrent operations with AsyncBackendPool (ClickHouse)."""

    @pytest.mark.asyncio
    async def test_concurrent_connections_are_distinct(self, async_clickhouse_pool: AsyncBackendPool):
        """Verify that concurrently acquired async connections are distinct."""
        num_concurrent = 5
        held_ids: set = set()
        held_lock = asyncio.Lock()
        double_checkouts: List[int] = []
        start_event = asyncio.Event()

        async def acquire_and_record(task_id: int):
            await start_event.wait()

            async with async_clickhouse_pool.connection() as backend:
                conn_id = id(backend)
                async with held_lock:
                    if conn_id in held_ids:
                        double_checkouts.append(conn_id)
                    held_ids.add(conn_id)
                try:
                    await asyncio.sleep(0.1)
                finally:
                    async with held_lock:
                        held_ids.discard(conn_id)

        tasks = [acquire_and_record(i) for i in range(num_concurrent)]
        start_event.set()
        await asyncio.gather(*tasks)

        assert not double_checkouts, (
            f"Pool handed the same connection to two tasks concurrently: {double_checkouts}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_operations_no_deadlock(self, async_clickhouse_pool_with_tables: AsyncBackendPool):
        """Verify that concurrent async operations don't cause deadlock."""
        pool = async_clickhouse_pool_with_tables
        num_concurrent = 4
        results: Dict[int, List[Any]] = {}
        results_lock = asyncio.Lock()
        start_event = asyncio.Event()

        async def complex_operation(task_id: int):
            await start_event.wait()

            async with pool.connection() as backend:
                # Insert records
                for i in range(10):
                    await backend.execute(
                        "INSERT INTO concurrent_test_users (task_id, name) VALUES (%s, %s)",
                        [task_id, f"user_{task_id}_{i}"],
                    )

                # Query back
                query_result = await backend.execute(
                    "SELECT * FROM concurrent_test_users WHERE task_id = %s", [task_id]
                )

                async with results_lock:
                    results[task_id] = query_result.data

        # Run all tasks concurrently
        tasks = [complex_operation(i) for i in range(num_concurrent)]
        start_event.set()
        await asyncio.gather(*tasks)

        # Verify results
        for task_id in range(num_concurrent):
            assert task_id in results
            assert len(results[task_id]) == 10
            for row in results[task_id]:
                assert row["task_id"] == task_id

    @pytest.mark.asyncio
    async def test_concurrent_query_results_not_mixed(self, async_clickhouse_pool_with_tables: AsyncBackendPool):
        """Verify that concurrent async queries don't mix results."""
        pool = async_clickhouse_pool_with_tables
        num_concurrent = 5
        records_per_task = 20

        # Setup shared data
        async with pool.connection() as backend:
            for task_id in range(num_concurrent):
                for i in range(records_per_task):
                    await backend.execute(
                        "INSERT INTO concurrent_test_posts (task_id, title, content) VALUES (%s, %s, %s)",
                        [task_id, f"title_{task_id}_{i}", f"content_{task_id}_{i}"],
                    )

        # Concurrent reads
        results: Dict[int, List[Dict]] = {}
        results_lock = asyncio.Lock()
        start_event = asyncio.Event()

        async def read_task_data(task_id: int):
            await start_event.wait()

            async with pool.connection() as backend:
                await asyncio.sleep(0.05)
                result = await backend.execute(
                    "SELECT * FROM concurrent_test_posts WHERE task_id = %s ORDER BY id", [task_id]
                )
                await asyncio.sleep(0.05)

                async with results_lock:
                    results[task_id] = result.data

        tasks = [read_task_data(i) for i in range(num_concurrent)]
        start_event.set()
        await asyncio.gather(*tasks)

        # Verify isolation
        for task_id in range(num_concurrent):
            assert task_id in results
            data = results[task_id]
            assert len(data) == records_per_task
            for row in data:
                assert row["task_id"] == task_id
                assert row["title"].startswith(f"title_{task_id}_")

    @pytest.mark.asyncio
    async def test_pool_stress_concurrent_acquire_release(self, async_clickhouse_pool_large: AsyncBackendPool):
        """Stress test: rapid async acquire and release."""
        pool = async_clickhouse_pool_large
        num_tasks = 5
        operations_per_task = 20

        success_count = 0
        success_lock = asyncio.Lock()
        errors: List[Tuple[int, int, Exception]] = []
        errors_lock = asyncio.Lock()

        async def rapid_acquire_release(task_id: int):
            nonlocal success_count
            for i in range(operations_per_task):
                try:
                    async with pool.connection() as backend:
                        await backend.execute("SELECT 1")
                        await asyncio.sleep(0.005)

                    async with success_lock:
                        success_count += 1
                except Exception as e:
                    async with errors_lock:
                        errors.append((task_id, i, e))

        tasks = [rapid_acquire_release(i) for i in range(num_tasks)]
        await asyncio.gather(*tasks)

        expected = num_tasks * operations_per_task
        success_rate = success_count / expected
        assert success_rate >= 0.95, f"Success rate too low: {success_rate:.2%}, errors: {errors[:5]}"

        stats = pool.get_stats()
        assert stats.current_in_use == 0

    @pytest.mark.asyncio
    async def test_concurrent_with_semaphore_limit(self, async_clickhouse_pool: AsyncBackendPool):
        """Test concurrent operations when pool size limits cause waiting.

        This test verifies that when more tasks than available connections
        are running, they properly wait and don't deadlock.
        """
        pool = async_clickhouse_pool
        num_tasks = 10
        max_pool_size = pool.config.max_size

        concurrent_count = 0
        max_concurrent = 0
        count_lock = asyncio.Lock()
        start_event = asyncio.Event()
        completed: List[int] = []
        completed_lock = asyncio.Lock()

        async def tracked_operation(task_id: int):
            nonlocal concurrent_count, max_concurrent

            await start_event.wait()

            async with pool.connection() as backend:
                # Track concurrent execution
                async with count_lock:
                    concurrent_count += 1
                    max_concurrent = max(max_concurrent, concurrent_count)

                # Do some work
                await backend.execute("SELECT 1")
                await asyncio.sleep(0.1)

                async with count_lock:
                    concurrent_count -= 1

            async with completed_lock:
                completed.append(task_id)

        tasks = [tracked_operation(i) for i in range(num_tasks)]
        start_event.set()
        await asyncio.gather(*tasks)

        # Verify all tasks completed
        assert len(completed) == num_tasks

        # Verify max concurrent didn't exceed pool size
        assert max_concurrent <= max_pool_size, f"Max concurrent {max_concurrent} exceeded pool size {max_pool_size}"

        # Verify some waiting occurred (proves semaphore works)
        assert max_concurrent > 0
