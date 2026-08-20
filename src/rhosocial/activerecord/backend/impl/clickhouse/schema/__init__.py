# src/rhosocial/activerecord/backend/impl/clickhouse/schema/__init__.py
"""ClickHouse schema differ."""

from .differ import ClickHouseSchemaDiffer

__all__ = ["ClickHouseSchemaDiffer"]
