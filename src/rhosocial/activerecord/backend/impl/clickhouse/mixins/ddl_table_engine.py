# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_table_engine.py
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

from typing import Any, List, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.bases import BaseExpression


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
    """ClickHouse table storage clause rendering.

    Renders the clauses ClickHouse appends to ``CREATE TABLE`` after the
    column list: ``ENGINE``, ``PRIMARY KEY``, ``PARTITION BY``, ``ORDER BY``,
    ``SAMPLE BY``, ``TTL`` and ``SETTINGS``.

    Each clause is one :class:`ClickHouseTableStorageOption` node. The nodes
    are declared on ``ClickHouseCreateTableOptions``; the statement renderer
    orders them by :attr:`ClickHouseStorageOptionKind.rank` and joins them.
    """

    def format_clickhouse_engine_spec(self, expr: Any) -> Tuple[str, tuple]:
        """Render an engine name and its parameters.

        ``ENGINE = MergeTree`` has no parameters; ``ReplacingMergeTree(version)``
        renders the parameter node in the parentheses.
        """
        if not expr.parameters:
            return expr.engine, ()
        params: List[Any] = []
        rendered: List[str] = []
        for parameter in expr.parameters:
            parameter_sql, parameter_params = parameter.to_sql()
            rendered.append(parameter_sql)
            params.extend(parameter_params)
        return f"{expr.engine}({', '.join(rendered)})", tuple(params)

    def format_clickhouse_setting(self, expr: Any) -> Tuple[str, tuple]:
        """Render one ``name = value`` pair of a ``SETTINGS`` clause.

        A scalar goes through :meth:`format_literal`, so the caller's text is
        never pasted into the statement; a node renders itself.
        """
        value = expr.value
        if isinstance(value, BaseExpression):
            value_sql, params = value.to_sql()
            return f"{expr.name} = {value_sql}", params
        return f"{expr.name} = {self.format_literal(value)}", ()

    def format_clickhouse_table_storage_option(self, expr: Any) -> Tuple[str, tuple]:
        """Render one ClickHouse table storage clause.

        The clause's spelling is decided here, not by the caller: the caller
        chooses the option and supplies a typed payload, the renderer owns
        the keyword.
        """
        from ..expression.storage_option import (
            ClickHouseStorageOptionKind,
            ClickHouseTableStorageOption,
        )

        option = expr.option
        if option is ClickHouseStorageOptionKind.ENGINE:
            engine_sql, engine_params = self.format_clickhouse_engine_spec(expr.value)
            return f"ENGINE = {engine_sql}", engine_params

        if option is ClickHouseStorageOptionKind.SETTINGS:
            params: List[Any] = []
            rendered: List[str] = []
            for item in expr.value:
                item_sql, item_params = self.format_clickhouse_setting(item)
                rendered.append(item_sql)
                params.extend(item_params)
            return f"SETTINGS {', '.join(rendered)}", tuple(params)

        if option in ClickHouseTableStorageOption.EXPRESSION_MEMBERS:
            value_sql, value_params = expr.value.to_sql()
            return f"{option.keyword} {value_sql}", value_params

        # Remaining members: PRIMARY KEY / PARTITION BY / ORDER BY.
        params = []
        rendered = []
        for item in expr.value:
            item_sql, item_params = item.to_sql()
            rendered.append(item_sql)
            params.extend(item_params)
        body = rendered[0] if len(rendered) == 1 else f"({', '.join(rendered)})"
        return f"{option.keyword} {body}", tuple(params)

    def format_clickhouse_create_table_options(self, expr: Any) -> Tuple[str, tuple]:
        """Render the ClickHouse ``CREATE`` header qualifier.

        ClickHouse places ``OR REPLACE`` between ``CREATE`` and ``TABLE``, the
        position the generic renderer reserves for this entry. ``ON CLUSTER``
        is **not** a header qualifier -- it follows the table name -- so the
        statement renderer reads it off the node and places it there.
        """
        parts: List[str] = []
        if expr.or_replace:
            if not self.supports_create_or_replace_table():
                raise UnsupportedFeatureError(self.name, "CREATE OR REPLACE TABLE")
            parts.append("OR REPLACE")
        return " ".join(parts), ()


class ClickHouseQueryClauseMixin(ClickHouseTableEngineSupport):
    """ClickHouse query clause rendering (FINAL, ARRAY JOIN, SAMPLE).

    These helpers render ClickHouse-specific clauses that can be injected into
    SELECT queries.
    """

    def format_final_modifier(self) -> Tuple[str, tuple]:
        """Return the FINAL modifier."""
        return "FINAL", ()

    def format_array_join_clause(self, array_exprs: List[str], is_left: bool = False) -> Tuple[str, tuple]:
        """Format an ARRAY JOIN clause.

        Args:
            array_exprs: Array expressions or column names to join.
            is_left: If True, use ``LEFT ARRAY JOIN``.
        """
        if not array_exprs:
            return "", ()
        join_kw = "LEFT ARRAY JOIN" if is_left else "ARRAY JOIN"
        return f"{join_kw} {', '.join(array_exprs)}", ()
