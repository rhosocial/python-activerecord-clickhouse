# docs/examples/ar-migration/01_partition_build.py
"""Offline example: declaring a partitioned table on ClickHouse.

ClickHouse has no declarative partition *strategy* to choose from. A partition is
declared inline on ``CREATE TABLE`` as a ``PARTITION BY <expr>`` storage clause,
so this example passes a real ``Column`` expression in the plan and renders the
clause via ``expr.to_sql()``. No connection and no ``ctx.apply()`` are involved:
the suggestion layer only answers the "how" question with expression nodes.

Run with (from the repository root)::

    PYTHONPATH=src python docs/examples/ar-migration/01_partition_build.py
"""

from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.statements import PartitionByRangeClause
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


def show(label, suggestion):
    """Render a tri-state suggestion: expression nodes, False, or None."""
    operations = suggestion.operations
    if operations is False:
        print(f"  {label}: False (no mechanism)")
    elif operations is None:
        print(f"  {label}: None (no action needed)")
    else:
        for expr in operations:
            print(f"  {label}: {expr.to_sql()[0]}")


def main():
    dialect = ClickHouseDialect()
    # The strategy is ignored by ClickHouse -- the expression is what matters.
    strategy = PartitionByRangeClause(dialect, [Column(dialect, "created_at")])

    print("== build: PARTITION BY <expr> ==")
    key = Column(dialect, "created_at")
    plan = {"expressions": [key]}
    show("build", dialect.suggest_partition_build(strategy, plan))

    print("\n== a plan with no expression node is declined ==")
    show("build(empty)", dialect.suggest_partition_build(strategy, {}))


if __name__ == "__main__":
    main()
