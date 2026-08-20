# tests/rhosocial/activerecord_clickhouse_test/feature/backend/named_connection/example_connections.py
"""
Example named connections for ClickHouse testing.

This module contains sample connection definitions for testing
the named connection functionality with ClickHouse backend.
"""

import os

from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig


def clickhouse_96(database: str = "test_db"):
    """ClickHouse 9.6 development server connection."""
    return ClickHouseConnectionConfig(
        host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "3306")),
        database=database,
        username=os.environ.get("CLICKHOUSE_USER", "root"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=True,
        init_command="SET time_zone = '+00:00'",
    )


def clickhouse_96_with_pool(pool_size: int = 5):
    """ClickHouse 9.6 connection with custom pool size."""
    if isinstance(pool_size, str):
        pool_size = int(pool_size)
    return ClickHouseConnectionConfig(
        host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "3306")),
        database=os.environ.get("CLICKHOUSE_DATABASE", "test_db"),
        username=os.environ.get("CLICKHOUSE_USER", "root"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=True,
        init_command="SET time_zone = '+00:00'",
        pool_size=pool_size,
    )


def clickhouse_96_readonly():
    """ClickHouse 9.6 read-only connection (shorter timeout)."""
    return ClickHouseConnectionConfig(
        host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "3306")),
        database=os.environ.get("CLICKHOUSE_DATABASE", "test_db"),
        username=os.environ.get("CLICKHOUSE_USER", "root"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=True,
        init_command="SET time_zone = '+00:00'",
        pool_timeout=10,
    )
