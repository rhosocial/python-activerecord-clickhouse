# src/rhosocial/activerecord/backend/impl/clickhouse/examples/named_connections/production.py
"""Production environment connection examples.

All configuration values can be overridden via environment variables:
    CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DATABASE
"""

import os

from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig


def _env_or_default(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int_or_default(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def prod_db():
    """Production ClickHouse database connection.

    Reads connection parameters from environment variables with
    fallback to example.com documentation defaults.

    Returns:
        ClickHouseConnectionConfig: Production database configuration.
    """
    return ClickHouseConnectionConfig(
        host=_env_or_default("CLICKHOUSE_HOST", "prod-clickhouse.example.com"),
        port=_env_int_or_default("CLICKHOUSE_PORT", 3306),
        user=_env_or_default("CLICKHOUSE_USER", "app_user"),
        password=_env_or_default("CLICKHOUSE_PASSWORD", ""),
        database=_env_or_default("CLICKHOUSE_DATABASE", "production"),
        connect_timeout=30,
        ssl_enabled=True,
    )


def prod_db_ssl():
    """Production ClickHouse database with full SSL verification.

    Uses SSL with certificate verification for secure
    production connections.

    Returns:
        ClickHouseConnectionConfig: SSL-verified database configuration.
    """
    return ClickHouseConnectionConfig(
        host=_env_or_default("CLICKHOUSE_HOST", "prod-clickhouse.example.com"),
        port=_env_int_or_default("CLICKHOUSE_PORT", 3306),
        user=_env_or_default("CLICKHOUSE_USER", "app_user"),
        password=_env_or_default("CLICKHOUSE_PASSWORD", ""),
        database=_env_or_default("CLICKHOUSE_DATABASE", "production"),
        connect_timeout=30,
        ssl_enabled=True,
        ssl_verify_server_cert=True,
    )


def prod_replica():
    """Production ClickHouse read replica connection.

    For read-heavy workloads, connect to a read replica
    to distribute load.

    Returns:
        ClickHouseConnectionConfig: Read replica database configuration.
    """
    return ClickHouseConnectionConfig(
        host=_env_or_default("CLICKHOUSE_REPLICA_HOST", "prod-clickhouse-replica.example.com"),
        port=_env_int_or_default("CLICKHOUSE_REPLICA_PORT", 3306),
        user=_env_or_default("CLICKHOUSE_REPLICA_USER", "app_user"),
        password=_env_or_default("CLICKHOUSE_REPLICA_PASSWORD", ""),
        database=_env_or_default("CLICKHOUSE_DATABASE", "production"),
        connect_timeout=30,
    )