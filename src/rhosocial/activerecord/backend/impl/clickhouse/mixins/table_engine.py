# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/table_engine.py
"""ClickHouse table engine and query clause support.

These features are ClickHouse-specific and not part of the generic SQL protocol,
so they are provided as backend-local support mixins:

- ``ENGINE = MergeTree()`` table engine clause
- ``ORDER BY (...)`` sorting key clause
- ``PARTITION BY (...)`` partitioning clause
- ``TTL ...`` retention clause
- ``SAMPLE BY ...`` sampling clause
- ``SETTINGS ...`` table settings
- ``FINAL`` modifier for ReplacingMergeTree / AggregatingMergeTree queries
- ``ARRAY JOIN`` clause
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ClickHouseTableEngineSupport:
    """Protocol-level capability flags for ClickHouse table engine features."""

    def supports_table_engine(self) -> bool:
        """ClickHouse supports the ENGINE table clause."""
        return True

    def supports_order_by_key(self) -> bool:
        """ClickHouse supports the ORDER BY sorting key clause."""
        return True

    def supports_partition_by_clause(self) -> bool:
        """ClickHouse supports the PARTITION BY partitioning clause."""
        return True

    def supports_ttl_clause(self) -> bool:
        """ClickHouse supports table- and column-level TTL."""
        return True

    def supports_sample_clause(self) -> bool:
        """ClickHouse supports SAMPLE and SAMPLE BY."""
        return True

    def supports_table_settings(self) -> bool:
        """ClickHouse supports the SETTINGS table clause."""
        return True

    def supports_final_modifier(self) -> bool:
        """ClickHouse supports the FINAL query modifier."""
        return True

    def supports_array_join(self) -> bool:
        """ClickHouse supports the ARRAY JOIN clause."""
        return True


class ClickHouseTableEngineMixin(ClickHouseTableEngineSupport):
    """ClickHouse table engine / storage clause rendering.

    Renders the ClickHouse-specific table clauses appended after the column
    list in ``CREATE TABLE``: ``ENGINE``, ``ORDER BY``, ``PARTITION BY``,
    ``PRIMARY KEY``, ``SAMPLE BY``, ``TTL`` and ``SETTINGS``.

    Usage: pass these clauses through the ``CreateTableExpression``
    ``dialect_options`` or ``storage_options`` mapping.
    """

    def format_table_engine_clauses(self, storage_options: Optional[Dict[str, Any]]) -> str:
        """Format ClickHouse storage clauses from a storage-options mapping.

        Accepted keys (case-insensitive):

        - ``ENGINE`` / ``engine``            — ``ENGINE = MergeTree()``
        - ``ORDER BY`` / ``order_by``        — ``ORDER BY (col1, col2)``
        - ``PARTITION BY`` / ``partition_by``— ``PARTITION BY (expr)``
        - ``PRIMARY KEY`` / ``primary_key``  — ``PRIMARY KEY (col)``
        - ``SAMPLE BY`` / ``sample_by``      — ``SAMPLE BY (expr)``
        - ``TTL`` / ``ttl``                  — ``TTL expr``
        - ``SETTINGS`` / ``settings``        — ``SETTINGS k = v, ...``

        Values are inserted verbatim (not quoted).
        """
        if not storage_options:
            return ""
        parts: List[str] = []
        for raw_key, value in storage_options.items():
            key = str(raw_key).upper().replace("_", " ")
            if key == "ENGINE":
                parts.append(f"ENGINE = {value}")
            elif key == "ORDER BY":
                parts.append(f"ORDER BY {self.format_clause_list(value)}")
            elif key == "PARTITION BY":
                parts.append(f"PARTITION BY {self.format_clause_list(value)}")
            elif key == "PRIMARY KEY":
                parts.append(f"PRIMARY KEY {self.format_clause_list(value)}")
            elif key == "SAMPLE BY":
                parts.append(f"SAMPLE BY {self.format_clause_list(value)}")
            elif key == "TTL":
                parts.append(f"TTL {value}")
            elif key == "SETTINGS":
                parts.append(f"SETTINGS {value}")
            else:
                parts.append(f"{key} = {value}")
        return " ".join(parts)

    @staticmethod
    def format_clause_list(value: Any) -> str:
        """Format a column/expression list, accepting str, list, or tuple."""
        if isinstance(value, (list, tuple)):
            return "(" + ", ".join(str(v) for v in value) + ")"
        return str(value)


class ClickHouseQueryClauseMixin(ClickHouseTableEngineSupport):
    """ClickHouse query clause rendering (FINAL, ARRAY JOIN, SAMPLE).

    These helpers render ClickHouse-specific clauses that can be injected into
    SELECT queries.
    """

    def format_final_modifier(self) -> str:
        """Return the FINAL modifier."""
        return "FINAL"

    def format_array_join_clause(self, array_exprs: List[str], is_left: bool = False) -> str:
        """Format an ARRAY JOIN clause.

        Args:
            array_exprs: Array expressions or column names to join.
            is_left: If True, use ``LEFT ARRAY JOIN``.
        """
        if not array_exprs:
            return ""
        join_kw = "LEFT ARRAY JOIN" if is_left else "ARRAY JOIN"
        return f"{join_kw} {', '.join(array_exprs)}"
