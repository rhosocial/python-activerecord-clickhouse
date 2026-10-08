# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/materialized_view.py
"""ClickHouse materialized view formatters.

ClickHouse's materialized view DDL diverges from the SQL-standard statement in
ways that must not be papered over — see
:mod:`..expression.materialized_view` for the two MV flavours and their grammar.
Anything the generic expressions carry that ClickHouse cannot express is
rejected with ``UnsupportedFeatureError`` instead of being silently dropped.

Every name here -- the view, the ``TO`` target, each ``DEPENDS ON`` upstream --
is rendered by the object's own ``to_sql()``, which reaches the matching
``format_<kind>_object``. There is deliberately no second ``_qualified()``
helper: clicking the shared renderer is what keeps the database a name carries
from being dropped between the statement that wrote it and the statement that
reads it back.
"""
from typing import Any, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import MaterializedView, Table

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

    def supports_with_data_clause(self) -> bool:
        """ClickHouse has no ``WITH [NO] DATA`` clause (measured: Code 62).

        The clause is shared by CTAS, CREATE MATERIALIZED VIEW and REFRESH
        MATERIALIZED VIEW; all three consumers are answered by this dialect's
        own formatters. Declared here, once, so the answer is this dialect's
        (a core default flipping must not silently change what ClickHouse
        claims): ``CREATE TABLE ... AS`` always populates, an incremental MV
        backfills with ``POPULATE`` and a refreshable MV creates empty with
        ``EMPTY``.
        """
        return False

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
            TypeError: ``expr.view`` is not a MaterializedView, or ``expr.to_table``
                is present and is not a Table. The generic
                ``CreateMaterializedViewExpression`` carries neither kind of
                check, and every object renders its own name, so without this a
                View or a Table would produce a well-formed CREATE MATERIALIZED
                VIEW naming something else.
            UnsupportedFeatureError: for clauses ClickHouse does not have.
        """
        if not isinstance(getattr(expr, "view", None), MaterializedView):
            raise TypeError(
                f"CreateMaterializedViewExpression.view must be a MaterializedView, "
                f"got {type(getattr(expr, 'view', None)).__name__}"
            )
        to_table = getattr(expr, "to_table", None)
        if to_table is not None and not isinstance(to_table, Table):
            raise TypeError(
                f"CreateMaterializedViewExpression.to_table must be a Table, "
                f"got {type(to_table).__name__}"
            )
        self._reject_unsupported_clauses(expr, "CREATE MATERIALIZED VIEW")
        # The validation also runs in the ClickHouse expression constructor, but a
        # generic CreateMaterializedViewExpression never goes through it -- and it
        # carries neither TO nor ENGINE, which ClickHouse requires.
        to_table = self._mv_target(expr)
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
        parts.append(expr.view.to_sql()[0])

        on_cluster = getattr(expr, "on_cluster", None)
        if on_cluster:
            parts.append(f"ON CLUSTER {self.format_identifier(str(on_cluster))}")

        if to_table:
            # The target table carries its own database. Reusing the view's here
            # would aim the materialized view at another database's table.
            target = to_table.to_sql()[0]
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
        """Format ``DROP VIEW [IF EXISTS]`` — ClickHouse has no ``DROP MATERIALIZED VIEW``.

        The keyword comes from :meth:`drop_object_keyword`, which reads the
        object's kind; a materialized view landing on ``VIEW`` is the engine's
        rule, not a mis-classification.

        Raises:
            TypeError: ``expr.view`` is not a MaterializedView. ``drop_object_keyword``
                would otherwise answer ``VIEW`` for a plain View and the statement
                would name something the caller did not ask to drop.
            UnsupportedFeatureError: ``CASCADE`` or ``RESTRICT``, neither of which
                ClickHouse accepts (measured: Code 62).
        """
        view = getattr(expr, "view", None)
        if not isinstance(view, MaterializedView):
            raise TypeError(
                f"DropMaterializedViewExpression.view must be a MaterializedView, "
                f"got {type(view).__name__}"
            )
        if getattr(expr, "cascade", False):
            raise UnsupportedFeatureError(self.name, "DROP MATERIALIZED VIEW CASCADE")
        if getattr(expr, "restrict", False):
            raise UnsupportedFeatureError(self.name, "DROP MATERIALIZED VIEW RESTRICT")
        parts = ["DROP", self.drop_object_keyword(view)]
        if getattr(expr, "if_exists", False):
            parts.append("IF EXISTS")
        parts.append(view.to_sql()[0])
        return " ".join(parts), ()

    def format_refresh_materialized_view_statement(
        self, expr: "ClickHouseRefreshMaterializedViewExpression"
    ) -> Tuple[str, tuple]:
        """Format ``SYSTEM REFRESH VIEW`` (optionally followed by ``SYSTEM WAIT VIEW``).

        Raises:
            TypeError: ``expr.view`` is not a MaterializedView. The generic
                ``RefreshMaterializedViewExpression`` would otherwise render any
                object's name as the view refreshed.
            UnsupportedFeatureError: ``CONCURRENTLY``, ``WITH DATA`` or
                ``WITH NO DATA``, none of which ClickHouse spells this way.
        """
        view = getattr(expr, "view", None)
        if not isinstance(view, MaterializedView):
            raise TypeError(
                f"RefreshMaterializedViewExpression.view must be a MaterializedView, "
                f"got {type(view).__name__}"
            )
        if getattr(expr, "concurrent", False):
            raise UnsupportedFeatureError(
                self.name,
                "REFRESH MATERIALIZED VIEW CONCURRENTLY",
                "ClickHouse refreshes through SYSTEM REFRESH VIEW; use wait=True to "
                "block until the refresh completes.",
            )
        if getattr(expr, "with_data", False):
            raise UnsupportedFeatureError(
                self.name,
                "REFRESH MATERIALIZED VIEW WITH DATA",
                "A ClickHouse refresh always repopulates the target.",
            )
        if getattr(expr, "no_data", False):
            raise UnsupportedFeatureError(
                self.name,
                "REFRESH MATERIALIZED VIEW WITH NO DATA",
                "A ClickHouse refresh always repopulates the target.",
            )
        target = view.to_sql()[0]
        statement = f"SYSTEM REFRESH VIEW {target}"
        if getattr(expr, "wait", False):
            statement = f"{statement}; SYSTEM WAIT VIEW {target}"
        return statement, ()

    def format_modify_materialized_view_refresh_statement(
        self, expr: "ClickHouseModifyMaterializedViewRefreshExpression"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... MODIFY REFRESH``.

        Raises:
            TypeError: ``expr.view`` is not a MaterializedView, or an entry of
                ``expr.schedule.depends_on`` is not one. ``DEPENDS ON`` renders
                each upstream through its own ``to_sql()``, so a Table there
                would name a table in a list documented as materialized views.
        """
        view = getattr(expr, "view", None)
        if not isinstance(view, MaterializedView):
            raise TypeError(
                f"ModifyMaterializedViewRefreshExpression.view must be a "
                f"MaterializedView, got {type(view).__name__}"
            )
        depends_on = getattr(getattr(expr, "schedule", None), "depends_on", ()) or ()
        for position, upstream in enumerate(depends_on):
            if not isinstance(upstream, MaterializedView):
                raise TypeError(
                    f"ClickHouseRefreshSchedule.depends_on must hold "
                    f"MaterializedView instances, got "
                    f"{type(upstream).__name__} at position {position}"
                )
        parts = ["ALTER TABLE"]
        if getattr(expr, "if_exists", False):
            parts.append("IF EXISTS")
        parts.append(view.to_sql()[0])
        clause = self._format_refresh_clause(expr.schedule)
        # ALTER TABLE ... MODIFY REFRESH requires the schedule keyword; the
        # SYSTEM form spells it the same way.
        parts.append(f"MODIFY {clause}")
        return " ".join(parts), ()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _mv_target(self, expr: Any) -> Optional[Table]:
        """Return the ``TO`` target table *expr* names, or ``None``.

        The target is a :class:`Table` with its own ``catalog_name``: which
        database a materialized view writes into is the target's business.
        """
        target = getattr(expr, "to_table", None)
        return target if isinstance(target, Table) else None

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
                upstream.to_sql()[0] for upstream in schedule.depends_on
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
        if getattr(expr, "with_data", False):
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} WITH DATA",
                "ClickHouse uses POPULATE (incremental) or EMPTY (refreshable) instead.",
            )
        if getattr(expr, "no_data", False):
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} WITH NO DATA",
                "ClickHouse uses POPULATE (incremental) or EMPTY (refreshable) instead.",
            )