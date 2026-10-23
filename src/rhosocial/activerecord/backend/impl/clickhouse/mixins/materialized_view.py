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
from typing import Any, Tuple, TYPE_CHECKING, Union

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import MaterializedView, Table

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements.ddl_view import (
        CreateMaterializedViewStatement,
        DropMaterializedViewStatement,
        RefreshMaterializedViewStatement,
    )
    from ..expression.materialized_view import (
        ClickHouseCreateMaterializedViewStatement,
        ClickHouseDropMaterializedViewStatement,
        ClickHouseModifyMaterializedViewRefreshStatement,
        ClickHouseRefreshMaterializedViewStatement,
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


    def supports_materialized_view_bind_parameters(self) -> bool:
        """ClickHouse accepts bind parameters in a materialized view body.

        Measured on 26.7.3: a materialized view whose definition binds is
        accepted, because ClickHouse's "parameters" are interpolated
        client-side and the value is baked into the stored definition.
        """
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
        self,
        expr: Union[
            "ClickHouseCreateMaterializedViewStatement", "CreateMaterializedViewStatement"
        ],
    ) -> Tuple[str, tuple]:
        """Format ``CREATE MATERIALIZED VIEW`` for both ClickHouse MV flavours.

        Args:
            expr: ClickHouse create expression (or a generic one, whose
                unsupported clauses are rejected and whose ClickHouse clauses
                it cannot declare).

        Returns:
            Tuple of (SQL string, params tuple from the defining query).

        Raises:
            TypeError: ``expr.view`` is not a MaterializedView, or ``expr.to_table``
                is present and is not a Table. The generic
                ``CreateMaterializedViewStatement`` carries neither kind of
                check, and every object renders its own name, so without this a
                View or a Table would produce a well-formed CREATE MATERIALIZED
                VIEW naming something else.
            UnsupportedFeatureError: for clauses ClickHouse does not have. The
                WITH DATA / WITH NO DATA duo is gated the way core gates it:
                only a requested spelling is refused (by name); with neither
                requested the statement renders the dialect's default form,
                without the clause.
        """
        if not isinstance(expr.view, MaterializedView):
            raise TypeError(
                f"CreateMaterializedViewStatement.view must be a MaterializedView, "
                f"got {type(expr.view).__name__}"
            )
        from ..expression.materialized_view import ClickHouseCreateMaterializedViewStatement

        if isinstance(expr, ClickHouseCreateMaterializedViewStatement):
            # The ClickHouse node: every clause below is a declared field on it,
            # and its constructor has already validated the shape ClickHouse
            # requires (TO or ENGINE, POPULATE without REFRESH, ...).
            to_table = expr.to_table
            engine = expr.engine
        else:
            # The generic statement: its clauses are the ones ClickHouse cannot
            # express, and each is refused by the name of its spelling -- the
            # WITH DATA / WITH NO DATA duo included, and only when a spelling
            # is requested. With neither requested there is nothing to refuse,
            # and the statement renders ClickHouse's default form.
            self._reject_unsupported_clauses(expr, "CREATE MATERIALIZED VIEW")
            # TO and ENGINE are not fields of the generic node; a caller that
            # carries them attaches them on the instance, and they are read
            # here exactly as the ClickHouse node's own fields are.
            to_table = getattr(expr, "to_table", None)
            engine = getattr(expr, "engine", None)
            if to_table is None and engine is None:
                # Nothing anchors the view: ClickHouse requires a TO target
                # table or an ENGINE, and the generic node provides neither.
                raise UnsupportedFeatureError(
                    self.name,
                    "CREATE MATERIALIZED VIEW",
                    "ClickHouse requires a TO target table or an ENGINE; use "
                    "ClickHouseCreateMaterializedViewStatement.",
                )

        if to_table is not None and not isinstance(to_table, Table):
            raise TypeError(
                f"CreateMaterializedViewStatement.to_table must be a Table, "
                f"got {type(to_table).__name__}"
            )

        # The clauses of the ClickHouse spelling are declared on this backend's
        # own node only, so a generic statement reaching the render below
        # carries none of them; ``getattr`` keeps one render path for both.
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

        if engine:
            parts.append(f"ENGINE = {engine}")

        if getattr(expr, "populate", False):
            parts.append("POPULATE")

        refresh = getattr(expr, "refresh", None)
        if refresh is not None:
            # The schedule is a node of its own; the dialect spells it through
            # its ``format_method``, the same dispatch every other clause goes
            # through.
            parts.append(refresh.to_sql()[0])

        if getattr(expr, "empty", False):
            parts.append("EMPTY")

        query_sql, query_params = self._materialized_view_query_sql(expr)
        parts.append(f"AS {query_sql}")

        comment = getattr(expr, "comment", None)
        if comment is not None:
            parts.append(f"COMMENT '{self.escape_sql_string(str(comment))}'")

        return " ".join(parts), query_params

    def format_drop_materialized_view_statement(
        self,
        expr: Union[
            "ClickHouseDropMaterializedViewStatement", "DropMaterializedViewStatement"
        ],
    ) -> Tuple[str, tuple]:
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
        view = expr.view
        if not isinstance(view, MaterializedView):
            raise TypeError(
                f"DropMaterializedViewStatement.view must be a MaterializedView, "
                f"got {type(view).__name__}"
            )
        from ..expression.materialized_view import ClickHouseDropMaterializedViewStatement

        if not isinstance(expr, ClickHouseDropMaterializedViewStatement):
            # ``CASCADE`` / ``RESTRICT`` are fields of the generic statement;
            # this backend's own node does not carry them, because the engine
            # has no such clause to spell.
            if expr.cascade:
                raise UnsupportedFeatureError(self.name, "DROP MATERIALIZED VIEW CASCADE")
            if expr.restrict:
                raise UnsupportedFeatureError(self.name, "DROP MATERIALIZED VIEW RESTRICT")
        parts = ["DROP", self.drop_object_keyword(view)]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(view.to_sql()[0])
        return " ".join(parts), ()

    def format_refresh_materialized_view_statement(
        self,
        expr: Union[
            "ClickHouseRefreshMaterializedViewStatement", "RefreshMaterializedViewStatement"
        ],
    ) -> Tuple[str, tuple]:
        """Format ``SYSTEM REFRESH VIEW`` (optionally followed by ``SYSTEM WAIT VIEW``).

        Raises:
            TypeError: ``expr.view`` is not a MaterializedView. The generic
                ``RefreshMaterializedViewStatement`` would otherwise render any
                object's name as the view refreshed.
            UnsupportedFeatureError: ``CONCURRENTLY``, ``WITH DATA`` or
                ``WITH NO DATA``, none of which ClickHouse spells this way.
        """
        view = expr.view
        if not isinstance(view, MaterializedView):
            raise TypeError(
                f"RefreshMaterializedViewStatement.view must be a MaterializedView, "
                f"got {type(view).__name__}"
            )
        from ..expression.materialized_view import ClickHouseRefreshMaterializedViewStatement

        if isinstance(expr, ClickHouseRefreshMaterializedViewStatement):
            # This backend's own node: ``SYSTEM WAIT VIEW`` is its spelling of
            # "block until the refresh completes".
            wait = expr.wait
        else:
            # The generic statement: it carries the standard clauses ClickHouse
            # cannot spell, and no ``wait`` -- which is this backend's own field.
            if expr.concurrent:
                raise UnsupportedFeatureError(
                    self.name,
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY",
                    "ClickHouse refreshes through SYSTEM REFRESH VIEW; use wait=True to "
                    "block until the refresh completes.",
                )
            if expr.with_data:
                raise UnsupportedFeatureError(
                    self.name,
                    "REFRESH MATERIALIZED VIEW WITH DATA",
                    "A ClickHouse refresh always repopulates the target.",
                )
            if expr.no_data:
                raise UnsupportedFeatureError(
                    self.name,
                    "REFRESH MATERIALIZED VIEW WITH NO DATA",
                    "A ClickHouse refresh always repopulates the target.",
                )
            wait = False
        target = view.to_sql()[0]
        statement = f"SYSTEM REFRESH VIEW {target}"
        if wait:
            statement = f"{statement}; SYSTEM WAIT VIEW {target}"
        return statement, ()

    def format_modify_materialized_view_refresh_statement(
        self, expr: "ClickHouseModifyMaterializedViewRefreshStatement"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... MODIFY REFRESH``.

        Raises:
            TypeError: ``expr.view`` is not a MaterializedView, or an entry of
                ``expr.schedule.depends_on`` is not one. ``DEPENDS ON`` renders
                each upstream through its own ``to_sql()``, so a Table there
                would name a table in a list documented as materialized views.
        """
        view = expr.view
        if not isinstance(view, MaterializedView):
            raise TypeError(
                f"ModifyMaterializedViewRefreshExpression.view must be a "
                f"MaterializedView, got {type(view).__name__}"
            )
        for position, upstream in enumerate(expr.schedule.depends_on):
            if not isinstance(upstream, MaterializedView):
                raise TypeError(
                    f"ClickHouseRefreshSchedule.depends_on must hold "
                    f"MaterializedView instances, got "
                    f"{type(upstream).__name__} at position {position}"
                )
        parts = ["ALTER TABLE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(view.to_sql()[0])
        # The schedule is a node of its own; its formatter carries the REFRESH
        # spelling, and MODIFY prefixes the keyword the statement needs.
        parts.append(f"MODIFY {expr.schedule.to_sql()[0]}")
        return " ".join(parts), ()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def format_clickhouse_refresh_schedule(
        self, schedule: "ClickHouseRefreshSchedule"
    ) -> Tuple[str, tuple]:
        """Render the ``REFRESH`` clause of a refreshable materialized view.

        The schedule is an expression node (``format_method`` names this
        method), so both ``CREATE MATERIALIZED VIEW ... REFRESH ...`` and
        ``ALTER TABLE ... MODIFY REFRESH`` reach the one spelling through the
        node's own ``to_sql()``.
        """
        return self._format_refresh_clause(schedule), ()

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
        """Return the defining query SQL, accepting an expression or raw SQL.

        ``query`` is a declared field of both node kinds this mixin renders:
        the generic statement's and this backend's own expression's.
        """
        if expr.query is None:
            raise ValueError("CREATE MATERIALIZED VIEW requires a defining query")
        if isinstance(expr.query, str):
            return expr.query, ()
        query_sql, query_params = expr.query.to_sql()
        if query_params and not self.supports_materialized_view_bind_parameters():
            self.refuse_ddl_bind_parameters("CREATE MATERIALIZED VIEW with bound parameters")
        return query_sql, query_params

    def _reject_unsupported_clauses(
        self, expr: "CreateMaterializedViewStatement", feature: str
    ) -> None:
        """Reject generic-statement clauses ClickHouse cannot express.

        Every field read here is declared on the generic
        ``CreateMaterializedViewStatement``; this backend's own node accepts
        none of them, which is why the create formatter calls this helper on
        the generic statement only.
        """
        if expr.column_aliases:
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} COLUMN ALIASES",
                "ClickHouse materialized views take column names from the query.",
            )
        if expr.tablespace:
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} TABLESPACE",
                "ClickHouse materializes into a target table or an ENGINE.",
            )
        if expr.storage_options:
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} STORAGE PARAMETERS",
                "ClickHouse materializes into a target table or an ENGINE.",
            )
        if expr.with_data:
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} WITH DATA",
                "ClickHouse uses POPULATE (incremental) or EMPTY (refreshable) instead.",
            )
        if expr.no_data:
            raise UnsupportedFeatureError(
                self.name,
                f"{feature} WITH NO DATA",
                "ClickHouse uses POPULATE (incremental) or EMPTY (refreshable) instead.",
            )