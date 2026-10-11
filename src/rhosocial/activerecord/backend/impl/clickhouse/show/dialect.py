# src/rhosocial/activerecord/backend/impl/clickhouse/show/dialect.py
"""
ClickHouse SHOW command dialect mixin.

This module provides the ClickHouse-specific SQL generation for SHOW commands.
It implements the format_show_* methods that are called by the expression classes.

The mixin is added to ClickHouseDialect to provide SHOW command support.
All methods follow the pattern:
- Accept an expression parameter
- Extract parameters from expression.get_params()
- Generate SQL string and parameter tuple
- Return (sql, params) tuple

Nine of these are ClickHouse statements and produce SQL:
``SHOW CREATE TABLE``, ``SHOW CREATE VIEW``, ``SHOW [FULL] TABLES``,
``SHOW DATABASES``, ``SHOW [FULL] COLUMNS``, ``SHOW INDEX``,
``SHOW PROCESSLIST``, ``SHOW ENGINES`` and ``SHOW GRANTS`` (all nine verified
against the 26.7.3.19 scenario server; the ``SHOW`` reference page at
https://clickhouse.com/docs/reference/statements/show documents each).
The rest of the MySQL ``SHOW`` set is ClickHouse's to not have; each raises
``UnsupportedFeatureError`` naming the ClickHouse replacement, so no method
here emits SQL this server would reject.

Two places where ClickHouse's own grammar is narrower than MySQL's, and the
rendering has to respect that rather than MySQL's shape:

* ``SHOW COLUMNS`` / ``SHOW INDEX`` take the database as part of the table
  reference (``SHOW COLUMNS FROM db.t``), never as a second ``FROM``. The
  documentation lists ``[{FROM | IN} <db>]``, but 26.7.3.19 answers
  ``SHOW INDEX FROM t FROM db`` with
  ``Code: 62 ... Expected one of: ParserArrayOfJSONIdentifierDelimiter, token
  sequence, OpeningSquareBracket, Dot, token, WHERE, INTO OUTFILE, FORMAT,
  SETTINGS, ParallelWithClause, PARALLEL WITH, end of query``; the abbreviated
  ``db.t`` form is the one the server accepts.
* ``SHOW PROCESSLIST`` has no ``FULL`` variant (26.7.3.19:
  ``Code: 62 ... Expected one of: DATABASES, CLUSTERS, MERGES, FILESYSTEM
  CACHES, CLUSTER, CHANGED, SETTINGS, TEMPORARY, TABLES, DICTIONARIES, COLUMNS,
  FIELDS``), so ``full=True`` cannot be rendered and is not rendered.
"""

from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Table, View

if TYPE_CHECKING:
    from ..expression.show import (
        ShowCreateTableExpression,
        ShowCreateViewExpression,
        ShowColumnsExpression,
        ShowIndexExpression,
        ShowTablesExpression,
        ShowDatabasesExpression,
        ShowTableStatusExpression,
        ShowTriggersExpression,
        ShowCreateTriggerExpression,
        ShowVariablesExpression,
        ShowStatusExpression,
        ShowProcessListExpression,
        ShowWarningsExpression,
        ShowErrorsExpression,
        ShowEnginesExpression,
        ShowCharsetExpression,
        ShowCollationExpression,
        ShowGrantsExpression,
        ShowPluginsExpression,
    )


class ClickHouseShowDialectMixin:
    """ClickHouse SHOW command SQL generation mixin.

    Provides format_show_* methods for generating ClickHouse SHOW command SQL.
    All methods take an expression parameter and return (sql, params) tuple.

    This mixin is added to ClickHouseDialect to provide SHOW functionality.
    """

    # ========== Shared helpers ==========

    def _qualified_table(self, table: str, schema: Optional[str] = None) -> str:
        """Render ``table`` or ``db.table`` as one identifier reference.

        ``SHOW COLUMNS`` and ``SHOW INDEX`` in ClickHouse take the database
        inside the table reference (``SHOW COLUMNS FROM db.t``); the two-``FROM``
        form MySQL allows is a ``SYNTAX_ERROR`` on 26.7.3.19. Measured error:
        ``Code: 62. DB::Exception: Syntax error: failed at position 34 (FROM):
        FROM test_db. Expected one of: ParserArrayOfJSONIdentifierDelimiter,
        token sequence, OpeningSquareBracket, Dot, token, WHERE, INTO OUTFILE,
        FORMAT, SETTINGS, ParallelWithClause, PARALLEL WITH, end of query.
        (SYNTAX_ERROR)``.
        """
        if schema:
            return f"{self.format_identifier(schema)}.{self.format_identifier(table)}"
        return self.format_identifier(table)

    # ========== SHOW CREATE Statements ==========

    def format_show_create_table(self, expr: "ShowCreateTableExpression") -> Tuple[str, tuple]:
        """Format SHOW CREATE TABLE statement.

        The name goes through ``format_table_object``, so the ``schema`` slot
        -- a ClickHouse database -- becomes the object's ``catalog_name`` and is
        rendered by the same code that renders every other qualified name.
        """
        params = expr.get_params()
        table = Table(
            self, params["table"], catalog_name=params.get("schema")
        ).to_sql()[0]
        return f"SHOW CREATE TABLE {table}", ()

    def format_show_create_view(self, expr: "ShowCreateViewExpression") -> Tuple[str, tuple]:
        """Format SHOW CREATE VIEW statement."""
        params = expr.get_params()
        view = View(
            self, params["view_name"], catalog_name=params.get("schema")
        ).to_sql()[0]
        return f"SHOW CREATE VIEW {view}", ()

    def format_show_create_trigger(self, expr: "ShowCreateTriggerExpression") -> Tuple[str, tuple]:
        """Format SHOW CREATE TRIGGER statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW CREATE TRIGGER",
            suggestion="ClickHouse does not support triggers.",
        )

    # ========== SHOW COLUMNS/INDEX ==========

    def format_show_columns(self, expr: "ShowColumnsExpression") -> Tuple[str, tuple]:
        """Format SHOW [FULL] COLUMNS FROM <table> [LIKE <pattern>].

        ClickHouse has this statement and answers it with lower-cased column
        names — on 26.7.3.19 ``SHOW COLUMNS FROM db.t`` reports ``field``,
        ``type``, ``null``, ``key``, ``default``, ``extra``, and adds
        ``collation``, ``comment`` and ``privileges`` under ``FULL``. Bare
        ``SHOW COLUMNS`` (no table) is a ``SYNTAX_ERROR``: the server expects
        ``FROM`` or ``IN`` after the keyword.

        ``EXTENDED`` is also accepted and documented but has no effect, so it is
        not rendered.
        """
        params = expr.get_params()
        table = params["table"]
        schema = params.get("schema")
        full = params.get("full", False)
        like_pattern = params.get("like_pattern")

        parts = ["SHOW"]
        if full:
            parts.append("FULL")
        parts.append("COLUMNS FROM")
        parts.append(self._qualified_table(table, schema))

        sql_params = ()
        if like_pattern:
            parts.append(f"LIKE {self.p()}")
            sql_params = (like_pattern,)

        return " ".join(parts), sql_params

    def format_show_index(self, expr: "ShowIndexExpression") -> Tuple[str, tuple]:
        """Format SHOW INDEX FROM <table>.

        ClickHouse has this statement, explicitly "for compatibility with MySQL",
        and answers it with ClickHouse's own column names — notably ``pk_col``
        where MySQL says ``Column_name``, and ``index_type`` carrying
        ``PRIMARY`` / ``MINMAX`` / ``BLOOM_FILTER`` / ``SET`` / ... rather than
        ``BTREE``. See ``https://clickhouse.com/docs/reference/statements/show``.
        """
        params = expr.get_params()
        table = params["table"]
        schema = params.get("schema")
        return f"SHOW INDEX FROM {self._qualified_table(table, schema)}", ()

    # ========== SHOW TABLES/DATABASES ==========

    def format_show_tables(self, expr: "ShowTablesExpression") -> Tuple[str, tuple]:
        """Format SHOW [FULL] TABLES statement."""
        params = expr.get_params()
        schema = params.get("schema")
        full = params.get("full", False)
        like_pattern = params.get("like_pattern")

        parts = ["SHOW"]
        if full:
            parts.append("FULL")
        parts.append("TABLES")
        if schema:
            parts.append(f"FROM {self.format_identifier(schema)}")

        sql_params = ()
        if like_pattern:
            parts.append(f"LIKE {self.p()}")
            sql_params = (like_pattern,)

        return " ".join(parts), sql_params

    def format_show_databases(self, expr: "ShowDatabasesExpression") -> Tuple[str, tuple]:
        """Format SHOW DATABASES statement."""
        params = expr.get_params()
        like_pattern = params.get("like_pattern")

        if like_pattern:
            return f"SHOW DATABASES LIKE {self.p()}", (like_pattern,)
        return "SHOW DATABASES", ()

    def format_show_table_status(self, expr: "ShowTableStatusExpression") -> Tuple[str, tuple]:
        """Format SHOW TABLE STATUS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW TABLE STATUS",
            suggestion="Query system.tables instead.",
        )

    # ========== SHOW TRIGGERS ==========

    def format_show_triggers(self, expr: "ShowTriggersExpression") -> Tuple[str, tuple]:
        """Format SHOW TRIGGERS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW TRIGGERS",
            suggestion="ClickHouse does not support triggers.",
        )

    # ========== SHOW VARIABLES/STATUS ==========

    def format_show_variables(self, expr: "ShowVariablesExpression") -> Tuple[str, tuple]:
        """Format SHOW VARIABLES statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW VARIABLES",
            suggestion="Query system.settings instead.",
        )

    def format_show_status(self, expr: "ShowStatusExpression") -> Tuple[str, tuple]:
        """Format SHOW STATUS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW STATUS",
            suggestion="Query system.metrics, system.events, or system.asynchronous_metrics instead.",
        )

    # ========== SHOW PROCESSLIST/WARNINGS/ERRORS ==========

    def format_show_processlist(self, expr: "ShowProcessListExpression") -> Tuple[str, tuple]:
        """Format SHOW PROCESSLIST.

        ClickHouse's ``SHOW PROCESSLIST`` is ``SELECT * FROM system.processes``:
        it answers with that table's 43 lower-cased columns (``query_id``,
        ``user``, ``address``, ``port``, ``elapsed``, ``current_database``,
        ``query``, ...). ``full`` is accepted and ignored because ClickHouse has
        no ``FULL`` variant — on 26.7.3.19 ``SHOW FULL PROCESSLIST`` is
        ``Code: 62 ... Expected one of: DATABASES, CLUSTERS, MERGES, FILESYSTEM
        CACHES, CLUSTER, CHANGED, SETTINGS, TEMPORARY, TABLES, DICTIONARIES,
        COLUMNS, FIELDS. (SYNTAX_ERROR)``, and the statement already reports
        the full query text in ``query``.
        """
        return "SHOW PROCESSLIST", ()

    def format_show_warnings(self, expr: "ShowWarningsExpression") -> Tuple[str, tuple]:
        """Format SHOW WARNINGS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW WARNINGS",
            suggestion="Query system.query_log or system.text_log instead.",
        )

    def format_show_errors(self, expr: "ShowErrorsExpression") -> Tuple[str, tuple]:
        """Format SHOW ERRORS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW ERRORS",
            suggestion="Query system.errors or system.query_log instead.",
        )

    # ========== SHOW ENGINES/CHARSET/COLLATION ==========

    def format_show_engines(self, expr: "ShowEnginesExpression") -> Tuple[str, tuple]:
        """Format SHOW ENGINES.

        ClickHouse's ``SHOW ENGINES`` is ``SELECT * FROM system.table_engines``.
        Its columns are its own, not MySQL's: ``name`` plus eight
        ``supports_*`` flags (``supports_settings``,
        ``supports_skipping_indices``, ``supports_projections``,
        ``supports_sort_order``, ``supports_ttl``, ``supports_replication``,
        ``supports_deduplication``, ``supports_parallel_insert``) and then
        ``description``, ``syntax``, ``examples``, ``introduced_in`` and
        ``related``. MySQL's ``Engine`` / ``Support`` / ``Transactions`` / ``XA``
        / ``Savepoints`` appear nowhere in that list.
        """
        return "SHOW ENGINES", ()

    def format_show_charset(self, expr: "ShowCharsetExpression") -> Tuple[str, tuple]:
        """Format SHOW CHARACTER SET statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW CHARACTER SET",
            suggestion="ClickHouse does not support MySQL character sets; query system.character_sets instead.",
        )

    def format_show_collation(self, expr: "ShowCollationExpression") -> Tuple[str, tuple]:
        """Format SHOW COLLATION statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW COLLATION",
            suggestion="ClickHouse does not support MySQL collations; query system.collations instead.",
        )

    # ========== SHOW GRANTS/PLUGINS ==========

    def format_show_grants(self, expr: "ShowGrantsExpression") -> Tuple[str, tuple]:
        """Format SHOW GRANTS [FOR <user>].

        ClickHouse's grammar is ``SHOW GRANTS [FOR user1 [, user2 ...]] [WITH
        IMPLICIT] [FINAL]`` — a comma-separated list of access-entity names,
        with **no** ``user@host`` form: ``SHOW GRANTS FOR root@localhost`` on
        26.7.3.19 is ``Code: 511. DB::Exception: There is no role
        `root@localhost` in `user directories`. (UNKNOWN_ROLE)``, because
        ClickHouse identifies access entities by role name alone. A supplied
        ``host`` is therefore not rendered; ``FOR <user>`` is the whole
        statement. ``SHOW GRANTS FOR CURRENT USER`` is also a ``SYNTAX_ERROR``
        here; omitting ``FOR`` is how the current user's grants are read.
        """
        params = expr.get_params()
        user = params.get("user")
        if not user:
            return "SHOW GRANTS", ()
        return f"SHOW GRANTS FOR {self.format_identifier(user)}", ()

    def format_show_plugins(self, expr: "ShowPluginsExpression") -> Tuple[str, tuple]:
        """Format SHOW PLUGINS statement.

        Note:
            MySQL-only command, not supported by ClickHouse.
        """
        raise UnsupportedFeatureError(
            self.name,
            "SHOW PLUGINS",
            suggestion="Query system.functions for user-defined functions instead.",
        )
