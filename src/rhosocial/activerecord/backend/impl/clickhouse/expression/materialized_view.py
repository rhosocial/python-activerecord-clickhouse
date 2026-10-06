# src/rhosocial/activerecord/backend/impl/clickhouse/expression/materialized_view.py
"""ClickHouse MATERIALIZED VIEW expressions.

ClickHouse has two kinds of materialized view, and their DDL shares almost
nothing with the SQL-standard statement:

**Incremental (classic) MV** — an insert trigger. Rows written to the source
table are transformed by the ``SELECT`` and pushed into a target table::

    CREATE MATERIALIZED VIEW [IF NOT EXISTS] [db.]name [ON CLUSTER cluster]
        [TO [db.]target [(columns)]]
        [ENGINE = engine]
        [POPULATE]
        AS SELECT ...

* Without ``TO`` an ``ENGINE`` is **mandatory**.
* ``POPULATE`` backfills existing rows; it cannot be combined with ``REFRESH``.

**Refreshable MV** — periodically re-runs the query and replaces the result::

    CREATE MATERIALIZED VIEW [IF NOT EXISTS] [db.]name [ON CLUSTER cluster]
        REFRESH [EVERY|AFTER interval [OFFSET interval]]
        [RANDOMIZE FOR interval]
        [DEPENDS ON [db.]name, ...]
        [SETTINGS name = value, ...]
        [APPEND [INCREMENTAL]]
        [TO [db.]name] [ENGINE = engine]
        [EMPTY]
        AS SELECT ...

* ``REFRESH`` must carry at least one of ``EVERY``, ``AFTER`` or ``DEPENDS ON``;
  a bare ``REFRESH`` is rejected by the server.
* ``OFFSET`` is only valid with ``EVERY``.
* ``EMPTY`` skips the first refresh (the ``POPULATE`` equivalent for
  refreshable views, and mutually exclusive with it).

Removal uses ``DROP VIEW``, not ``DROP MATERIALIZED VIEW``.

Every object these statements name is a schema object from
:mod:`rhosocial.activerecord.backend.expression.objects`, and each one carries
its own ``catalog_name`` -- the ClickHouse database it lives in. That is what
makes the ``TO <target>`` clause correct: the target table's database is the
target table's business, not the materialized view's, and an expression that
kept one ``database`` field for both would silently aim the MV at another
database's table.

Reference:
https://clickhouse.com/docs/sql-reference/statements/create/view
"""
from collections.abc import Sequence as AbcSequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.objects import MaterializedView, Table

if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import ClickHouseDialect


__all__ = [
    "ClickHouseCreateMaterializedViewExpression",
    "ClickHouseDropMaterializedViewExpression",
    "ClickHouseIntervalUnit",
    "ClickHouseModifyMaterializedViewRefreshExpression",
    "ClickHouseRefreshMaterializedViewExpression",
    "ClickHouseRefreshSchedule",
]


class ClickHouseIntervalUnit(Enum):
    """Units accepted in a ClickHouse refresh interval."""

    SECOND = "SECOND"
    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    YEAR = "YEAR"


@dataclass
class ClickHouseRefreshSchedule:
    """The ``REFRESH`` clause of a refreshable materialized view.

    Args:
        every: ``EVERY interval`` — a sequence of ``<number> <unit>`` parts.
        after: ``AFTER interval`` — fires relative to the previous completion.
        offset: ``OFFSET interval``, only valid together with ``every``.
        randomize_for: ``RANDOMIZE FOR interval``.
        depends_on: materialized views this refresh waits on, each a
            :class:`MaterializedView` carrying its own ``catalog_name``.
        settings: ``SETTINGS name = value, ...`` refresh settings.
        append: ``APPEND`` — each refresh inserts without deleting.
        incremental: ``APPEND INCREMENTAL`` — refresh only rows committed since
            the previous run.

    At least one of ``every`` / ``after`` / ``depends_on`` is required: the
    server rejects a bare ``REFRESH``.
    """

    every: Optional[str] = None
    after: Optional[str] = None
    offset: Optional[str] = None
    randomize_for: Optional[str] = None
    depends_on: Sequence[MaterializedView] = field(default_factory=tuple)
    settings: Optional[Dict[str, Any]] = None
    append: bool = False
    incremental: bool = False

    def validate(self) -> None:
        """Validate the schedule the way the server does.

        Raises:
            ValueError: on a bare ``REFRESH``, ``OFFSET`` without ``EVERY``,
                ``APPEND INCREMENTAL`` without ``APPEND``, or an empty
                ``DEPENDS ON`` list.
            TypeError: ``depends_on`` is not a sequence, or an entry is not a
                materialized view object.
        """
        if not self.every and not self.after and not self.depends_on:
            raise ValueError(
                "REFRESH requires at least one of EVERY, AFTER or DEPENDS ON"
            )
        if self.offset and not self.every:
            raise ValueError("OFFSET is only valid with EVERY")
        if self.incremental and not self.append:
            raise ValueError("INCREMENTAL requires APPEND")
        if not isinstance(self.depends_on, AbcSequence):
            raise TypeError("depends_on must be a sequence of materialized views")
        for upstream in self.depends_on:
            if not isinstance(upstream, MaterializedView):
                raise TypeError(
                    "depends_on entries must be MaterializedView objects carrying "
                    f"their own catalog_name, got {type(upstream).__name__}"
                )


class ClickHouseCreateMaterializedViewExpression(BaseExpression):
    """``CREATE MATERIALIZED VIEW`` for both ClickHouse MV flavours.

    Args:
        dialect: the ClickHouse dialect instance.
        view: the materialized view being created, carrying its own
            ``catalog_name``.
        query: defining query, an expression or raw SQL.
        on_cluster: optional ``ON CLUSTER`` name.
        to_table: target table for the ``TO`` form, a :class:`Table` carrying
            **its own** ``catalog_name``; its columns come from the query
            unless ``to_columns`` is given.
        engine: table engine, e.g. ``"MergeTree ORDER BY id"``. Mandatory
            without ``to_table``.
        populate: backfill existing rows (incremental MVs only).
        refresh: a :class:`ClickHouseRefreshSchedule` making it refreshable.
        empty: skip the first refresh (refreshable MVs only).
        comment: ``COMMENT`` string.
        or_replace: emit ``OR REPLACE`` (requires an Atomic/Replicated database).
        if_not_exists: emit ``IF NOT EXISTS``.

    Raises:
        TypeError: ``view`` is not a :class:`MaterializedView`, or ``to_table``
            is not a :class:`Table`.
        ValueError: on an invalid combination — see ``validate``.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        view: MaterializedView,
        query: Any,
        on_cluster: Optional[str] = None,
        to_table: Optional[Table] = None,
        to_columns: Optional[Sequence[str]] = None,
        engine: Optional[str] = None,
        populate: bool = False,
        refresh: Optional[ClickHouseRefreshSchedule] = None,
        empty: bool = False,
        comment: Optional[str] = None,
        or_replace: bool = False,
        if_not_exists: bool = False,
    ):
        super().__init__(dialect)
        if query is None:
            raise ValueError("CREATE MATERIALIZED VIEW requires a defining query")
        if not isinstance(view, MaterializedView):
            raise TypeError(
                "view must be a MaterializedView object carrying its own "
                f"catalog_name, got {type(view).__name__}"
            )
        if to_table is not None and not isinstance(to_table, Table):
            raise TypeError(
                "to_table must be a Table object carrying its own catalog_name, "
                f"got {type(to_table).__name__}"
            )
        if or_replace and if_not_exists:
            raise ValueError(
                "ClickHouse rejects OR REPLACE together with IF NOT EXISTS"
            )
        if to_columns is not None and (
            isinstance(to_columns, str) or not to_columns
        ):
            raise ValueError("to_columns must be a non-empty sequence of columns")

        self.view = view
        self.query = query
        self.on_cluster = on_cluster
        self.to_table = to_table
        self.to_columns = list(to_columns) if to_columns else None
        self.engine = engine
        self.populate = populate
        self.refresh = refresh
        self.empty = empty
        self.comment = comment
        self.or_replace = or_replace
        self.if_not_exists = if_not_exists
        self.validate()

    @property
    def view_name(self) -> str:
        """The materialized view's own name, unqualified."""
        return self.view.name

    @property
    def database(self) -> Optional[str]:
        """The materialized view's database, or ``None`` for the default one."""
        return self.view.catalog_name

    def validate(self) -> None:
        """Validate the MV form the way the server does.

        Raises:
            ValueError: when neither ``TO`` nor ``ENGINE`` is given, or when
                ``POPULATE``/``EMPTY`` are combined with ``REFRESH``.
        """
        if not self.to_table and not self.engine:
            raise ValueError(
                "a ClickHouse materialized view requires a TO target table or an "
                "ENGINE (the engine is mandatory when TO is omitted)"
            )
        if self.populate and self.refresh is not None:
            raise ValueError(
                "POPULATE cannot be combined with REFRESH; use EMPTY to skip the "
                "first refresh of a refreshable materialized view"
            )
        if self.empty and self.refresh is None:
            raise ValueError("EMPTY is only meaningful for a refreshable materialized view")
        if self.refresh is not None:
            self.refresh.validate()

    @property
    def is_refreshable(self) -> bool:
        """Whether this is a refreshable (rather than incremental) MV."""
        return self.refresh is not None

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_create_materialized_view_statement"


class ClickHouseDropMaterializedViewExpression(BaseExpression):
    """``DROP VIEW [IF EXISTS]`` — ClickHouse removes MVs with ``DROP VIEW``.

    The ``VIEW`` keyword is ClickHouse's, not a mis-classification: the server
    has no ``DROP MATERIALIZED VIEW``. Which keyword to emit follows from the
    object's kind, and the dialect owns that mapping.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        view: MaterializedView,
        if_exists: bool = True,
    ):
        super().__init__(dialect)
        if not isinstance(view, MaterializedView):
            raise TypeError(
                "view must be a MaterializedView object carrying its own "
                f"catalog_name, got {type(view).__name__}"
            )
        self.view = view
        self.if_exists = if_exists

    @property
    def view_name(self) -> str:
        """The materialized view's own name, unqualified."""
        return self.view.name

    @property
    def database(self) -> Optional[str]:
        """The materialized view's database, or ``None`` for the default one."""
        return self.view.catalog_name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_drop_materialized_view_statement"


class ClickHouseRefreshMaterializedViewExpression(BaseExpression):
    """``SYSTEM REFRESH VIEW`` — trigger a refreshable MV refresh now.

    ClickHouse has no ``REFRESH MATERIALIZED VIEW`` statement; an immediate
    refresh is a ``SYSTEM`` command, and ``SYSTEM WAIT VIEW`` blocks until the
    running refresh completes.

    Args:
        dialect: the ClickHouse dialect instance.
        view: the materialized view to refresh, carrying its own
            ``catalog_name``.
        wait: also emit ``SYSTEM WAIT VIEW`` so the call blocks until done.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        view: MaterializedView,
        wait: bool = False,
    ):
        super().__init__(dialect)
        if not isinstance(view, MaterializedView):
            raise TypeError(
                "view must be a MaterializedView object carrying its own "
                f"catalog_name, got {type(view).__name__}"
            )
        self.view = view
        self.wait = wait

    @property
    def view_name(self) -> str:
        """The materialized view's own name, unqualified."""
        return self.view.name

    @property
    def database(self) -> Optional[str]:
        """The materialized view's database, or ``None`` for the default one."""
        return self.view.catalog_name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_refresh_materialized_view_statement"


class ClickHouseModifyMaterializedViewRefreshExpression(BaseExpression):
    """``ALTER TABLE ... MODIFY REFRESH`` — change an existing schedule.

    The statement replaces **all** refresh parameters: whatever is omitted is
    reset to its default or removed.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        view: MaterializedView,
        schedule: ClickHouseRefreshSchedule,
        if_exists: bool = False,
    ):
        super().__init__(dialect)
        if not isinstance(view, MaterializedView):
            raise TypeError(
                "view must be a MaterializedView object carrying its own "
                f"catalog_name, got {type(view).__name__}"
            )
        if not isinstance(schedule, ClickHouseRefreshSchedule):
            raise TypeError("schedule must be a ClickHouseRefreshSchedule")
        schedule.validate()
        self.view = view
        self.schedule = schedule
        self.if_exists = if_exists

    @property
    def view_name(self) -> str:
        """The materialized view's own name, unqualified."""
        return self.view.name

    @property
    def database(self) -> Optional[str]:
        """The materialized view's database, or ``None`` for the default one."""
        return self.view.catalog_name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_modify_materialized_view_refresh_statement"