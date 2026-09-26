# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/materialized_view.py
"""ClickHouse materialized view formatters.

ClickHouse's materialized view DDL diverges from the SQL-standard statement in
ways that must not be papered over — see
:mod:`..expression.materialized_view` for the two MV flavours and their grammar.
Anything the generic expressions carry that ClickHouse cannot express is
rejected with ``UnsupportedFeatureError`` instead of being silently dropped.
"""
from typing import Any, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.materialized_view import (
        ClickHouseCreateMaterializedViewExpression,
        ClickHouseModifyMaterializedViewRefreshExpression,
        ClickHouseRefreshMaterializedViewExpression,
        ClickHouseRefreshSchedule,
    )


class ClickHouseMaterializedViewMixin:
    """ClickHouse MATERIALIZED VIEW support.

    Must be listed before the core ``ViewMixin`` in ``ClickHouseDialect`` so
    these formatters take precedence.
    """

    def supports_materialized_view(self) -> bool:
        """ClickHouse supports incremental and refreshable materialized views."""
        return True

    def supports_refresh_materialized_view(self) -> bool:
        """Refreshable MVs are refreshed through ``SYSTEM REFRESH VIEW``."""
        return True

    def supports_materialized_view_refresh_schedule(self) -> bool:
        """Whether a ``REFRESH`` schedule can be declared / modified."""
        return True

    def supports_materialized_view_populate(self) -> bool:
        """``POPULATE`` backfills an incremental MV from existing rows."""
        return True

    # ------------------------------------------------------------------
    # Formatters
    # ------------------------------------------------------------------

    def format_create_materialized_view_statement(
        self, expr: "ClickHouseCreateMaterializedViewExpression"
    ) -> Tuple[str, tuple]:
        """Format ``CREATE MATERIALIZED VIEW`` for both ClickHouse MV flavours.

        Args:
            expr: ClickHouse create expression (or a generic one, whose
                unsupported clauses are rejected).

        Returns:
            Tuple of (SQL string, params tuple from the defining query).

        Raises:
            UnsupportedFeatureError: for clauses ClickHouse does not have.
        """
        self._reject_unsupported_clauses(expr, "CREATE MATERIALIZED VIEW")
        # The validation also runs in the ClickHouse expression constructor, but a
        # generic CreateMaterializedViewExpression never goes through it — and it
        # carries neither TO nor ENGINE, which ClickHouse requires.
        to_table = getattr(expr, "to_table", None)
        engine = getattr(expr, "engine", None)
        if not to_table and not engine:
            raise UnsupportedFeatureError(
                self.name,
                "CREATE MATERIALIZED VIEW",
                "ClickHouse requires a TO target table or an ENGINE; use "
                "ClickHouseCreateMaterializedViewExpression.",
            )

        parts = ["CREATE"]
        if getattr(expr, "or_replace", False):
            parts.append("OR REPLACE")
        parts.append("MATERIALIZED VIEW")
        if getattr(expr, "if_not_exists", False):
            parts.append("IF NOT EXISTS")
        parts.append(self._qualified(expr.view_name, getattr(expr, "database", None)))

        on_cluster = getattr(expr, "on_cluster", None)
        if on_cluster:
            parts.append(f"ON CLUSTER {self.format_identifier(str(on_cluster))}")

        if to_table:
            target = self._qualified(to_table, getattr(expr, "database", None))
            to_columns = getattr(expr, "to_columns", None)
            if to_columns:
                target = f"{target} ({', '.join(str(c) for c in to_columns)})"
            parts.append(f"TO {target}")

        engine = getattr(expr, "engine", None)
        if engine:
            parts.append(f"ENGINE = {engine}")

        if getattr(expr, "populate", False):
            parts.append("POPULATE")

        refresh = getattr(expr, "refresh", None)
        if refresh is not None:
            parts.append(self._format_refresh_clause(refresh))

        if getattr(expr, "empty", False):
            parts.append("EMPTY")

        query_sql, query_params = self._materialized_view_query_sql(expr)
        parts.append(f"AS {query_sql}")

        comment = getattr(expr, "comment", None)
        if comment is not None:
            parts.append(f"COMMENT '{self._escape_sql_string(str(comment))}'")

        return " ".join(parts), query_params

    def format_drop_materialized_view_statement(self, expr: Any) -> Tuple[str, tuple]:
        """Format ``DROP VIEW [IF EXISTS]`` — ClickHouse has no ``DROP MATERIALIZED VIEW``."""
        if getattr(expr, "cascade", False):
            raise UnsupportedFeatureError(self.name, "DROP MATERIALIZED VIEW CASCADE")
        parts = ["DROP", "VIEW"]
        if getattr(expr, "if_exists", False):
            parts.append("IF EXISTS")
        parts.append(self._qualified(expr.view_name, getattr(expr, "database", None)))
        return " ".join(parts), ()

    def format_refresh_materialized_view_statement(
        self, expr: "ClickHouseRefreshMaterializedViewExpression"
    ) -> Tuple[str, tuple]:
        """Format ``SYSTEM REFRESH VIEW`` (optionally followed by ``SYSTEM WAIT VIEW``)."""
        if getattr(expr, "concurrent", False):
            raise UnsupportedFeatureError(
                self.name,
                "REFRESH MATERIALIZED VIEW CONCURRENTLY",
                "ClickHouse refreshes through SYSTEM REFRESH VIEW; use wait=True to "
                "block until the refresh completes.",
            )
        if getattr(expr, "with_data", None) is not None:
            raise UnsupportedFeatureError(
                self.name,
                "REFRESH MATERIALIZED VIEW WITH [NO] DATA",
                "A ClickHouse refresh always repopulates the target.",
            )
        target = self._qualified(expr.view_name, getattr(expr, "database", None))
        statement = f"SYSTEM REFRESH VIEW {target}"
        if getattr(expr, "wait", False):
            statement = f"{statement}; SYSTEM WAIT VIEW {target}"
        return statement, ()

    def format_modify_materialized_view_refresh_statement(
        self, expr: "ClickHouseModifyMaterializedViewRefreshExpression"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... MODIFY REFRESH``."""
        parts = ["ALTER TABLE"]
        if getattr(expr, "if_exists", False):
            parts.append("IF EXISTS")
        parts.append(self._qualified(expr.view_name, getattr(expr, "database", None)))
        clause = self._format_refresh_clause(expr.schedule)
        # ALTER TABLE ... MODIFY REFRESH requires the schedule keyword; the
        # SYSTEM form spells it the same way.
        parts.append(f"MODIFY {clause}")
        return " ".join(parts), ()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_refresh_clause(self, schedule: "ClickHouseRefreshSchedule") -> str:
        """Render a ``REFRESH ...`` clause body (without the leading keyword)."""
        parts = ["REFRESH"]
        if schedule.every:
            parts.append(f"EVERY {schedule.every}")
            if schedule.offset:
                parts.append(f"OFFSET {schedule.offset}")
        elif schedule.after:
            parts.append(f"AFTER {schedule.after}")
        if schedule.randomize_for:
            parts.append(f"RANDOMIZE FOR {schedule.randomize_for}")
        if schedule.depends_on:
            deps = ", ".join(
                self.format_identifier(str(name)) for name in schedule.depends_on
            )
            parts.append(f"DEPENDS ON {deps}")
        if schedule.settings:
            rendered = ", ".join(
                f"{key} = {value}" for key, value in schedule.settings.items()
            )
            parts.append(f"SETTINGS {rendered}")
        if schedule.append:
            parts.append("APPEND INCREMENTAL" if schedule.incremental else "APPEND")
        return " ".join(parts)

    def _qualified(self, name: str, database: Optional[str]) -> str:
        """Render a possibly database-qualified ClickHouse object name."""
        if database:
            return f"{self.format_identifier(database)}.{self.format_identifier(name)}"
        return self.format_identifier(name)

    def _materialized_view_query_sql(self, expr: Any) -> Tuple[str, tuple]:
        """Return the defining query SQL, accepting an expression or raw SQL."""
        query = getattr(expr, "query", None)
        if query is None:
            raise ValueError("CREATE MATERIALIZED VIEW requires a defining query")
        if isinstance(query, str):
            return query, ()
        return query.to_sql()

    def _reject_unsupported_clauses(self, expr: Any, feature: str) -> None:
        """Reject generic-expression clauses ClickHouse cannot express."""
        if getattr(expr, "column_aliases", None):
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} COLUMN ALIASES",
                "ClickHouse materialized views take column names from the query.",
            )
        if getattr(expr, "tablespace", None):
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} TABLESPACE",
                "ClickHouse materializes into a target table or an ENGINE.",
            )
        if getattr(expr, "storage_options", None):
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} STORAGE PARAMETERS",
                "ClickHouse materializes into a target table or an ENGINE.",
            )
        with_data = getattr(expr, "with_data", True)
        if with_data is False:
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} WITH NO DATA",
                "ClickHouse uses POPULATE (incremental) or EMPTY (refreshable) instead.",
            )
