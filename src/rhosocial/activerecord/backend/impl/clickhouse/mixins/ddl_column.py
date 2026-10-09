# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_column.py
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_table import (
        TableConstraint,
    )


class ClickHouseDDLColumnMixin:
    """ClickHouse DDL column action formatting."""

    def supports_add_column_if_not_exists(self) -> bool:
        """ClickHouse supports ADD COLUMN IF NOT EXISTS."""
        return True

    def supports_drop_column_if_exists(self) -> bool:
        """ClickHouse supports DROP COLUMN IF EXISTS."""
        return True

    def supports_drop_constraint_if_exists(self) -> bool:
        """Whether DROP CONSTRAINT IF EXISTS is supported."""
        return False

    def supports_generated_columns(self) -> bool:
        """Whether generated columns are supported (alias for protocol)."""
        return False

    def format_add_table_constraint_action(self, action: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ADD CONSTRAINT",
            suggestion="ClickHouse does not support table constraints."
        )

    def format_add_column_action(self, action) -> Tuple[str, tuple]:
        column_sql, column_params = self.format_column_definition(action.column)
        parts = []
        if getattr(action, "if_not_exists", None) is True:
            parts.append("ADD COLUMN IF NOT EXISTS")
        else:
            parts.append("ADD COLUMN")
        parts.append(column_sql)
        after = getattr(action, "after", None)
        if after:
            parts.append(f"AFTER {self.format_identifier(after)}")
        return " ".join(parts), column_params

    def format_alter_column_action(self, action) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... ALTER/MODIFY COLUMN for a default change.

        ClickHouse has no ``SET DEFAULT`` / ``DROP DEFAULT`` action. What it has,
        per ``https://clickhouse.com/docs/reference/statements/alter/column`` and
        measured on 26.7.3.19:

        =====================================  ==========================================
        intent                                  ClickHouse
        =====================================  ==========================================
        set a default expression                ``ALTER COLUMN c [TYPE] DEFAULT expr``
        remove a default expression             ``MODIFY COLUMN c REMOVE DEFAULT``
        =====================================  ==========================================

        The MySQL spellings this used to emit are both rejected. Quoting the
        server, for ``ALTER TABLE t ALTER COLUMN a SET DEFAULT 5``::

            Code: 62. DB::Exception: Syntax error: failed at position 45 (SET):
            SET DEFAULT 5. Expected one of: token sequence, Dot, token, REMOVE,
            MODIFY SETTING, RESET SETTING, ADD ENUM VALUES, NULL, NOT, DEFAULT,
            MATERIALIZED, EPHEMERAL, ALIAS, AUTO_INCREMENT, TTL, PRIMARY KEY,
            COMMENT, CODEC, TYPE. (SYNTAX_ERROR)

        ``DEFAULT`` is on that list and ``SET`` is not, so the keyword ``SET`` is
        the whole difference; and for ``ALTER TABLE t ALTER COLUMN a DROP
        DEFAULT`` the same error names no ``DROP`` at all — removing a property
        is ``MODIFY COLUMN ... REMOVE``, which the reference page lists for
        ``DEFAULT``, ``ALIAS``, ``MATERIALIZED``, ``CODEC``, ``COMMENT``, ``TTL``
        and ``SETTINGS``.

        Note that ClickHouse does require a literal default expression here, so
        the value is inlined rather than parameterised.
        """
        operation = getattr(action.operation, "value", None) or str(action.operation)
        col_name = self.format_identifier(action.column_name)

        if operation == "DROP DEFAULT":
            return f"MODIFY COLUMN {col_name} REMOVE DEFAULT", ()

        if operation == "SET DEFAULT":
            new_value = getattr(action, "new_value", None)
            if isinstance(new_value, str):
                escaped = self._escape_sql_string(new_value)
                return f"ALTER COLUMN {col_name} DEFAULT '{escaped}'", ()
            if isinstance(new_value, bool):
                return f"ALTER COLUMN {col_name} DEFAULT {1 if new_value else 0}", ()
            if new_value is None:
                raise ValueError("SET DEFAULT requires a default value")
            if isinstance(new_value, (int, float)):
                return f"ALTER COLUMN {col_name} DEFAULT {new_value}", ()
            if hasattr(new_value, "to_sql"):
                value_sql, value_params = new_value.to_sql()
                return f"ALTER COLUMN {col_name} DEFAULT {value_sql}", tuple(value_params)
            return f"ALTER COLUMN {col_name} DEFAULT {new_value}", ()

        return super().format_alter_column_action(action)

    def format_table_constraint(
        self,
        t_const: "TableConstraint"
    ) -> Tuple[str, tuple]:
        """Format a table-level constraint.

        ClickHouse has two table-level constraint forms and they are not these:
        ``CONSTRAINT name CHECK <expr>`` and ``CONSTRAINT name ASSUME <expr>``
        (https://clickhouse.com/docs/reference/statements/create/table#constraints).
        Only ``PRIMARY KEY`` is rendered from the SQL-standard set.

        ``UNIQUE`` and ``FOREIGN KEY`` refuse rather than emit, and the reason is
        not symmetric:

        * ``UNIQUE (col)`` is a ``SYNTAX_ERROR`` on 26.7.3.19 — ``Code: 62.
          Syntax error: failed at position 50 ((): (col)). Expected one of: NULL,
          NOT, DEFAULT, MATERIALIZED, EPHEMERAL, ALIAS, AUTO_INCREMENT, TTL,
          PRIMARY KEY, data type, identifier. (SYNTAX_ERROR)`` — so rendering it
          would be an error the caller sees immediately.
        * ``FOREIGN KEY`` **without** a ``CONSTRAINT`` name is *accepted and
          silently discarded*, and that is why it refuses. Measured on
          26.7.3.19: ``CREATE TABLE c (id UInt32, pid UInt32, FOREIGN KEY (pid)
          REFERENCES p(id)) ENGINE = MergeTree ORDER BY id`` succeeds, but
          ``SHOW CREATE TABLE c`` reports no foreign key,
          ``system.tables.create_table_query`` does not contain the string
          ``FOREIGN``, an orphan row inserts and reads back fine, and dropping
          the referenced parent also succeeds. (The *named* form ``CONSTRAINT fk
          FOREIGN KEY ...`` is a ``SYNTAX_ERROR`` expecting ``CHECK`` or
          ``ASSUME``, as are the inline column-level ``REFERENCES p(id)`` and
          the form written after the storage clauses.)

          So emitting it would be the worst of the three outcomes: no error at
          DDL time, no record in the schema, and no enforcement at write time.
          The referential-integrity bug would surface in production data with
          nothing in the server's metadata to explain it. Refusing turns that
          into an ``UnsupportedFeatureError`` at the point of declaration.
        """
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            TableConstraintType,
        )
        parts = []
        params: List[Any] = []

        if t_const.constraint_type == TableConstraintType.PRIMARY_KEY:
            if t_const.columns:
                cols_str = ', '.join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"PRIMARY KEY ({cols_str})")
        elif t_const.constraint_type == TableConstraintType.UNIQUE:
            raise UnsupportedFeatureError(
                self.name, "UNIQUE table constraint",
                suggestion="ClickHouse does not support UNIQUE constraints."
            )
        elif t_const.constraint_type == TableConstraintType.FOREIGN_KEY:
            raise UnsupportedFeatureError(
                self.name, "FOREIGN KEY constraint",
                suggestion=(
                    "ClickHouse does not support FOREIGN KEY constraints, and an "
                    "unnamed FOREIGN KEY (...) REFERENCES ... clause is accepted and "
                    "then silently discarded, so emitting one would produce a schema "
                    "with no foreign key and no enforcement. Maintain referential "
                    "integrity in the application, or use CONSTRAINT ... CHECK."
                )
            )

        return ' '.join(parts), tuple(params)

    def format_storage_options(self, storage_options: Dict[str, Any]) -> str:
        """
        Format storage options for ClickHouse.

        Args:
            storage_options: Dict with keys like 'ENGINE', 'ORDER BY', 'PARTITION BY'

        Returns:
            Formatted storage options string (e.g., "ENGINE = MergeTree() ORDER BY id")
        """
        parts = []
        for key, value in storage_options.items():
            if isinstance(value, str):
                parts.append(f"{key} = {value}")
            else:
                parts.append(f"{key} = {value}")
        return ' '.join(parts)
