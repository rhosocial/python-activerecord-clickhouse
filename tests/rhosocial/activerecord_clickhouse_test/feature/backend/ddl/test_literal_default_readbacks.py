# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_literal_default_readbacks.py
"""The tier-2 literal spellings, verified end to end against the live server.

Moved here from the expression area (``feature/backend/expression`` used to
hold them beside the render-only literal tests): these cases open a connection,
create tables and read rows back, which is backend integration by the org
rules (expression-dialect §12) -- expression tests stay construction → render,
and every check that needs a real database belongs in the scenario-driven
area this package already runs.

The two spellings under test are the backend's whole tier-2 override:
``unhex('...')`` for bytes and the bare quoted text for a UUID, each exercised
as a column DEFAULT -- the path a DDL position actually takes -- with an
INSERT and a read-back to prove the stored value round-trips.

Every verdict below was measured against the instance
``tests/config/clickhouse_scenarios.yaml`` names ``clickhouse_http``:
**ClickHouse 26.7.3.19 (official build)**, HTTP on ``127.0.0.1:18682``,
database ``test_db``. The statements and readbacks behind each verdict are
recorded in ``mixins/literal.py``.
"""

import uuid as uuidlib

_UUID = uuidlib.UUID("01234567-89ab-cdef-0123-456789abcdef")
_UUID_TEXT = "01234567-89ab-cdef-0123-456789abcdef"


class TestLiteralDefaultReadbacks:
    """CREATE TABLE with the literal as a DEFAULT, INSERT, read back, compare."""

    def _drop(self, backend, name):
        backend.execute(f"DROP TABLE IF EXISTS {name}")

    def test_binary_default_roundtrip(self, clickhouse_backend):
        from rhosocial.activerecord.backend.expression.objects import Table
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraint,
            ColumnDefaultConstraint,
            ColumnDefinition,
            CreateTableStatement,
        )
        from rhosocial.activerecord.backend.expression.types import (
            IntegerType,
            VarCharType,
        )

        backend = clickhouse_backend
        dialect = backend.dialect
        name = "probe_literal_bin"
        self._drop(backend, name)
        try:
            # The bare bytes scalar: the DEFAULT clause normalises it into
            # an inline Literal, which is the path under test.
            create = CreateTableStatement(
                dialect,
                Table(dialect, name),
                [
                    ColumnDefinition(dialect, "id", IntegerType(dialect)),
                    ColumnDefinition(
                        dialect,
                        "s",
                        VarCharType(dialect=dialect),
                        constraints=[
                            ColumnConstraint(
                                dialect,
                                branch=ColumnDefaultConstraint(dialect, b"\x01\x02"),
                            )
                        ],
                    ),
                ],
                storage_options={"ENGINE": "MergeTree()", "ORDER BY": "id"},
            )
            sql, params = create.to_sql()
            assert params == ()
            assert "unhex('0102')" in sql
            backend.execute(sql, params)
            backend.execute(f"INSERT INTO {name} (id) VALUES (1)")
            result = backend.execute(f"SELECT hex(s) FROM {name}")
            assert [row["hex(s)"] for row in result.data] == ["0102"]
        finally:
            self._drop(backend, name)

    def test_uuid_default_roundtrip(self, clickhouse_backend):
        from rhosocial.activerecord.backend.expression.objects import Table
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraint,
            ColumnDefaultConstraint,
            ColumnDefinition,
            CreateTableStatement,
        )
        from rhosocial.activerecord.backend.expression.types import (
            IntegerType,
            UUIDType,
        )

        backend = clickhouse_backend
        dialect = backend.dialect
        name = "probe_literal_uuid"
        self._drop(backend, name)
        try:
            create = CreateTableStatement(
                dialect,
                Table(dialect, name),
                [
                    ColumnDefinition(dialect, "id", IntegerType(dialect)),
                    ColumnDefinition(
                        dialect,
                        "u",
                        UUIDType(dialect),
                        constraints=[
                            ColumnConstraint(
                                dialect,
                                branch=ColumnDefaultConstraint(dialect, _UUID),
                            )
                        ],
                    ),
                ],
                storage_options={"ENGINE": "MergeTree()", "ORDER BY": "id"},
            )
            sql, params = create.to_sql()
            assert params == ()
            assert f"'{_UUID_TEXT}'" in sql
            backend.execute(sql, params)
            backend.execute(f"INSERT INTO {name} (id) VALUES (1)")
            result = backend.execute(f"SELECT toString(u) FROM {name}")
            assert [row["toString(u)"] for row in result.data] == [_UUID_TEXT]
        finally:
            self._drop(backend, name)
