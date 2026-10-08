# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_table.py
from typing import Any, List, Tuple, TYPE_CHECKING
import re

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.types import DataType

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_table import (
        ColumnDefinition,
        CreateTableAsExpression,
        CreateTableCloneExpression,
        CreateTableExpression,
        CreateTableLikeExpression,
        StorageOptionsExpression,
        IndexDefinition,
        TableConstraint,
    )


class ClickHouseTableMixin:
    """ClickHouse table DDL implementation."""

    @staticmethod
    def _validate_data_type(data_type: str) -> bool:
        """Validate data type string, allowing single quotes for ClickHouse ENUM types."""
        return bool(re.fullmatch(r"[A-Za-z0-9\s\(\),\']+", data_type))

    def supports_create_table_like(self) -> bool:
        """ClickHouse expresses a structure copy with ``AS <source>``, not ``LIKE``.

        The capability exists; only the keyword differs, so the probe still
        answers ``True`` and the renderer in
        :meth:`format_create_table_like_statement` overrides the generic form.
        """
        return True

    def supports_create_table_clone(self) -> bool:
        """ClickHouse has ``CREATE TABLE target CLONE AS source``."""
        return True

    def supports_create_or_replace_table(self) -> bool:
        return True

    def supports_inline_index(self) -> bool:
        return True

    def supports_table_comment(self) -> bool:
        """Whether inline ``COMMENT 'text'`` on ``CREATE TABLE`` is supported.

        ClickHouse renders the table comment as an inline clause (and the
        column comment inside the column definition), so both capabilities
        advertise True and the inline path is the rendering path.
        """
        return True

    def supports_column_comment(self) -> bool:
        """Whether inline ``COMMENT 'text'`` in a column definition is
        supported. ClickHouse renders it natively."""
        return True

    def supports_storage_engine_option(self) -> bool:
        return True

    def supports_charset_option(self) -> bool:
        return True

    def format_create_table_statement(self, expr: "CreateTableExpression") -> Tuple[str, tuple]:
        """Format CREATE TABLE statement for ClickHouse.

        The target is read from ``expr.table`` as a schema object and rendered by
        ``format_table_object``. Reading a bare name instead would take the name
        only and drop whatever database the object carried, so a statement aimed
        at ``other_db.users`` would create ``users`` in the connection's own
        database.

        Raises:
            TypeError: ``CreateTableExpression.table`` is not a Table. Any other
                object kind carries its own ``format_method``, so the dialect
                would call that kind's formatter and render a well-formed
                ``CREATE TABLE`` whose name is a view, an index or a sequence.
        """
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"CreateTableExpression.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        if expr.tablespace:
            raise UnsupportedFeatureError(
                self.name, "TABLESPACE",
                "ClickHouse does not support table tablespaces.",
            )
        if expr.inherits:
            raise UnsupportedFeatureError(
                self.name, "table INHERITS",
                "ClickHouse does not support table inheritance.",
            )
        all_params: List[Any] = []

        options_part = ""
        table_options = getattr(expr, "table_options", None)
        if table_options is not None:
            options_sql, options_params = table_options.to_sql()
            if options_sql:
                options_part = options_sql
            all_params.extend(options_params)
        parts = ["CREATE"]
        if options_part:
            parts.append(options_part)
        if expr.temporary:
            parts.append("TEMPORARY")
        parts.append("TABLE")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(expr.table.to_sql()[0])

        column_parts = []
        for col_def in expr.columns:
            col_sql, col_params = self.format_column_definition(col_def)
            column_parts.append(col_sql)
            all_params.extend(col_params)

        for t_const in expr.table_constraints:
            const_sql, const_params = self.format_table_constraint(t_const)
            column_parts.append(const_sql)
            all_params.extend(const_params)

        for idx_def in expr.indexes:
            idx_sql, idx_params = self.format_index_definition(idx_def)
            if idx_sql:
                column_parts.append(idx_sql)

        parts.append(f"({', '.join(column_parts)})")

        if expr.storage_options:
            storage_sql, storage_params = self._format_table_storage_options(expr.storage_options)
            if storage_sql:
                parts.append(storage_sql)
                all_params.extend(storage_params)

        table_options = getattr(expr, "table_options", None)
        if table_options is not None and getattr(table_options, "comment", None) is not None:
            comment_sql, _ = self.format_table_comment_clause(table_options.comment)
            parts.append(comment_sql.strip())

        if expr.partition is not None:
            partition_sql, partition_params = expr.partition.to_sql()
            if partition_sql:
                parts.append(partition_sql.strip())
                all_params.extend(partition_params)

        return " ".join(parts), tuple(all_params)

    def _format_table_storage_options(self, storage_options: Any) -> Tuple[str, tuple]:
        """Render storage options from either a mapping or a StorageOptionsExpression."""
        if isinstance(storage_options, dict):
            return self.format_table_engine_clauses(storage_options)
        return storage_options.to_sql()

    def format_create_table_like_statement(
        self, expr: "CreateTableLikeExpression"
    ) -> Tuple[str, tuple]:
        """Format ClickHouse ``CREATE TABLE target AS source``.

        ClickHouse has no ``LIKE`` keyword: a structure copy is spelled ``AS``.
        ``CREATE TABLE target CLONE AS source`` -- which also copies data -- is
        a *different* statement and lives in
        :meth:`format_create_table_clone_statement`, driven by
        ``CreateTableCloneExpression``. It used to be mentioned in this
        docstring as if it were something this method could emit; it never was.

        Raises:
            TypeError: ``CreateTableLikeExpression.table`` or ``.like_table`` is
                not a Table. Either one would otherwise render its own name as
                the target or the copied table's.
            UnsupportedFeatureError: The form is not available.
        """
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"CreateTableLikeExpression.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        if not isinstance(expr.like_table, Table):
            raise TypeError(
                f"CreateTableLikeExpression.like_table must be a Table, "
                f"got {type(expr.like_table).__name__}"
            )
        if not self.supports_create_table_like():
            raise UnsupportedFeatureError(self.name, "CREATE TABLE ... AS <source>")

        parts = ["CREATE"]
        if expr.temporary:
            parts.append("TEMPORARY")
        parts.append("TABLE")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        target = expr.table.to_sql()[0]
        source = expr.like_table.to_sql()[0]
        parts.append(target)
        parts.append(f"AS {source}")
        return " ".join(parts), ()

    def format_create_table_as_statement(
        self, expr: "CreateTableAsExpression"
    ) -> Tuple[str, tuple]:
        """Format ClickHouse ``CREATE TABLE ... AS <query>``.

        ClickHouse's CTAS always populates the new table and has no
        ``WITH [NO] DATA`` clause: each spelling is refused by name (measured:
        Code 62) instead of being rendered, and the unspecified state renders
        the plain statement through the generic formatter.

        Raises:
            UnsupportedFeatureError: ``WITH DATA`` or ``WITH NO DATA``, neither
                of which ClickHouse spells this way.
        """
        if expr.with_data:
            raise UnsupportedFeatureError(
                self.name,
                "CREATE TABLE ... WITH DATA",
                "ClickHouse CTAS always populates the new table; there is no "
                "WITH DATA clause.",
            )
        if expr.no_data:
            raise UnsupportedFeatureError(
                self.name,
                "CREATE TABLE ... WITH NO DATA",
                "ClickHouse CTAS cannot create an unpopulated table; there is "
                "no WITH NO DATA clause.",
            )
        return super().format_create_table_as_statement(expr)

    def format_create_table_clone_statement(
        self, expr: "CreateTableCloneExpression"
    ) -> Tuple[str, tuple]:
        """Format ClickHouse ``CREATE TABLE target CLONE AS source``.

        ClickHouse's zero-copy clone is ``CLONE AS``: the one engine where the
        keyword is neither bare ``CLONE`` nor ``COPY``, and neither
        ``COPY GRANTS`` nor the time-travel suffixes the generic form carries.
        The generic renderer is therefore overridden rather than reused.

        Reference:
        https://clickhouse.com/docs/sql-reference/statements/create/table#create-table-clone-as

        Raises:
            TypeError: ``CreateTableCloneExpression.table`` or ``.source_table``
                is not a Table. Either one would otherwise render its own name
                as the target or the cloned table's.
            UnsupportedFeatureError: A clause ClickHouse's ``CLONE AS`` has no
                form for, or the form is not available.
        """
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"CreateTableCloneExpression.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        if not isinstance(expr.source_table, Table):
            raise TypeError(
                f"CreateTableCloneExpression.source_table must be a Table, "
                f"got {type(expr.source_table).__name__}"
            )
        if not self.supports_create_table_clone():
            raise UnsupportedFeatureError(self.name, "CREATE TABLE ... CLONE AS")
        for unsupported, flag in (
            ("CREATE TABLE CLONE COPY GRANTS", expr.copy_grants),
            ("CREATE TABLE CLONE AT", expr.at),
            ("CREATE TABLE CLONE BEFORE", expr.before),
        ):
            if flag:
                raise UnsupportedFeatureError(
                    self.name,
                    unsupported,
                    "ClickHouse's CLONE AS has no such clause.",
                )

        parts = ["CREATE"]
        if expr.temporary:
            parts.append("TEMPORARY")
        parts.append("TABLE")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        target = expr.table.to_sql()[0]
        source = expr.source_table.to_sql()[0]
        parts.append(target)
        parts.append(f"CLONE AS {source}")
        return " ".join(parts), ()

    def format_column_definition(self, col_def: "ColumnDefinition") -> Tuple[str, tuple]:
        """Format a single column definition with ClickHouse-specific syntax.

        Accepts both the generic ``ColumnDefinition`` and the ClickHouse
        ``ClickHouseColumnDefinition``; the latter's ClickHouse-only attributes
        (``codec`` / ``materialized`` / ``alias`` / ``ttl``) are rendered here.

        Raises:
            TypeError: ``col_def.data_type`` is not a DataType. The generic
                constructor already refuses one, but ``ClickHouseColumnDefinition``
                binds its type differently and a ``str`` reaching here would
                render as a column of that literal text.
        """
        if not isinstance(col_def.data_type, DataType):
            raise TypeError(
                f"{type(col_def).__name__}.data_type must be a DataType, "
                f"got {type(col_def.data_type).__name__}"
            )
        from rhosocial.activerecord.backend.impl.clickhouse.expression.column import (
            ClickHouseColumnDefinition,
        )

        type_sql, type_params = col_def.data_type.to_sql()
        parts = [self.format_identifier(col_def.name), type_sql]
        params: List[Any] = list(type_params)

        for constraint in col_def.constraints:
            suffix, cp = self.format_column_constraint(constraint)
            constraint_text = suffix.strip()
            if constraint_text:
                parts.append(constraint_text)
            params.extend(list(cp))
            if constraint.is_auto_increment:
                raise UnsupportedFeatureError(
                    self.name, "AUTO_INCREMENT column",
                    suggestion="ClickHouse does not support AUTO_INCREMENT; use UUID or an explicit value."
                )

        attr_sql, attr_params = self.format_column_attributes(col_def)
        if attr_sql:
            parts.append(attr_sql.strip())
        params.extend(attr_params)

        if isinstance(col_def, ClickHouseColumnDefinition):
            if col_def.materialized is not None:
                mat_sql, mat_params = col_def.materialized.to_sql()
                parts.append(f"MATERIALIZED {mat_sql}")
                params.extend(mat_params)
            if col_def.alias is not None:
                alias_sql, alias_params = col_def.alias.to_sql()
                parts.append(f"ALIAS {alias_sql}")
                params.extend(alias_params)
            if col_def.codec:
                parts.append(f"CODEC({', '.join(col_def.codec)})")
            if col_def.ttl is not None:
                ttl_sql, ttl_params = col_def.ttl.to_sql()
                parts.append(f"TTL {ttl_sql}")
                params.extend(ttl_params)

        if col_def.comment is not None:
            comment_sql, _ = self.format_column_comment_clause(col_def.comment)
            parts.append(comment_sql.strip())

        return " ".join(parts), tuple(params)

    def format_table_constraint(self, t_const: "TableConstraint") -> Tuple[str, tuple]:
        """Format a table-level constraint.

        Raises:
            TypeError: ``t_const.foreign_key_table`` is not a Table. The check
                runs before the kind dispatch so the error names the wrong type
                rather than reporting FOREIGN KEY as unsupported, which is a
                different mistake and sends the caller looking in the wrong place.
        """
        from rhosocial.activerecord.backend.expression.statements import TableConstraintType
        foreign_key_table = getattr(t_const, "foreign_key_table", None)
        if foreign_key_table is not None and not isinstance(foreign_key_table, Table):
            raise TypeError(
                f"TableConstraint.foreign_key_table must be a Table, "
                f"got {type(foreign_key_table).__name__}"
            )
        parts = []
        params: List[Any] = []

        if t_const.name:
            parts.append(f"CONSTRAINT {self.format_identifier(t_const.name)}")

        if t_const.constraint_type == TableConstraintType.PRIMARY_KEY:
            if t_const.columns:
                cols_str = ", ".join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"PRIMARY KEY ({cols_str})")
        elif t_const.constraint_type == TableConstraintType.UNIQUE:
            raise UnsupportedFeatureError(
                self.name, "UNIQUE table constraint",
                suggestion="ClickHouse does not support UNIQUE constraints."
            )
        elif t_const.constraint_type == TableConstraintType.FOREIGN_KEY:
            raise UnsupportedFeatureError(
                self.name, "FOREIGN KEY constraint",
                suggestion="ClickHouse does not support FOREIGN KEY constraints."
            )

        return " ".join(parts), tuple(params)

    def format_index_definition(self, idx_def: "IndexDefinition") -> Tuple[str, tuple]:
        """Format an inline data-skipping INDEX definition (ClickHouse-specific).

        Renders ``INDEX <name> (<columns>) TYPE <type> GRANULARITY <n>``; the
        granularity is taken from :class:`ClickHouseIndexDefinition` and defaults
        to 1 for a plain ``IndexDefinition``.
        """
        from ..expression.index import ClickHouseIndexDefinition

        if idx_def.unique:
            raise UnsupportedFeatureError(
                self.name, "UNIQUE index",
                suggestion="ClickHouse cannot enforce unique indexes."
            )
        parts = ["INDEX", self.format_identifier(idx_def.name)]
        cols_str = ", ".join(self.format_identifier(c) for c in idx_def.columns)
        parts.append(f"({cols_str})")
        idx_type = idx_def.type if idx_def.type else "minmax"
        parts.append(f"TYPE {idx_type}")
        granularity = idx_def.granularity if isinstance(idx_def, ClickHouseIndexDefinition) else 1
        parts.append(f"GRANULARITY {granularity}")
        return " ".join(parts), ()

    def format_storage_options(self, expr: "StorageOptionsExpression") -> Tuple[str, tuple]:
        """Format ClickHouse table storage options.

        Delegates to ``format_table_engine_clauses`` using the expression's
        options mapping.  Values are rendered verbatim (not quoted) because
        ClickHouse storage option values are SQL fragments (engine names,
        column lists, etc.).
        """
        return self.format_table_engine_clauses(expr.options)

    def supports_if_not_exists_table(self) -> bool:
        """Whether CREATE TABLE IF NOT EXISTS is supported."""
        return True

    def supports_if_exists_table(self) -> bool:
        """Whether DROP TABLE IF EXISTS is supported."""
        return True

    def supports_drop_table_cascade(self) -> bool:
        """ClickHouse DROP TABLE has no CASCADE spelling (measured: Code 62).

        Declared here, on the mixin that precedes core's ``TableMixin`` in the
        MRO: declared on ``ClickHouseConstraintMixin`` (which follows it) the
        answer would be shadowed by the generic ``True`` and the formatter
        would render SQL the server rejects.
        """
        return False

    def supports_drop_table_restrict(self) -> bool:
        """ClickHouse DROP TABLE has no RESTRICT spelling (measured: Code 62)."""
        return False

    def supports_temporary_table(self) -> bool:
        """Whether CREATE TEMPORARY TABLE is supported."""
        return True

    def supports_rename_table(self) -> bool:
        """Whether RENAME TABLE is supported."""
        return True

    def supports_rename_column(self) -> bool:
        """Whether RENAME COLUMN is supported."""
        return True

    def supports_ilike(self) -> bool:
        """ClickHouse supports ILIKE operator."""
        return True

