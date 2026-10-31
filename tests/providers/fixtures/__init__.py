# tests/providers/fixtures/__init__.py
"""ClickHouse-specific DDL expression fixtures for the testsuite providers.

Each module in this package exposes a ``TABLE_EXPRESSIONS`` mapping of
table name -> factory callable ``Callable[[DialectLike, str], CreateTableStatement]``.

The factory functions build :class:`CreateTableStatement` instances that emit
ClickHouse-compatible DDL (ENGINE / CHARSET / COLLATE / inline indexes / FK with
ON DELETE CASCADE / TINYINT(1) / DATETIME(6) / ENUM / JSON).  The pre-existing
``.sql`` schema files under ``tests/rhosocial/activerecord_clickhouse_test/feature/<feature>/schema/``
remain as the authoritative reference for what the expressions here must
produce; they are simply no longer read at runtime by the providers.

The storage clauses are declared as expression nodes
(:func:`default_table_options` builds the clause run every table shares), so
the engine and sort-key values are rendered unquoted by the backend itself.
Each factory still routes its expression through :func:`to_clickhouse_ddl_sql`,
which drops the constraints ClickHouse rejects, producing DDL equivalent to the
reference ``.sql`` files.
"""
