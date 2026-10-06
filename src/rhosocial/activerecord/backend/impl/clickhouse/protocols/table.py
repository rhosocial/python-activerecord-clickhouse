# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/table.py
"""ClickHouse table DDL protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Any, Protocol, runtime_checkable, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.protocols import (
    AlterTableSupport,
    CreateTableCloneSupport,
    CreateTableLikeSupport,
    CreateTableSupport,
    DropTableSupport,
    TableObjectSupport,
)


if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements.ddl_table import (
        CreateTableLikeExpression,
    )


@runtime_checkable
class ClickHouseTableSupport(
    TableObjectSupport,
    CreateTableSupport,
    CreateTableLikeSupport,
    CreateTableCloneSupport,
    DropTableSupport,
    AlterTableSupport,
    Protocol,
):
    """ClickHouse table DDL protocol.

    Narrows the core's table protocols where ClickHouse differs, and adds the
    methods that are ClickHouse's alone. The core protocol each method comes
    from is listed as a base so a mixin method is never undeclared: the
    naming protocol declares only ``format_table_object``, and naming a table
    is independent of the statements that create, drop or alter it.

    Feature Source: Native support (no extension required)

    ClickHouse table features beyond SQL standard:
    - ENGINE storage engine selection
    - CHARSET/COLLATE character set options
    - AUTO_INCREMENT column attribute
    - Inline index definitions in CREATE TABLE
    - Table-level COMMENT
    - CREATE TABLE ... AS <source> structure copy
    - Row format options

    Official Documentation:
    - CREATE TABLE: https://clickhouse.com/docs/en/sql-reference/statements/create/table

    Version Requirements:
    - Basic features: All versions
    - Various storage engines: ClickHouse 5.5+
    """

    def supports_inline_index(self) -> bool:
        """Whether an inline data-skipping INDEX may appear in CREATE TABLE."""
        ...

    def supports_storage_engine_option(self) -> bool:
        """Whether ENGINE option is supported.

        ClickHouse supports multiple storage engines (InnoDB, MyISAM, etc.).
        """
        ...

    def supports_charset_option(self) -> bool:
        """Whether CHARSET/COLLATE options are supported.

        ClickHouse supports character set and collation at table level.
        """
        ...

    def format_create_table_like_statement(
        self, expr: "CreateTableLikeExpression"
    ) -> Tuple[str, tuple]:
        """Format the ClickHouse ``CREATE TABLE ... AS <source>`` structure copy.

        ClickHouse has no ``LIKE`` keyword; the capability advertised by
        :meth:`~...CreateTableLikeSupport.supports_create_table_like` is
        rendered with ``AS <source>``.
        """
        ...

    def format_column_definition(self, col_def: Any) -> Tuple[str, tuple]:
        """Format a column definition with ClickHouse-specific syntax (AUTO_INCREMENT, etc.)."""
        ...

    def supports_column_comment(self) -> bool:
        """Whether an inline column COMMENT is supported (ClickHouse: yes)."""
        ...

    def format_table_constraint(self, t_const: Any) -> Tuple[str, tuple]:
        """Format a table-level constraint."""
        ...

    def format_index_definition(self, idx_def: Any) -> Tuple[str, tuple]:
        """Format an inline data-skipping INDEX definition within CREATE TABLE."""
        ...

    def format_storage_options(self, expr: Any) -> Tuple[str, tuple]:
        """Format ClickHouse table storage options (ENGINE, CHARSET, etc.)."""
        ...

    def supports_ilike(self) -> bool:
        """Whether ILIKE is supported."""
        ...
