# tests/test_partition_suggestion_contract.py
"""Contract for ClickHouse's eight partition-lifecycle backend suggestions.

ClickHouse declares partitioning inline as ``PARTITION BY <expr>`` and addresses
existing partitions by server-assigned id. This module checks that the dialect
satisfies all eight suggestion protocols, answers the tri-state honestly when
there is no usable plan, and emits *real* expression nodes (never SQL text) when
the plan does carry one. No live server is needed, so it runs under
``--noconftest`` when the root conftest lacks configuration.
"""

import pytest

from rhosocial.activerecord.backend.suggestion.protocols import (
    PartitionAddSuggestionSupport,
    PartitionBuildSuggestionSupport,
    PartitionDropSuggestionSupport,
    PartitionMergeSuggestionSupport,
    PartitionRetentionSuggestionSupport,
    PartitionSplitSuggestionSupport,
    PartitionTableAlterSuggestionSupport,
    PartitionTableDropSuggestionSupport,
)
from rhosocial.activerecord.backend.expression import Column, DropTableStatement
from rhosocial.activerecord.backend.expression.bases.bases import BaseExpression
from rhosocial.activerecord.backend.expression.statements import PartitionByRangeClause
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseDropPartitionStatement,
    ClickHouseStorageOptionKind,
    ClickHouseTableStorageOption,
)
from rhosocial.activerecord.backend.impl.clickhouse.suggestion import (
    ClickHousePartitionAddSuggestionMixin,
    ClickHousePartitionBuildSuggestionMixin,
    ClickHousePartitionDropSuggestionMixin,
    ClickHousePartitionMergeSuggestionMixin,
    ClickHousePartitionRetentionSuggestionMixin,
    ClickHousePartitionSplitSuggestionMixin,
    ClickHousePartitionTableAlterSuggestionMixin,
    ClickHousePartitionTableDropSuggestionMixin,
)


def _strategy(dialect):
    """A RANGE strategy expressed as an expression node (ClickHouse ignores it)."""
    return PartitionByRangeClause(dialect, [Column(dialect, "created_at")])


CASES = [
    ("build", PartitionBuildSuggestionSupport, "suggest_partition_build"),
    ("table_drop", PartitionTableDropSuggestionSupport, "suggest_partition_table_drop"),
    ("table_alter", PartitionTableAlterSuggestionSupport, "suggest_partition_table_alter"),
    ("add", PartitionAddSuggestionSupport, "suggest_partition_add"),
    ("drop", PartitionDropSuggestionSupport, "suggest_partition_drop"),
    ("split", PartitionSplitSuggestionSupport, "suggest_partition_split"),
    ("merge", PartitionMergeSuggestionSupport, "suggest_partition_merge"),
    ("retention", PartitionRetentionSuggestionSupport, "suggest_partition_retention"),
]

# Honest answer with no plan at all: a real-chain point declines (False), ADD is
# a genuine no-op (None), and retention has no explicit id set to act on (None).
NO_PLAN_EXPECTED = {
    "build": False,
    "table_drop": False,
    "table_alter": False,
    "add": None,
    "drop": False,
    "split": False,
    "merge": False,
    "retention": None,
}


@pytest.fixture
def dialect():
    return ClickHouseDialect()


PARTITION_SUGGESTION_MIXINS = [
    ClickHousePartitionBuildSuggestionMixin,
    ClickHousePartitionTableDropSuggestionMixin,
    ClickHousePartitionTableAlterSuggestionMixin,
    ClickHousePartitionAddSuggestionMixin,
    ClickHousePartitionDropSuggestionMixin,
    ClickHousePartitionSplitSuggestionMixin,
    ClickHousePartitionMergeSuggestionMixin,
    ClickHousePartitionRetentionSuggestionMixin,
]


def test_dialect_carries_the_mixins():
    for mixin in PARTITION_SUGGESTION_MIXINS:
        assert issubclass(ClickHouseDialect, mixin), mixin.__name__


def test_dialect_satisfies_all_eight_protocols(dialect):
    for _name, protocol, _method in CASES:
        assert isinstance(dialect, protocol), protocol.__name__


TRISTATE_CASES = [(name, method) for name, _protocol, method in CASES]


@pytest.mark.parametrize("name,method", TRISTATE_CASES, ids=[c[0] for c in CASES])
def test_no_plan_tristate(dialect, name, method):
    suggestion = getattr(dialect, method)(_strategy(dialect), None)
    assert suggestion.operations is NO_PLAN_EXPECTED[name]


def test_build_returns_real_partition_by_storage_option(dialect):
    key = Column(dialect, "created_at")
    suggestion = dialect.suggest_partition_build(_strategy(dialect), {"expressions": [key]})
    operations = suggestion.operations
    assert isinstance(operations, tuple) and len(operations) == 1
    clause = operations[0]
    assert isinstance(clause, ClickHouseTableStorageOption)
    assert isinstance(clause, BaseExpression)
    assert clause.option is ClickHouseStorageOptionKind.PARTITION_BY
    assert clause.value == (key,)


def test_build_declines_a_plan_without_expression_nodes(dialect):
    assert dialect.suggest_partition_build(_strategy(dialect), {}).operations is False
    bad = {"expressions": ["toYYYYMM(created_at)"]}  # SQL text is not an expression node
    assert dialect.suggest_partition_build(_strategy(dialect), bad).operations is False


def test_table_drop_returns_real_drop_table_statement(dialect):
    suggestion = dialect.suggest_partition_table_drop(_strategy(dialect), {"table": "visits"})
    operations = suggestion.operations
    assert isinstance(operations, tuple) and len(operations) == 1
    drop = operations[0]
    assert isinstance(drop, DropTableStatement)
    assert isinstance(drop, BaseExpression)
    assert drop.table.name == "visits"


def test_drop_returns_real_partition_id_statement(dialect):
    suggestion = dialect.suggest_partition_drop(
        _strategy(dialect), {"table": "visits", "partition_id": "202601"}
    )
    operations = suggestion.operations
    assert isinstance(operations, tuple) and len(operations) == 1
    drop = operations[0]
    assert isinstance(drop, ClickHouseDropPartitionStatement)
    assert isinstance(drop, BaseExpression)
    assert drop.table == "visits"
    assert drop.partition_id == "202601"


def test_drop_declines_a_plan_without_a_partition_id(dialect):
    suggestion = dialect.suggest_partition_drop(_strategy(dialect), {"table": "visits"})
    assert suggestion.operations is False


def test_retention_returns_ordered_drop_chain_for_explicit_ids(dialect):
    plan = {"table": "visits", "partition_ids": ["202601", "202602"]}
    suggestion = dialect.suggest_partition_retention(_strategy(dialect), plan)
    operations = suggestion.operations
    assert isinstance(operations, tuple) and len(operations) == 2
    assert all(isinstance(op, ClickHouseDropPartitionStatement) for op in operations)
    assert [op.partition_id for op in operations] == ["202601", "202602"]


def test_retention_is_conservative_without_explicit_ids(dialect):
    assert (
        dialect.suggest_partition_retention(_strategy(dialect), {"table": "visits"}).operations
        is None
    )
    assert (
        dialect.suggest_partition_retention(
            _strategy(dialect), {"partition_ids": ["202601"]}
        ).operations
        is False
    )
