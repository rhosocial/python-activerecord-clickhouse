# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_column.py
from typing import Any, Dict, Tuple


class ClickHouseDDLColumnMixin:
    """ClickHouse DDL column action formatting."""

    def supports_add_column_if_not_exists(self) -> bool:
        """ClickHouse supports ADD COLUMN IF NOT EXISTS."""
        return True

    def supports_drop_column_if_exists(self) -> bool:
        """ClickHouse supports DROP COLUMN IF EXISTS."""
        return True

    def supports_drop_constraint_if_exists(self) -> bool:
        """True: ``DROP CONSTRAINT IF EXISTS`` is accepted and is a silent no-op
        when the constraint is absent.

        ClickHouse 26.7.3.19 (official build), measured on the instance
        ``tests/config/clickhouse_scenarios.yaml`` names ``clickhouse_http``
        (``127.0.0.1:18682``, database ``test_db``)::

            ALTER TABLE probe_t DROP CONSTRAINT nope
            -> Code: 36. DB::Exception: Wrong constraint name.
               Cannot find constraint `nope` to drop. (BAD_ARGUMENTS)

            ALTER TABLE probe_t DROP CONSTRAINT IF EXISTS nope
            -- accepted; system.constraints unchanged, no result set, no error

        So on this backend the ``IF EXISTS`` form is **the** idempotent path,
        exactly as it is on MariaDB, PostgreSQL and SQL Server. The plain form
        is a real error, so catching Code 36 instead of spelling ``IF EXISTS``
        would be both worse and less portable -- MySQL has no
        ``DROP CONSTRAINT IF EXISTS`` at all and fails at the parser (1064).

        Declared here (and in this package) rather than left to core's
        ``DDLColumnMixin`` default of ``False``: that default is shared with the
        dummy dialect and is exactly the kind of value that can move silently.

        Core renders the clause itself, as of its ``4875ea3b`` fix (before it,
        core read this probe but never spelled the two words, and this module
        carried an override to add them; that override is gone -- keeping it
        now splices a second ``IF EXISTS`` and produces
        ``DROP CONSTRAINT IF EXISTS IF EXISTS <name>``).

        Only CHECK and ASSUME can be named here -- they are the only kinds that
        exist. The primary key is not a constraint and cannot be dropped by
        name; see
        :meth:`ClickHouseConstraintMixin.supports_drop_constraint`.
        """
        return True

    def supports_generated_columns(self) -> bool:
        """Whether generated columns are supported (alias for protocol)."""
        return False

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
