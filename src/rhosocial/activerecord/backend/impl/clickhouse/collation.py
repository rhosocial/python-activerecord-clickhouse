# src/rhosocial/activerecord/backend/impl/clickhouse/collation.py
"""ClickHouse collation support.

ClickHouse does not enforce MySQL-style collations. This module retains the
class and function signatures for backward compatibility, but validation is
a no-op (accepts any collation name as valid).
"""

from typing import Optional


class ClickHouseCollation:
    """ClickHouse collation constants (placeholder).

    ClickHouse does not use MySQL-style collations. The original MySQL
    collation enum (utf8mb4_*, utf16_*, etc.) has been removed.
    This class is kept for API compatibility.
    """

    # Single sentinel value for compatibility
    DEFAULT = "utf8"


class ClickHouseCollationValidator:
    """ClickHouse collation validator (no-op).

    ClickHouse does not enforce MySQL-style collations.
    All collation names are accepted as valid.
    """

    @staticmethod
    def is_supported(name: str) -> bool:
        return True

    @staticmethod
    def validate(name: str) -> str:
        return name


def validate_clickhouse_collation_name(name: str, version: Optional[tuple] = None) -> str:
    """Validate a collation name (no-op for ClickHouse).

    ClickHouse does not enforce MySQL-style collations.
    Any collation name is accepted and returned as-is.

    Args:
        name: Collation name to validate
        version: Optional server version tuple (ignored)

    Returns:
        The collation name unchanged.
    """
    return name