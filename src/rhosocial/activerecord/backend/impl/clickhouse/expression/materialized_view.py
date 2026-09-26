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

Reference:
https://clickhouse.com/docs/sql-reference/statements/create/view
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

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


def _validate_name(value: Optional[str], field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass
class ClickHouseRefreshSchedule:
    """The ``REFRESH`` clause of a refreshable materialized view.

    Args:
        every: ``EVERY interval`` — a sequence of ``<number> <unit>`` parts.
        after: ``AFTER interval`` — fires relative to the previous completion.
        offset: ``OFFSET interval``, only valid together with ``every``.
        randomize_for: ``RANDOMIZE FOR interval``.
        depends_on: ``DEPENDS ON`` materialized view names.
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
    depends_on: Sequence[str] = field(default_factory=tuple)
    settings: Optional[Dict[str, Any]] = None
    append: bool = False
    incremental: bool = False

    def validate(self) -> None:
        """Validate the schedule the way the server does.

        Raises:
            ValueError: on a bare ``REFRESH``, ``OFFSET`` without ``EVERY``,
                ``APPEND INCREMENTAL`` without ``APPEND``, or an empty
                ``DEPENDS ON`` list.
        """
        if not self.every and not self.after and not self.depends_on:
            raise ValueError(
                "REFRESH requires at least one of EVERY, AFTER or DEPENDS ON"
            )
        if self.offset and not self.every:
            raise ValueError("OFFSET is only valid with EVERY")
        if self.incremental and not self.append:
            raise ValueError("INCREMENTAL requires APPEND")
        if self.depends_on is not None and not isinstance(self.depends_on, (list, tuple)):
            raise TypeError("depends_on must be a sequence of view names")
        if self.depends_on:
            for name in self.depends_on:
                _validate_name(name, "depends_on entry")


class ClickHouseCreateMaterializedViewExpression(BaseExpression):
    """``CREATE MATERIALIZED VIEW`` for both ClickHouse MV flavours.

    Args:
        dialect: the ClickHouse dialect instance.
        view_name: materialized view name.
        query: defining query, an expression or raw SQL.
        database: optional database qualifier.
        on_cluster: optional ``ON CLUSTER`` name.
        to_table: target table for the ``TO`` form; its columns come from the
            query unless ``to_columns`` is given.
        engine: table engine, e.g. ``"MergeTree ORDER BY id"``. Mandatory
            without ``to_table``.
        populate: backfill existing rows (incremental MVs only).
        refresh: a :class:`ClickHouseRefreshSchedule` making it refreshable.
        empty: skip the first refresh (refreshable MVs only).
        comment: ``COMMENT`` string.
        or_replace: emit ``OR REPLACE`` (requires an Atomic/Replicated database).
        if_not_exists: emit ``IF NOT EXISTS``.

    Raises:
        ValueError: on an invalid combination — see ``validate``.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        view_name: str,
        query: Any,
        database: Optional[str] = None,
        on_cluster: Optional[str] = None,
        to_table: Optional[str] = None,
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
        _validate_name(view_name, "view_name")
        if query is None:
            raise ValueError("CREATE MATERIALIZED VIEW requires a defining query")
        if or_replace and if_not_exists:
            raise ValueError(
                "ClickHouse rejects OR REPLACE together with IF NOT EXISTS"
            )
        if database is not None:
            _validate_name(database, "database")
        if to_table is not None:
            _validate_name(to_table, "to_table")
        if to_columns is not None and (
            isinstance(to_columns, str) or not to_columns
        ):
            raise ValueError("to_columns must be a non-empty sequence of columns")

        self.view_name = view_name
        self.query = query
        self.database = database
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
    """``DROP VIEW [IF EXISTS]`` — ClickHouse removes MVs with ``DROP VIEW``."""

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        view_name: str,
        database: Optional[str] = None,
        if_exists: bool = True,
    ):
        super().__init__(dialect)
        _validate_name(view_name, "view_name")
        if database is not None:
            _validate_name(database, "database")
        self.view_name = view_name
        self.database = database
        self.if_exists = if_exists

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
        view_name: materialized view name.
        database: optional database qualifier.
        wait: also emit ``SYSTEM WAIT VIEW`` so the call blocks until done.
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        view_name: str,
        database: Optional[str] = None,
        wait: bool = False,
    ):
        super().__init__(dialect)
        _validate_name(view_name, "view_name")
        if database is not None:
            _validate_name(database, "database")
        self.view_name = view_name
        self.database = database
        self.wait = wait

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
        view_name: str,
        schedule: ClickHouseRefreshSchedule,
        database: Optional[str] = None,
        if_exists: bool = False,
    ):
        super().__init__(dialect)
        _validate_name(view_name, "view_name")
        if database is not None:
            _validate_name(database, "database")
        if not isinstance(schedule, ClickHouseRefreshSchedule):
            raise TypeError("schedule must be a ClickHouseRefreshSchedule")
        schedule.validate()
        self.view_name = view_name
        self.schedule = schedule
        self.database = database
        self.if_exists = if_exists

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_modify_materialized_view_refresh_statement"
