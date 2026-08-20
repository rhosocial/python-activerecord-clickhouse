# tests/providers/pooling.py
"""Database pooling helpers for the ClickHouse test providers.

Under parallel (pytest-xdist) runs with a positive pool size the testsuite
prepares ``{database}_0`` .. ``{database}_{N-1}`` databases per scenario on the
scenario's ClickHouse server (N = pool size = worker count), clearing any leftover
tables. Each test then takes any free slot and uses it exclusively until it
finishes, so concurrent workers never share a schema. The pool name prefix is
derived from the scenario's configured ``database`` (the YAML ``database``
field), so e.g. ``database: test_db`` produces ``test_db_0``, ``test_db_1``, ...
Serial runs (no ``-n``) keep the previous behaviour: the provider connects to
the scenario's configured ``database``.

The scenario name selects the server (host/port); the pool index selects the
database name. The two are deliberately unrelated.
"""

import clickhouse.connector

from typing import Dict, Optional, Tuple

from rhosocial.activerecord.testsuite.core.pool import (
    pooled_database_name,
    register_base_database,
    register_pool_reset_handler,
)

from .scenarios import SCENARIO_MAP, get_scenario_raw

# Derive each scenario's pooled-database base name from its configured
# ``database`` (YAML ``database`` field). Registered at import time so any
# caller of pooled_database_name() / resolve_database_name() resolves names
# consistent with the scenario configuration.
for _scenario_name, _scenario_config in SCENARIO_MAP.items():
    register_base_database(_scenario_name, _scenario_config["database"])


def resolve_database_name(scenario_name: str):
    """
    Return the pooled database name (e.g. ``test_db_3``) used by a test for
    the given scenario, or ``None`` when pooling is inactive (callers then fall
    back to the scenario's configured database).
    """
    return pooled_database_name(scenario_name)


class _VersionProfile:
    """Collation/DDL provider for one ClickHouse server version family.

    Supplies the charset collation and the CREATE / ALTER / DROP database SQL
    expressions used to prepare and clear a pooled database. Profiles are
    selected by the detected server version, so collations and expressions
    that only exist on newer servers (e.g. ``utf8mb4_0900_ai_ci``, introduced
    in ClickHouse 8.0) are never sent to older ones.
    """

    def __init__(self, min_version: Tuple[int, ...], collations: Dict[str, str]):
        self._min_version = min_version
        self._collations = collations

    @property
    def min_version(self) -> Tuple[int, ...]:
        return self._min_version

    def collation(self, charset: str) -> Optional[str]:
        return self._collations.get(charset)

    def create_database_sql(self, db_name: str, charset: str) -> str:
        collate = self.collation(charset)
        suffix = f" COLLATE {collate}" if collate else ""
        return f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET {charset}{suffix}"

    def alter_database_sql(self, db_name: str, charset: str) -> str:
        collate = self.collation(charset)
        suffix = f" COLLATE {collate}" if collate else ""
        return f"ALTER DATABASE `{db_name}` CHARACTER SET {charset}{suffix}"

    def drop_database_sql(self, db_name: str) -> str:
        return f"DROP DATABASE IF EXISTS `{db_name}`"


# Ordered newest-first; the first profile whose ``min_version`` the server
# satisfies is used, falling back to the oldest profile below.
_POOL_PROFILES = [
    _VersionProfile((8, 0, 0), {"utf8mb4": "utf8mb4_0900_ai_ci"}),
    _VersionProfile((5, 7, 0), {"utf8mb4": "utf8mb4_unicode_ci"}),
]
_DEFAULT_PROFILE = _POOL_PROFILES[-1]


def _version_tuple(version_string: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in version_string.split(".")[:3])


def _profile_for(server_version: str) -> _VersionProfile:
    server_version_tuple = _version_tuple(server_version)
    for profile in _POOL_PROFILES:
        if server_version_tuple >= profile.min_version:
            return profile
    return _DEFAULT_PROFILE


def _prepare_clickhouse_database(scenario_name: str, db_name: str) -> None:
    """Create (if missing) and clear a pooled database on the scenario's server.

    Connects to the server selected by ``scenario_name``, creates the pooled
    ``db_name`` database if missing, and drops every leftover table so the slot
    starts empty. The charset collation and the DDL expressions are taken from
    the version profile matching the server, so e.g. ``utf8mb4_0900_ai_ci`` is
    only used on ClickHouse 8.0+ and ``utf8mb4_unicode_ci`` on older servers. Called
    once per slot at session start by the master. Tests then own the slot: they
    set up and tear down their own schema. Errors are swallowed: a failed
    preparation must not hide the underlying test failure.
    """
    if scenario_name not in SCENARIO_MAP:
        return
    _, config = get_scenario_raw(scenario_name)
    try:
        conn_kwargs = {
            "host": config.host,
            "port": config.port,
            "user": config.username,
            "password": config.password,
            "connection_timeout": 10,
            "charset": config.charset or "utf8mb4",
        }
        if config.ssl_disabled is not None:
            conn_kwargs["ssl_disabled"] = config.ssl_disabled
        conn = clickhouse.connector.connect(**conn_kwargs)
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT VERSION()")
                profile = _profile_for(cursor.fetchone()[0])
                charset = config.charset or "utf8mb4"
                cursor.execute(profile.create_database_sql(db_name, charset))
                cursor.execute(profile.alter_database_sql(db_name, charset))
                cursor.execute(f"USE `{db_name}`")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
                    (db_name,),
                )
                for (table,) in cursor.fetchall():
                    cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
                conn.commit()
            finally:
                cursor.close()
        finally:
            conn.close()
    except Exception:
        pass


# ClickHouse tests are self-contained: each test creates its own tables and drops
# them in cleanup, so the pool only prepares (creates + clears) the slot
# databases once at session start. Per-acquire clearing is disabled to avoid a
# DROP-all-tables pass on every test (significant on slower CI interpreters).
register_pool_reset_handler(_prepare_clickhouse_database, clear_on_acquire=False)