# src/rhosocial/activerecord/backend/impl/clickhouse/examples/named_connections/development.py
"""Development environment connection examples.

All configuration values can be overridden via environment variables:
    CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DATABASE
"""

import os

from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig


def _env_or_default(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int_or_default(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def local_dev():
    """Local development ClickHouse database connection.

    Reads connection parameters from environment variables with
    fallback to localhost defaults.

    Returns:
        ClickHouseConnectionConfig: Development database configuration.
    """
    return ClickHouseConnectionConfig(
        host=_env_or_default("CLICKHOUSE_HOST", "localhost"),
        port=_env_int_or_default("CLICKHOUSE_PORT", 3306),
        user=_env_or_default("CLICKHOUSE_USER", "root"),
        password=_env_or_default("CLICKHOUSE_PASSWORD", ""),
        database=_env_or_default("CLICKHOUSE_DATABASE", "dev"),
        connect_timeout=10,
    )


def local_dev_no_auth():
    """Local ClickHouse connection without authentication.

    Reads connection parameters from environment variables with
    fallback to localhost defaults (empty password).

    Returns:
        ClickHouseConnectionConfig: No-auth database configuration.
    """
    return ClickHouseConnectionConfig(
        host=_env_or_default("CLICKHOUSE_HOST", "localhost"),
        port=_env_int_or_default("CLICKHOUSE_PORT", 3306),
        user=_env_or_default("CLICKHOUSE_USER", "root"),
        password=_env_or_default("CLICKHOUSE_PASSWORD", ""),
        database=_env_or_default("CLICKHOUSE_DATABASE", "dev"),
        connect_timeout=10,
    )


def test_db():
    """Test database connection.

    Reads connection parameters from environment variables with
    fallback to localhost defaults.

    Returns:
        ClickHouseConnectionConfig: Test database configuration.
    """
    return ClickHouseConnectionConfig(
        host=_env_or_default("CLICKHOUSE_HOST", "localhost"),
        port=_env_int_or_default("CLICKHOUSE_PORT", 3306),
        user=_env_or_default("CLICKHOUSE_USER", "root"),
        password=_env_or_default("CLICKHOUSE_PASSWORD", ""),
        database=_env_or_default("CLICKHOUSE_DATABASE", "test"),
        connect_timeout=10,
    )