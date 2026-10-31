# src/rhosocial/activerecord/backend/impl/clickhouse/expression/create_table_options.py
"""ClickHouse's ``CREATE TABLE`` options node.

The generic :class:`CreateTableOptions` carries only ``OR REPLACE`` and an
inline table comment. Its docstring assigns the backend-specific creation
options to each backend -- naming ``ENGINE`` among them -- so ClickHouse
declares its own subclass rather than widening the generic one.

ClickHouse's creation options do not all sit where the generic renderer puts
them, so this node holds the data and the statement renderer places it:

* ``OR REPLACE`` -- between ``CREATE`` and ``TABLE``. Rendered by
  :meth:`format_clickhouse_create_table_options`, which is where the generic
  renderer's ``table_options.to_sql()`` call lands.
* ``ON CLUSTER <name>`` -- after the table name, before the column list.
* the storage clause run -- after the column list, before the comment.

The last two are read off this node by
``ClickHouseTableMixin.format_create_table_statement`` and rendered by their
own entries, the way the core renderer already treats ``comment``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    CreateTableOptions,
)

from .storage_option import ClickHouseTableStorageOption

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.statements.ddl_table import (
        TableCommentClause,
    )


__all__ = ["ClickHouseCreateTableOptions"]


class ClickHouseCreateTableOptions(CreateTableOptions):
    """``CREATE TABLE`` options for ClickHouse.

    Extends the generic node with the two things ClickHouse adds: the
    ``ON CLUSTER`` position and the storage clause run. A storage clause may
    appear at most once -- a repeated option raises :exc:`ValueError` here, at
    construction, rather than being silently collapsed or rendered twice.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        or_replace: bool = False,
        comment: Optional["TableCommentClause"] = None,
        on_cluster: Optional[str] = None,
        table_storage_options: Sequence[ClickHouseTableStorageOption] = (),
    ):
        super().__init__(dialect, or_replace=or_replace, comment=comment)
        if on_cluster is not None and (not isinstance(on_cluster, str) or not on_cluster):
            raise TypeError(
                f"on_cluster must be a non-empty string, " f"got {type(on_cluster).__name__}"
            )
        declared = {}
        for clause in table_storage_options:
            if not isinstance(clause, ClickHouseTableStorageOption):
                raise TypeError(
                    f"table_storage_options must be "
                    f"ClickHouseTableStorageOption nodes, "
                    f"got {type(clause).__name__}"
                )
            if clause.option in declared:
                raise ValueError(
                    f"table_storage_options repeats {clause.option.keyword}; "
                    f"a storage clause may be declared once"
                )
            declared[clause.option] = clause
        self.on_cluster = on_cluster
        self.table_storage_options = tuple(table_storage_options)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_create_table_options"
