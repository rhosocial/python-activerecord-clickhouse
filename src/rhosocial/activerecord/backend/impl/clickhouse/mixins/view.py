# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/view.py
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import View

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        CreateViewStatement,
        DropViewStatement,
    )


class ClickHouseViewMixin:
    """ClickHouse view support."""

    def supports_or_replace_view(self) -> bool:
        """Whether CREATE OR REPLACE VIEW is supported."""
        return True

    def supports_temporary_view(self) -> bool:
        """Whether CREATE TEMPORARY VIEW is supported.

        ClickHouse has a session-scoped temporary view:
        ``CREATE TEMPORARY VIEW [IF NOT EXISTS] view_name AS <select_query>``.
        The reference also states the limits the formatter enforces: ``OR
        REPLACE`` is not supported for temporary views, and a temporary view
        cannot be database-qualified. See ``format_create_view_statement``.

        https://clickhouse.com/docs/sql-reference/statements/create/view
        """
        return True


    def supports_create_view_bind_parameters(self) -> bool:
        """ClickHouse accepts bind parameters in a view body.

        Measured on 26.7.3: a view whose definition binds is accepted,
        because ClickHouse's "parameters" are interpolated client-side and
        the value is baked into the stored definition.
        """
        return True
    def supports_if_exists_view(self) -> bool:
        """True: ``DROP VIEW [IF EXISTS] [db.]name``.

        Official reference (DROP, DROP VIEW):
        https://clickhouse.com/docs/sql-reference/statements/drop
        """
        return True

    def supports_create_or_replace_view(self) -> bool:
        """ClickHouse supports CREATE OR REPLACE VIEW."""
        return True

    def supports_if_not_exists_view(self) -> bool:
        """True: ``CREATE [OR REPLACE] VIEW [IF NOT EXISTS] ...``.

        Official reference (CREATE VIEW, Normal View):
        https://clickhouse.com/docs/sql-reference/statements/create/view

        Both keywords are in the grammar, but they are not combinable: the
        same page states that ``OR REPLACE`` and ``IF NOT EXISTS`` are
        mutually exclusive, and that combining them is a syntax error. The
        renderer refuses that pair rather than emitting it.
        """
        return True

    def supports_view_check_option(self) -> bool:
        """Whether WITH CHECK OPTION is supported in views."""
        return True

    def supports_cascade_view(self) -> bool:
        """Whether CASCADE is supported in DROP VIEW."""
        return False

    def supports_restrict_view(self) -> bool:
        """Whether RESTRICT is supported in DROP VIEW (measured: Code 62)."""
        return False

    def format_create_view_statement(self, expr: "CreateViewStatement") -> Tuple[str, tuple]:
        """Format CREATE VIEW statement for ClickHouse.

        Args:
            expr: The ``CreateViewStatement`` to render.

        Raises:
            TypeError: ``CreateViewStatement.view`` is not a View. A
                materialized view passed here would render as a well-formed
                ``CREATE VIEW`` over the MV's name; an Index or a Table would do
                the same. The object carries its own ``format_method``, so the
                dialect has no way to notice on its own.
            UnsupportedFeatureError: a combination the reference forbids:
                ``replace`` with ``if_not_exists`` (the page calls the pair a
                syntax error), ``replace`` with ``temporary`` (``OR REPLACE``
                is not supported for temporary views), or ``temporary`` with
                a database qualifier (temporary objects live outside
                databases). Each has no ClickHouse spelling, so each is
                refused by name rather than rendered.
        """
        if not isinstance(expr.view, View):
            raise TypeError(
                f"CreateViewStatement.view must be a View, "
                f"got {type(expr.view).__name__}"
            )
        if expr.replace and expr.if_not_exists:
            raise UnsupportedFeatureError(
                self.name,
                "CREATE OR REPLACE VIEW ... IF NOT EXISTS",
                "ClickHouse's CREATE VIEW treats OR REPLACE and IF NOT EXISTS "
                "as mutually exclusive; combining them is a syntax error. "
                "Choose one: OR REPLACE replaces an existing view, IF NOT "
                "EXISTS keeps one that is already there.",
            )
        if expr.replace and expr.temporary:
            raise UnsupportedFeatureError(
                self.name,
                "CREATE OR REPLACE TEMPORARY VIEW",
                "ClickHouse's CREATE VIEW reference says OR REPLACE is not "
                "supported for temporary views. Drop the temporary view and "
                "create it again instead; there is no combined spelling.",
            )
        if expr.temporary and (
            expr.view.catalog_name is not None or expr.view.schema_name is not None
        ):
            raise UnsupportedFeatureError(
                self.name,
                "CREATE TEMPORARY VIEW with a database qualifier",
                "Temporary views are session-local and live outside databases: "
                "the reference forbids CREATE TEMPORARY VIEW db.view AS .... "
                "Name the view without a qualifier, or drop TEMPORARY.",
            )
        parts = ["CREATE"]

        if expr.temporary:
            parts.append("TEMPORARY")

        if expr.replace and self.supports_create_or_replace_view():
            parts.append("OR REPLACE")

        parts.append("VIEW")

        # ``IF NOT EXISTS`` follows the VIEW keyword: ClickHouse spells
        # ``CREATE [OR REPLACE] VIEW [IF NOT EXISTS] ...``. Putting it before
        # ``VIEW`` (``CREATE IF NOT EXISTS VIEW``) is not a clause the server
        # parses, so the position is part of the contract, not cosmetics.
        if expr.if_not_exists and self.supports_if_not_exists_view():
            parts.append("IF NOT EXISTS")

        parts.append(expr.view.to_sql()[0])

        if expr.column_aliases:
            cols = ", ".join(self.format_identifier(c) for c in expr.column_aliases)
            parts.append(f"({cols})")

        query_sql, query_params = expr.query.to_sql()
        if query_params and not self.supports_create_view_bind_parameters():
            self.refuse_ddl_bind_parameters("CREATE VIEW with bound parameters")
        parts.append(f"AS {query_sql}")

        if expr.options and expr.options.check_option:
            if not self.supports_view_check_option():
                raise UnsupportedFeatureError(
                    self.name, "WITH CHECK OPTION",
                    f"{self.name} does not support WITH CHECK OPTION.",
                )
            check_option = expr.options.check_option.value
            parts.append(f"WITH {check_option} CHECK OPTION")

        return " ".join(parts), query_params

    def format_drop_view_statement(self, expr: "DropViewStatement") -> Tuple[str, tuple]:
        """Format DROP VIEW statement for ClickHouse.

        Raises:
            TypeError: ``DropViewStatement.view`` is not a View. Anything else
                would have its own name rendered as the dropped view's.
            UnsupportedFeatureError: ``CASCADE`` or ``RESTRICT``, neither of
                which ClickHouse accepts (measured: Code 62).
        """
        if not isinstance(expr.view, View):
            raise TypeError(
                f"DropViewStatement.view must be a View, "
                f"got {type(expr.view).__name__}"
            )
        if expr.cascade:
            raise UnsupportedFeatureError(
                self.name, "DROP VIEW CASCADE",
                "ClickHouse does not support DROP VIEW CASCADE.",
            )
        if expr.restrict:
            raise UnsupportedFeatureError(
                self.name, "DROP VIEW RESTRICT",
                "ClickHouse does not support DROP VIEW RESTRICT.",
            )
        parts = ["DROP VIEW"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(expr.view.to_sql()[0])
        return " ".join(parts), ()
