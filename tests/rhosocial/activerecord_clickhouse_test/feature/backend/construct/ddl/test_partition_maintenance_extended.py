# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/ddl/test_partition_maintenance_extended.py
"""Offline contract for the ClickHouse partition operations beyond DROP/DETACH/ATTACH.

Each node here models a clause from the official ALTER TABLE ... PARTITION
reference (``REPLACE`` / ``MOVE`` / ``FREEZE`` / ``UNFREEZE`` / ``CLEAR``) or
the OPTIMIZE statement reference, and each is rendered by one formatter in
``ClickHousePartitionMixin``. The tests pin four things per operation:

* the exact SQL, including the ``PARTITION ID`` addressing form;
* the refusals the grammar requires, raised by name before any SQL exists;
* the backend-level helper that builds the node and executes its SQL;
* the probe that answers for the operation.

References:
https://clickhouse.com/docs/sql-reference/statements/alter/partition
https://clickhouse.com/docs/sql-reference/statements/alter/column
https://clickhouse.com/docs/sql-reference/statements/alter/projection
https://clickhouse.com/docs/sql-reference/statements/optimize
"""

from typing import List, Optional, Tuple

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
    ClickHouseClearInPartitionStatement,
    ClickHouseFreezePartitionStatement,
    ClickHouseMovePartitionStatement,
    ClickHouseOptimizePartitionStatement,
    ClickHouseReplacePartitionStatement,
    ClickHouseUnfreezePartitionStatement,
)
from rhosocial.activerecord.backend.impl.clickhouse.partition_maintenance import (
    ClickHousePartitionMaintenance,
)
from rhosocial.activerecord.backend.result import QueryResult


TABLE = "ar_partition_ext"
DATABASE = "analytics"
PARTITION_ID = "202601"


class _RecordingIntrospector:
    def __init__(self) -> None:
        self.invalidated: List[Tuple[object, Optional[str]]] = []

    def invalidate_cache(self, scope=None, name: Optional[str] = None) -> None:
        self.invalidated.append((scope, name))


class _RecordingBackend:
    """Records the statement the service would execute."""

    def __init__(self, dialect: ClickHouseDialect) -> None:
        self.dialect = dialect
        self.introspector = _RecordingIntrospector()
        self.calls: List[Tuple[str, tuple]] = []
        self.result = QueryResult(affected_rows=1)

    def execute(self, sql: str, params: tuple = ()) -> QueryResult:
        self.calls.append((sql, params))
        return self.result


@pytest.fixture(scope="module")
def dialect() -> ClickHouseDialect:
    return ClickHouseDialect(version=(26, 7, 3))


@pytest.fixture
def service(dialect: ClickHouseDialect) -> ClickHousePartitionMaintenance:
    return ClickHousePartitionMaintenance(_RecordingBackend(dialect))


def _render(statement) -> Tuple[str, tuple]:
    return statement.to_sql()


def _feature(statement) -> str:
    with pytest.raises(UnsupportedFeatureError) as excinfo:
        statement.to_sql()
    return excinfo.value.feature_name


# --------------------------------------------------------------------------- #
# REPLACE PARTITION ... FROM
# --------------------------------------------------------------------------- #


class TestReplacePartition:
    def test_renders_partition_id_and_source(self, dialect):
        sql, params = _render(
            ClickHouseReplacePartitionStatement(dialect, TABLE, PARTITION_ID, "staging")
        )

        assert sql == (
            f"ALTER TABLE `{TABLE}` REPLACE PARTITION ID '{PARTITION_ID}' "
            "FROM `staging`"
        )
        assert params == ()

    def test_database_lands_in_the_catalog_slot_on_both_tables(self, dialect):
        sql, _params = _render(
            ClickHouseReplacePartitionStatement(
                dialect,
                TABLE,
                PARTITION_ID,
                "staging",
                schema=DATABASE,
                source_schema="staging_db",
            )
        )

        assert sql == (
            f"ALTER TABLE `{DATABASE}`.`{TABLE}` REPLACE PARTITION ID "
            f"'{PARTITION_ID}' FROM `staging_db`.`staging`"
        )

    def test_a_missing_source_is_refused_by_name(self, dialect):
        assert (
            _feature(
                ClickHouseReplacePartitionStatement(dialect, TABLE, PARTITION_ID, "")
            )
            == "REPLACE PARTITION"
        )

    def test_a_missing_partition_is_refused_by_name(self, dialect):
        assert (
            _feature(
                ClickHouseReplacePartitionStatement(dialect, TABLE, None, "staging")
            )
            == "REPLACE PARTITION"
        )

    def test_the_backend_helper_executes_the_rendered_statement(self, service):
        backend = service.backend

        assert service.replace(TABLE, PARTITION_ID, "staging") is backend.result
        assert backend.calls == [
            (
                f"ALTER TABLE `{TABLE}` REPLACE PARTITION ID '{PARTITION_ID}' "
                "FROM `staging`",
                (),
            )
        ]
        assert backend.introspector.invalidated == [(IntrospectionScope.TABLE, TABLE)]


# --------------------------------------------------------------------------- #
# MOVE PARTITION ... TO DISK | VOLUME | TABLE
# --------------------------------------------------------------------------- #


class TestMovePartition:
    @pytest.mark.parametrize("destination", ["DISK", "VOLUME", "disk", "volume"])
    def test_disk_and_volume_targets_are_literals(self, dialect, destination):
        sql, params = _render(
            ClickHouseMovePartitionStatement(
                dialect, TABLE, PARTITION_ID, destination, "cold"
            )
        )

        assert sql == (
            f"ALTER TABLE `{TABLE}` MOVE PARTITION ID '{PARTITION_ID}' "
            f"TO {destination.upper()} 'cold'"
        )
        assert params == ()

    def test_table_target_is_an_identifier(self, dialect):
        sql, _params = _render(
            ClickHouseMovePartitionStatement(
                dialect, TABLE, PARTITION_ID, "TABLE", "archive"
            )
        )

        assert sql == (
            f"ALTER TABLE `{TABLE}` MOVE PARTITION ID '{PARTITION_ID}' "
            "TO TABLE `archive`"
        )

    def test_table_target_carries_its_database(self, dialect):
        sql, _params = _render(
            ClickHouseMovePartitionStatement(
                dialect,
                TABLE,
                PARTITION_ID,
                "TABLE",
                "archive",
                target_schema=DATABASE,
            )
        )

        assert sql.endswith(f"TO TABLE `{DATABASE}`.`archive`")

    def test_an_unknown_destination_is_refused_by_name(self, dialect):
        assert (
            _feature(
                ClickHouseMovePartitionStatement(
                    dialect, TABLE, PARTITION_ID, "CLUSTER", "db1"
                )
            )
            == "MOVE PARTITION TO CLUSTER"
        )

    def test_a_missing_target_is_refused_by_name(self, dialect):
        assert (
            _feature(
                ClickHouseMovePartitionStatement(
                    dialect, TABLE, PARTITION_ID, "DISK", ""
                )
            )
            == "MOVE PARTITION"
        )

    @pytest.mark.parametrize("destination", ["DISK", "VOLUME", "TABLE"])
    def test_the_backend_helper_executes_the_rendered_statement(
        self, service, destination
    ):
        backend = service.backend
        target = "archive" if destination == "TABLE" else "cold"

        service.move(TABLE, PARTITION_ID, destination, target)

        expected_target = f"`{target}`" if destination == "TABLE" else f"'{target}'"
        assert backend.calls == [
            (
                f"ALTER TABLE `{TABLE}` MOVE PARTITION ID '{PARTITION_ID}' "
                f"TO {destination} {expected_target}",
                (),
            )
        ]


# --------------------------------------------------------------------------- #
# FREEZE / UNFREEZE
# --------------------------------------------------------------------------- #


class TestFreezePartition:
    def test_partition_and_name_are_both_optional(self, dialect):
        sql, params = _render(ClickHouseFreezePartitionStatement(dialect, TABLE))

        assert sql == f"ALTER TABLE `{TABLE}` FREEZE"
        assert params == ()

    def test_partition_without_name(self, dialect):
        sql, _params = _render(
            ClickHouseFreezePartitionStatement(dialect, TABLE, PARTITION_ID)
        )

        assert sql == (
            f"ALTER TABLE `{TABLE}` FREEZE PARTITION ID '{PARTITION_ID}'"
        )

    def test_name_without_partition(self, dialect):
        sql, _params = _render(
            ClickHouseFreezePartitionStatement(dialect, TABLE, name="backup_1")
        )

        assert sql == f"ALTER TABLE `{TABLE}` FREEZE WITH NAME 'backup_1'"

    def test_both_clauses(self, dialect):
        sql, _params = _render(
            ClickHouseFreezePartitionStatement(
                dialect, TABLE, PARTITION_ID, "backup_1"
            )
        )

        assert sql == (
            f"ALTER TABLE `{TABLE}` FREEZE PARTITION ID '{PARTITION_ID}' "
            "WITH NAME 'backup_1'"
        )

    def test_a_blank_partition_is_refused_not_treated_as_absent(self, dialect):
        assert (
            _feature(
                ClickHouseFreezePartitionStatement(dialect, TABLE, "   ")
            )
            == "FREEZE PARTITION"
        )

    def test_the_backend_helper_executes_the_rendered_statement(self, service):
        service.freeze(TABLE, PARTITION_ID, name="backup_1")

        assert service.backend.calls == [
            (
                f"ALTER TABLE `{TABLE}` FREEZE PARTITION ID '{PARTITION_ID}' "
                "WITH NAME 'backup_1'",
                (),
            )
        ]


class TestUnfreezePartition:
    def test_with_name_is_required_and_rendered_after_the_partition(self, dialect):
        sql, params = _render(
            ClickHouseUnfreezePartitionStatement(
                dialect, TABLE, PARTITION_ID, "backup_1"
            )
        )

        assert sql == (
            f"ALTER TABLE `{TABLE}` UNFREEZE PARTITION ID '{PARTITION_ID}' "
            "WITH NAME 'backup_1'"
        )
        assert params == ()

    def test_partition_stays_optional(self, dialect):
        sql, _params = _render(
            ClickHouseUnfreezePartitionStatement(dialect, TABLE, name="backup_1")
        )

        assert sql == f"ALTER TABLE `{TABLE}` UNFREEZE WITH NAME 'backup_1'"

    @pytest.mark.parametrize("name", [None, "", "   "])
    def test_a_missing_name_is_refused_by_name(self, dialect, name):
        """The reference gives ``WITH NAME`` no brackets, so there is no fallback."""
        assert (
            _feature(
                ClickHouseUnfreezePartitionStatement(
                    dialect, TABLE, PARTITION_ID, name
                )
            )
            == "UNFREEZE PARTITION WITH NAME"
        )

    def test_the_backend_helper_executes_the_rendered_statement(self, service):
        service.unfreeze(TABLE, "backup_1", PARTITION_ID)

        assert service.backend.calls == [
            (
                f"ALTER TABLE `{TABLE}` UNFREEZE PARTITION ID '{PARTITION_ID}' "
                "WITH NAME 'backup_1'",
                (),
            )
        ]


# --------------------------------------------------------------------------- #
# CLEAR COLUMN | INDEX | PROJECTION ... IN PARTITION
# --------------------------------------------------------------------------- #


class TestClearInPartition:
    @pytest.mark.parametrize(
        "kind, name",
        [("COLUMN", "browser"), ("INDEX", "idx_browser"), ("column", "browser")],
    )
    def test_column_and_index_require_a_partition(self, dialect, kind, name):
        sql, params = _render(
            ClickHouseClearInPartitionStatement(
                dialect, TABLE, kind, name, PARTITION_ID
            )
        )

        assert sql == (
            f"ALTER TABLE `{TABLE}` CLEAR {kind.upper()} `{name}` "
            f"IN PARTITION ID '{PARTITION_ID}'"
        )
        assert params == ()

    def test_projection_partition_is_optional(self, dialect):
        sql, _params = _render(
            ClickHouseClearInPartitionStatement(
                dialect, TABLE, "PROJECTION", "proj_user"
            )
        )

        assert sql == f"ALTER TABLE `{TABLE}` CLEAR PROJECTION `proj_user`"

    def test_projection_with_partition(self, dialect):
        sql, _params = _render(
            ClickHouseClearInPartitionStatement(
                dialect, TABLE, "projection", "proj_user", PARTITION_ID
            )
        )

        assert sql == (
            f"ALTER TABLE `{TABLE}` CLEAR PROJECTION `proj_user` "
            f"IN PARTITION ID '{PARTITION_ID}'"
        )

    @pytest.mark.parametrize("kind", ["COLUMN", "INDEX"])
    def test_column_and_index_without_a_partition_are_refused_by_name(
        self, dialect, kind
    ):
        """The reference spells ``IN PARTITION`` without brackets for both."""
        assert (
            _feature(
                ClickHouseClearInPartitionStatement(dialect, TABLE, kind, "x", None)
            )
            == f"CLEAR {kind} IN PARTITION"
        )

    def test_an_unknown_kind_is_refused_by_name(self, dialect):
        assert (
            _feature(
                ClickHouseClearInPartitionStatement(
                    dialect, TABLE, "TABLE", "x", PARTITION_ID
                )
            )
            == "CLEAR TABLE IN PARTITION"
        )

    def test_a_missing_object_name_is_refused_by_name(self, dialect):
        assert (
            _feature(
                ClickHouseClearInPartitionStatement(
                    dialect, TABLE, "COLUMN", "", PARTITION_ID
                )
            )
            == "CLEAR COLUMN IN PARTITION"
        )

    @pytest.mark.parametrize(
        "kind, name, partition",
        [
            ("COLUMN", "browser", PARTITION_ID),
            ("INDEX", "idx_browser", PARTITION_ID),
            ("PROJECTION", "proj_user", None),
        ],
    )
    def test_the_backend_helper_executes_the_rendered_statement(
        self, service, kind, name, partition
    ):
        service.clear(TABLE, kind, name, partition)

        tail = f" IN PARTITION ID '{partition}'" if partition else ""
        assert service.backend.calls == [
            (
                f"ALTER TABLE `{TABLE}` CLEAR {kind} `{name}`{tail}",
                (),
            )
        ]


# --------------------------------------------------------------------------- #
# OPTIMIZE TABLE ... [PARTITION] FINAL
# --------------------------------------------------------------------------- #


class TestOptimizePartition:
    def test_partition_and_final(self, dialect):
        sql, params = _render(
            ClickHouseOptimizePartitionStatement(dialect, TABLE, PARTITION_ID, True)
        )

        assert sql == f"OPTIMIZE TABLE `{TABLE}` PARTITION ID '{PARTITION_ID}' FINAL"
        assert params == ()

    def test_table_wide_final(self, dialect):
        sql, _params = _render(
            ClickHouseOptimizePartitionStatement(dialect, TABLE)
        )

        assert sql == f"OPTIMIZE TABLE `{TABLE}` FINAL"

    def test_plain_form_is_valid_without_final(self, dialect):
        sql, _params = _render(
            ClickHouseOptimizePartitionStatement(dialect, TABLE, PARTITION_ID, False)
        )

        assert sql == f"OPTIMIZE TABLE `{TABLE}` PARTITION ID '{PARTITION_ID}'"

    def test_a_non_bool_final_is_refused(self, dialect):
        """``"no"`` would truthiness-render as ``FINAL``; refusing is the only honest answer."""
        assert (
            _feature(
                ClickHouseOptimizePartitionStatement(dialect, TABLE, None, "no")
            )
            == "OPTIMIZE TABLE ... FINAL"
        )

    def test_the_backend_helper_executes_the_rendered_statement(self, service):
        service.optimize(TABLE, PARTITION_ID)

        assert service.backend.calls == [
            (
                f"OPTIMIZE TABLE `{TABLE}` PARTITION ID '{PARTITION_ID}' FINAL",
                (),
            )
        ]

    def test_the_backend_helper_can_render_the_plain_form(self, service):
        service.optimize(TABLE, final=False)

        assert service.backend.calls == [(f"OPTIMIZE TABLE `{TABLE}`", ())]


# --------------------------------------------------------------------------- #
# Capability probes
# --------------------------------------------------------------------------- #


class TestCapabilityProbes:
    @pytest.mark.parametrize(
        "probe",
        [
            "supports_replace_partition",
            "supports_move_partition",
            "supports_freeze_partition",
            "supports_unfreeze_partition",
            "supports_clear_in_partition",
            "supports_optimize_partition_final",
        ],
    )
    def test_each_operation_answers_true(self, dialect, probe):
        answer = getattr(dialect, probe)()

        assert isinstance(answer, bool)
        assert answer is True

    def test_the_mysql_optimize_probe_stays_absent(self, dialect):
        """``supports_optimize_partition`` names MySQL's statement; it is not this one."""
        assert not hasattr(dialect, "supports_optimize_partition")
