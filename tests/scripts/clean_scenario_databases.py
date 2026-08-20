# tests/scripts/clean_scenario_databases.py
"""Manually drop pooled test databases on the configured ClickHouse servers.

The test-suite database pool keeps ``{database}_{index}`` databases on each
scenario's server across sessions (they are reused, never auto-removed). This
script drops those pooled databases so the servers can be reset to a clean
state.

It reuses the same scenario resolution as the test providers (env var
``CLICKHOUSE_SCENARIOS_CONFIG_PATH`` or ``tests/config/clickhouse_scenarios.yaml``, plus
the ``CLICKHOUSE_ACTIVE_SCENARIOS`` / ``TESTSUITE_ACTIVE_SCENARIOS`` filter) and the
same naming convention (pool prefix derived from the yaml ``database`` field),
so what it drops matches exactly what the pool creates.

The scenario's shared ``database`` itself (e.g. ``test_db``) is kept unless
``--include-base`` is given.

Usage:
    .venv3.14-ubuntu26.04/bin/python tests/scripts/clean_scenario_databases.py --dry-run
    .venv3.14-ubuntu26.04/bin/python tests/scripts/clean_scenario_databases.py --yes
    CLICKHOUSE_ACTIVE_SCENARIOS=clickhouse_80 .venv3.14-ubuntu26.04/bin/python \
        tests/scripts/clean_scenario_databases.py --yes
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import clickhouse.connector  # noqa: E402

from rhosocial.activerecord.testsuite.core.pool import base_database  # noqa: E402

from providers import pooling  # noqa: E402,F401  (registers pool base names)
from providers.scenarios import SCENARIO_MAP, get_scenario_raw  # noqa: E402


def _escape_identifier(name: str) -> str:
    """Escape a ClickHouse database identifier for use inside backticks."""
    return name.replace("`", "``")


def _pooled_databases(base: str) -> re.Pattern:
    """Match the pooled database names derived from a base name."""
    return re.compile(rf"^{re.escape(base)}_\d+$")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Drop pooled test databases on the configured ClickHouse servers."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print which databases would be dropped; do not connect.",
    )
    parser.add_argument(
        "--include-base",
        action="store_true",
        help="Also drop each scenario's shared configured database (e.g. test_db).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    args = parser.parse_args()

    scenarios = list(SCENARIO_MAP.keys())
    if not scenarios:
        print("No scenarios registered (check scenario filter / config file).")
        return 1

    print(f"Scenarios: {scenarios}")
    plan = []
    for name in scenarios:
        _, config = get_scenario_raw(name)
        base = base_database(name)
        print(
            f"  {name}: server {config.host}:{config.port}, "
            f"base database {base!r}, pooled prefix {base}_{{index}}"
        )
        plan.append((name, config, base))

    if args.dry_run:
        print("\nDry run: nothing was dropped.")
        return 0

    if not args.yes:
        answer = input("Drop the pooled databases listed above? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 0

    total = 0
    for name, config, base in plan:
        dropped = _clean_server(config, base, args.include_base)
        total += len(dropped)
        for db in dropped:
            print(f"  dropped {name} {config.host}:{config.port} `{db}`")

    print(f"\nDone. Dropped {total} database(s).")
    return 0


def _clean_server(config, base: str, include_base: bool) -> list:
    """Drop the pooled databases on one scenario's server; return dropped names."""
    conn = clickhouse.connector.connect(
        host=config.host,
        port=config.port,
        user=config.username,
        password=config.password,
        connection_timeout=10,
        charset=config.charset or "utf8mb4",
        ssl_disabled=config.ssl_disabled,
    )
    dropped = []
    pooled = _pooled_databases(base)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("SHOW DATABASES")
            for (db,) in cursor.fetchall():
                matches = pooled.match(db) or (include_base and db == base)
                if matches:
                    cursor.execute(f"DROP DATABASE IF EXISTS `{_escape_identifier(db)}`")
                    dropped.append(db)
        finally:
            cursor.close()
    finally:
        conn.close()
    return dropped


if __name__ == "__main__":
    sys.exit(main())