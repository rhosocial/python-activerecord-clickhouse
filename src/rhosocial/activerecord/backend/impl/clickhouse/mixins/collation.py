# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/collation.py
from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.collation import CollateExpression


class ClickHouseCollationMixin:
    """ClickHouse collation validation."""

    def supports_column_collation(self) -> bool:
        """ClickHouse has no per-column collations.

        ``COLLATE`` in a column definition is parsed only for MySQL
        migration compatibility and is otherwise rejected with
        ``NOT_IMPLEMENTED`` unless ``compatibility_ignore_collation_in_create_table``
        is set; ``SHOW COLUMNS`` reports the collation as always ``NULL``.
        """
        return False

    def validate_collation_name(self, expr: "CollateExpression") -> str:
        """Validate ClickHouse collation names and return their SQL representation."""
        if expr.collation_options:
            unsupported = ", ".join(sorted(expr.collation_options))
            raise UnsupportedFeatureError(self.name, f"COLLATE options: {unsupported}")
        from rhosocial.activerecord.backend.impl.clickhouse.collation import (
            validate_clickhouse_collation_name,
        )

        return validate_clickhouse_collation_name(expr.collation_name, getattr(self, "version", None))
