# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/view.py
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.objects import View

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        CreateViewExpression,
        DropViewExpression,
    )


class ClickHouseViewMixin:
    """ClickHouse view support."""

    def supports_or_replace_view(self) -> bool:
        """Whether CREATE OR REPLACE VIEW is supported."""
        return True

    def supports_temporary_view(self) -> bool:
        """Whether CREATE TEMPORARY VIEW is supported."""
        return True

    def supports_if_exists_view(self) -> bool:
        """Whether DROP VIEW IF EXISTS is supported."""
        return True

    def supports_create_or_replace_view(self) -> bool:
        """ClickHouse supports CREATE OR REPLACE VIEW."""
        return True

    def supports_if_not_exists_view(self) -> bool:
        """ClickHouse supports CREATE VIEW IF NOT EXISTS."""
        return True

    def supports_view_check_option(self) -> bool:
        """Whether WITH CHECK OPTION is supported in views."""
        return True

    def supports_cascade_view(self) -> bool:
        """Whether CASCADE is supported in DROP VIEW."""
        return False

    def format_create_view_statement(self, expr: "CreateViewExpression") -> Tuple[str, tuple]:
        """Format CREATE VIEW statement for ClickHouse.

        Raises:
            TypeError: ``CreateViewExpression.view`` is not a View. A
                materialized view passed here would render as a well-formed
                ``CREATE VIEW`` over the MV's name; an Index or a Table would do
                the same. The object carries its own ``format_method``, so the
                dialect has no way to notice on its own.
        """
        if not isinstance(expr.view, View):
            raise TypeError(
                f"CreateViewExpression.view must be a View, "
                f"got {type(expr.view).__name__}"
            )
        parts = ["CREATE"]

        if expr.temporary:
            parts.append("TEMPORARY")

        if expr.replace and self.supports_create_or_replace_view():
            parts.append("OR REPLACE")

        if expr.if_not_exists and self.supports_if_not_exists_view():
            parts.append("IF NOT EXISTS")

        parts.append("VIEW")
        parts.append(expr.view.to_sql()[0])

        if expr.column_aliases:
            cols = ", ".join(self.format_identifier(c) for c in expr.column_aliases)
            parts.append(f"({cols})")

        query_sql, query_params = expr.query.to_sql()
        parts.append(f"AS {query_sql}")

        if expr.options and expr.options.check_option:
            if not self.supports_view_check_option():
                from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
                raise UnsupportedFeatureError(
                    self.name, "WITH CHECK OPTION",
                    f"{self.name} does not support WITH CHECK OPTION.",
                )
            check_option = expr.options.check_option.value
            parts.append(f"WITH {check_option} CHECK OPTION")

        return " ".join(parts), query_params

    def format_drop_view_statement(self, expr: "DropViewExpression") -> Tuple[str, tuple]:
        """Format DROP VIEW statement for ClickHouse.

        Raises:
            TypeError: ``DropViewExpression.view`` is not a View. Anything else
                would have its own name rendered as the dropped view's.
        """
        if not isinstance(expr.view, View):
            raise TypeError(
                f"DropViewExpression.view must be a View, "
                f"got {type(expr.view).__name__}"
            )
        parts = ["DROP VIEW"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(expr.view.to_sql()[0])
        return " ".join(parts), ()
