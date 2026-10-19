# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/ddl_column.py
from enum import Enum
from typing import Any, Dict, Tuple

from rhosocial.activerecord.backend.expression.bases import BaseExpression


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
        if action.if_not_exists is True:
            parts.append("ADD COLUMN IF NOT EXISTS")
        else:
            parts.append("ADD COLUMN")
        parts.append(column_sql)
        # The core AddColumnAction carries no position field, so there is
        # nothing here to place. ClickHouse's ``AFTER <column>`` arrives through
        # ``ClickHouseAddColumnAction.after``, which has its own entry below.
        return " ".join(parts), column_params

    def format_clickhouse_add_column_action(self, action) -> Tuple[str, tuple]:
        """``ADD COLUMN ... AFTER <column>`` — the ClickHouse position clause.

        ClickHouse places a new column with ``AFTER <name>`` (also ``FIRST``);
        no other backend has the clause, which is why it lives on the derived
        node and gets its own entry rather than being probed for on the core
        action. ``after=None`` renders exactly what the core entry renders, so
        the clause is a position the caller asked for and nothing else.

        Documented on
        ``https://clickhouse.com/docs/sql-reference/statements/alter/column``;
        the spelling is the server's, quoted identifiers included: the name is
        rendered through ``format_column_reference`` so a reserved word arrives
        quoted.
        """
        sql, params = self.format_add_column_action(action)
        if action.after is not None:
            after_sql, after_params = self.format_column(action.after)
            sql = f"{sql} AFTER {after_sql}"
            params = params + after_params
        return sql, params

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
        # ``operation`` accepts the enum or its raw spelling; which one it
        # is is a type question, so it is asked with isinstance rather than
        # probed for a ``value`` attribute (the core formatter reads it the
        # same way).
        operation = (
            action.operation.value if isinstance(action.operation, Enum) else str(action.operation)
        )
        col_name = self.format_identifier(action.column_name)

        if operation == "DROP DEFAULT":
            return f"MODIFY COLUMN {col_name} REMOVE DEFAULT", ()

        if operation == "SET DEFAULT":
            new_value = action.new_value
            if isinstance(new_value, str):
                escaped = self._escape_sql_string(new_value)
                return f"ALTER COLUMN {col_name} DEFAULT '{escaped}'", ()
            if isinstance(new_value, bool):
                return f"ALTER COLUMN {col_name} DEFAULT {1 if new_value else 0}", ()
            if new_value is None:
                raise ValueError("SET DEFAULT requires a default value")
            if isinstance(new_value, (int, float)):
                return f"ALTER COLUMN {col_name} DEFAULT {new_value}", ()
            if isinstance(new_value, BaseExpression):
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
