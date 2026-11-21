# docs/examples/ar-migration/02_partition_lifecycle.py
"""Offline example: ClickHouse partition lifecycle after the table exists.

ClickHouse has no ``ADD PARTITION`` -- a partition appears automatically the
first time a row lands in it, so ``suggest_partition_add`` answers ``None``
("no action"). Maintenance is by the server-assigned partition id exposed in
``system.parts.partition_id``: ``DROP PARTITION ID`` for a single id, and a
chain of those for retention. There is no ``REORGANIZE``/``COALESCE`` verb, so
split and merge are explicitly unsupported (``False``); removing partitioning
means dropping the whole table.

Everything is rendered offline via ``expr.to_sql()`` -- no connection, no
``ctx.apply()``.
"""

from rhosocial.activerecord.backend.expression.statements import PartitionStrategy
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
    strategy = PartitionStrategy.RANGE

    print("== table drop: ClickHouse has no REMOVE PARTITIONING ==")
    show("table_drop", dialect.suggest_partition_table_drop(strategy, {"table": "visits"}))

    print("\n== add: a partition appears with its first row, so no ADD ==")
    show("add", dialect.suggest_partition_add(strategy, {"table": "visits"}))

    print("\n== drop one partition by server-assigned id ==")
    show(
        "drop",
        dialect.suggest_partition_drop(strategy, {"table": "visits", "partition_id": "202601"}),
    )

    print("\n== retention: drop an explicit list of ids, in order ==")
    show(
        "retention",
        dialect.suggest_partition_retention(
            strategy, {"table": "visits", "partition_ids": ["202601", "202602"]}
        ),
    )

    print("\n== retention with no explicit ids is conservative (None) ==")
    show(
        "retention(without ids)", dialect.suggest_partition_retention(strategy, {"table": "visits"})
    )

    print("\n== split / merge / table_alter are unavailable ==")
    show("table_alter", dialect.suggest_partition_table_alter(strategy, {"table": "visits"}))
    show("split", dialect.suggest_partition_split(strategy, {"table": "visits"}))
    show("merge", dialect.suggest_partition_merge(strategy, {"table": "visits"}))


if __name__ == "__main__":
    main()
