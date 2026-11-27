# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/ddl/test_partition_action_vocabulary.py
"""Every partition action is declared, with the engine's own answers.

ClickHouse renders a statement for DROP / ATTACH / DETACH / MOVE PARTITION and
refuses the rest: partitions appear from inserts, ``PARTITION BY`` is fixed at
CREATE, and MySQL's maintenance vocabulary (REORGANIZE / COALESCE / ANALYZE /
CHECK / OPTIMIZE / REBUILD / REPAIR) is a different engine's grammar. The names
the engine does not have are still declared and answer False, so a caller can
enumerate the family and get one definite answer per name.
"""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

PARTITION_ACTIONS = {
    "supports_add_partition": False,
    "supports_drop_partition": True,
    "supports_truncate_partition": False,
    "supports_attach_partition": True,
    "supports_detach_partition": True,
    "supports_split_partition": False,
    "supports_merge_partition": False,
    "supports_exchange_partition": False,
    "supports_reorganize_partition": False,
    "supports_coalesce_partition": False,
    "supports_move_partition": True,
    "supports_analyze_partition": False,
    "supports_check_partition": False,
    "supports_optimize_partition": False,
    "supports_rebuild_partition": False,
    "supports_repair_partition": False,
    "supports_remove_partitioning": False,
}


@pytest.fixture()
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


@pytest.mark.parametrize("name,expected", sorted(PARTITION_ACTIONS.items()))
def test_every_action_is_declared_with_the_engines_answer(dialect, name, expected):
    switch = getattr(dialect, name, None)
    assert callable(switch), f"{name} is missing from the partition vocabulary"
    assert switch() is expected, f"{name} answered {not expected}"


def test_the_vocabulary_is_the_whole_action_family():
    """Guards against a short list passing by accident."""
    assert len(PARTITION_ACTIONS) == 17
