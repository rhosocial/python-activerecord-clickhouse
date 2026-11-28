# src/rhosocial/activerecord/backend/impl/clickhouse/expression_registry.py
"""ClickHouse's expression table: core's kinds merged with ClickHouse's own.

``CLICKHOUSE_EXPRESSIONS`` is the mapping this backend's expression package
declares. The published table is the merge of core's mapping and that one --
never a sibling backend's, and no dialect takes part.

Both mappings are data (``kind -> fully qualified class name``); resolution
imports a class only when an artifact names its kind.
"""

from rhosocial.activerecord.backend.expression_registry import (
    CORE_EXPRESSIONS,
    ExpressionRegistry,
    collect_expressions,
    merge_expressions,
)

#: The kinds ClickHouse's own expression package declares.
CLICKHOUSE_EXPRESSIONS = collect_expressions(
    "rhosocial.activerecord.backend.impl.clickhouse.expression"
)

#: ClickHouse's table: core's kinds plus ClickHouse's own, frozen.
CLICKHOUSE_EXPRESSION_REGISTRY = ExpressionRegistry(
    merge_expressions(CORE_EXPRESSIONS, CLICKHOUSE_EXPRESSIONS)
).freeze()

__all__ = ["CLICKHOUSE_EXPRESSIONS", "CLICKHOUSE_EXPRESSION_REGISTRY"]
