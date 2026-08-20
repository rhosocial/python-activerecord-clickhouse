#!/usr/bin/env python3
"""
Example: ClickHouse Connection Pool Stress Test (Asynchronous)

This example demonstrates a stress test for the async connection pool by having
multiple async tasks repeatedly acquire and release connections from the same pool.
It verifies the reliability of PooledBackend under concurrent usage.

Run with: .venv_clickhouse\Scripts\python connection_pool_stress_test_async.py
Or in ClickHouse virtual environment

Requirements:
    pip install clickhouse-connector-python
    pip install -e ..\\..\\python-activerecord\\src
    pip install -e ..\\..\\python-activerecord-testsuite\\src
    # Or use the virtual environment: .venv3.10*
"""

import asyncio
import sys
import os
import time

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("CLICKHOUSE_HOST", "")
os.environ.setdefault("CLICKHOUSE_PORT", "")
os.environ.setdefault("CLICKHOUSE_USER", "")
os.environ.setdefault("CLICKHOUSE_PASSWORD", "")
os.environ.setdefault("CLICKHOUSE_DATABASE", "")
os.environ.setdefault("CLICKHOUSE_CHARSET", "")
os.environ.setdefault("CLICKHOUSE_AUTOCOMMIT", "")

# Add the project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", 
                             "python-activerecord", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", 
                             "python-activerecord-testsuite", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", 
                             "python-activerecord-clickhouse", "src"))

from rhosocial.activerecord.connection.pool import PoolConfig, AsyncBackendPool
from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


async def worker_task(pool: AsyncBackendPool, worker_id: int, iterations: int):
    """Worker function that repeatedly acquires and releases connections."""
    success_count = 0
    error_count = 0
    
    for i in range(iterations):
        backend = None
        try:
            # Acquire connection from pool
            backend = await pool.acquire(timeout=30.0)
            
            # Output backend info for verification
            print(f"  [Worker {worker_id}] Iteration {i + 1}/{iterations}")
            print(f"    threadsafety: {backend.threadsafety}")
            print(f"    mode: {pool.connection_mode}")
            
            # Execute a simple query to verify connection works
            options = ExecutionOptions(stmt_type=StatementType.DQL)
            result = await backend.execute("SELECT 1 AS test", [], options=options)
            
            if result.data and result.data[0]["test"] == 1:
                success_count += 1
                print(f"    [Worker {worker_id}] Query OK")
            else:
                error_count += 1
                print(f"    [Worker {worker_id}] Query failed: unexpected result")
            
            # Small delay to simulate work
            await asyncio.sleep(0.01)
            
        except Exception as e:
            error_count += 1
            print(f"    [Worker {worker_id}] Error: {e}")
        finally:
            if backend is not None:
                await pool.release(backend)
    
    return worker_id, success_count, error_count


async def main():
    # Pre-set environment defaults to empty strings to prevent accidental leakage
    os.environ.setdefault("CLICKHOUSE_HOST", "")
    os.environ.setdefault("CLICKHOUSE_PORT", "")
    os.environ.setdefault("CLICKHOUSE_USER", "")
    os.environ.setdefault("CLICKHOUSE_PASSWORD", "")
    os.environ.setdefault("CLICKHOUSE_DATABASE", "")
    os.environ.setdefault("CLICKHOUSE_CHARSET", "")
    os.environ.setdefault("CLICKHOUSE_AUTOCOMMIT", "")
    
    print("=" * 70)
    print("ClickHouse Connection Pool Stress Test (Asynchronous)")
    print("=" * 70)
    
    # ClickHouse connection parameters - use environment variables
    clickhouse_host = (os.environ.get("CLICKHOUSE_HOST") or "").strip()
    clickhouse_port = int((os.environ.get("CLICKHOUSE_PORT") or "0").strip() or 0)
    clickhouse_user = (os.environ.get("CLICKHOUSE_USER") or "").strip()
    clickhouse_password = (os.environ.get("CLICKHOUSE_PASSWORD") or "").strip()
    clickhouse_database = (os.environ.get("CLICKHOUSE_DATABASE") or "").strip()
    clickhouse_charset = (os.environ.get("CLICKHOUSE_CHARSET") or "").strip()
    clickhouse_autocommit = (os.environ.get("CLICKHOUSE_AUTOCOMMIT") or "").strip()
    
    clickhouse_config = {
        "host": clickhouse_host,
        "username": clickhouse_user,
        "password": clickhouse_password,
        "database": clickhouse_database,
    }
    if clickhouse_port > 0:
        clickhouse_config["port"] = clickhouse_port
    if clickhouse_charset:
        clickhouse_config["charset"] = clickhouse_charset
    if clickhouse_autocommit:
        clickhouse_config["autocommit"] = clickhouse_autocommit.lower() == "true"
    
    print("Environment variables:")
    for key in ["CLICKHOUSE_HOST", "CLICKHOUSE_PORT", "CLICKHOUSE_USER", "CLICKHOUSE_DATABASE"]:
        print(f"  {key}={os.environ.get(key, 'NOT SET')}")
    print()
    
    try:
        # Create backend to get threadsafety info
        test_backend = AsyncClickHouseBackend(**clickhouse_config)
        await test_backend.connect()
        print(f"Backend threadsafety: {test_backend.threadsafety}")
        print(f"  0 = None (not thread-safe)")
        print(f"  1 = aioclickhouse (only supports SQL)")
        print(f" 2 = Full thread-safe")
        await test_backend.disconnect()
        
        # Create connection pool with higher load
        config = PoolConfig(
            min_size=10,
            max_size=50,
            connection_mode="auto",  # auto-detect based on threadsafety
            validate_on_borrow=True,
            validation_query="SELECT 1",
            backend_factory=lambda: AsyncClickHouseBackend(**clickhouse_config)
        )
        
        print(f"\nPool configuration:")
        print(f"  min_size: {config.min_size}")
        print(f"  max_size: {config.max_size}")
        print(f"  connection_mode: {config.connection_mode}")
        print(f"  validate_on_borrow: {config.validate_on_borrow}")
        print(f"  validation_query: {config.validation_query}")
        
        pool = await AsyncBackendPool.create(config)
        
        print(f"\nEffective connection mode: {pool.connection_mode}")
        
        print(f"\nPool initial stats: {pool.get_stats()}")
        
        # -----------------------------------------------------------
        # Stress test with multiple async tasks
        # -----------------------------------------------------------
        print("\n" + "-" * 50)
        print("Starting stress test with 20 workers, 50 iterations each")
        print("-" * 50)
        
        num_workers = 20
        iterations = 50
        
        start_time = time.time()
        
        tasks = [
            worker_task(pool, i, iterations)
            for i in range(num_workers)
        ]
        
        results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start_time
        
        # -----------------------------------------------------------
        # Results
        # -----------------------------------------------------------
        print("\n" + "-" * 50)
        print("Stress test results")
        print("-" * 50)
        
        stats = pool.get_stats()
        print(f"Total connections created: {stats.total_created}")
        print(f"Total acquired: {stats.total_acquired}")
        print(f"Total released: {stats.total_released}")
        print(f"Current available: {stats.current_available}")
        print(f"Current in use: {stats.current_in_use}")
        print(f"Elapsed time: {elapsed:.2f}s")
        
        for result in results:
            worker_id, success, errors = result
            print(f"Worker {worker_id} completed: {success} success, {errors} errors")
        
        # -----------------------------------------------------------
        # Cleanup
        # -----------------------------------------------------------
        print("\n" + "-" * 50)
        print("Cleanup")
        print("-" * 50)
        
        await pool.close()
        print(f"Pool closed: {pool.is_closed}")
        
        print("\n" + "=" * 70)
        print("Stress test completed!")
        print("=" * 70)
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure ClickHouse server is running and credentials are correct.")


if __name__ == "__main__":
    asyncio.run(main())