# tests/providers/pooling.py
"""Database pooling helpers for the ClickHouse test providers.

Under parallel (pytest-xdist) runs with a positive pool size the testsuite
prepares ``{database}_0`` .. ``{database}_{N-1}`` databases per scenario on the
scenario's ClickHouse server (N = pool size = worker count), clearing any leftover
tables. Each test then takes any free slot and uses it exclusively until it
finishes, so concurrent workers never share a schema.

NOTE: This is a simplified version for rhosocial-activerecord-clickhouse.
The original MySQL-specific pooling logic is not used.
"""

from typing import Optional


def resolve_database_name(scenario_name: str) -> Optional[str]:
    """
    Return the pooled database name, or None when pooling is inactive.
    ClickHouse tests use the configured database name directly.
    """
    return None