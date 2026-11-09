# tests/rhosocial/activerecord_clickhouse_test/feature/backend/introspection/test_catalog_families.py
"""The server-wide catalogue families, without a server.

``system.functions``, ``system.dictionaries``, ``system.clusters``,
``system.quotas``, ``system.users`` and ``system.roles`` are not table-scoped
catalogues. This file pins the half that can be checked offline:

* the statement each family renders -- source, projection and order;
* the parameters a name filter binds;
* the parser's normalisation of ``UInt8`` flags, arrays and empty strings;
* the capability switches the CLI gate reads.

No database is involved; a dialect instance and a row-shaped stub are enough.
"""

import asyncio
from types import SimpleNamespace

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.introspection import (
    ClickHouseClusterListQuery,
    ClickHouseDictionaryListQuery,
    ClickHouseFunctionListQuery,
    ClickHouseQuotaListQuery,
    ClickHouseRoleListQuery,
    ClickHouseUserListQuery,
)
from rhosocial.activerecord.backend.impl.clickhouse.introspection.introspector import (
    AsyncClickHouseIntrospector,
    ClickHouseIntrospector,
)
from rhosocial.activerecord.backend.impl.clickhouse.introspection.types import (
    ClickHouseClusterInfo,
    ClickHouseDictionaryInfo,
    ClickHouseFunctionInfo,
    ClickHouseQuotaInfo,
    ClickHouseRoleInfo,
    ClickHouseUserInfo,
)


class _StubBackend:
    """The facts the parsers read from their backend, and nothing else."""

    def __init__(self, dialect, database="analytics"):
        self.dialect = dialect
        self.config = SimpleNamespace(database=database)

    def get_cached_server_version(self):
        return None


class _RowsExecutor:
    """A synchronous executor that returns the same rows and records calls."""

    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def execute(self, sql, params):
        self.statements.append((sql, params))
        return self.rows


class _AsyncRowsExecutor:
    """The asynchronous twin of :class:`_RowsExecutor`."""

    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    async def execute(self, sql, params):
        self.statements.append((sql, params))
        return self.rows


def _sync_introspector(dialect, rows):
    executor = _RowsExecutor(rows)
    introspector = ClickHouseIntrospector(_StubBackend(dialect), executor)
    return introspector, executor


def _async_introspector(dialect, rows):
    executor = _AsyncRowsExecutor(rows)
    introspector = AsyncClickHouseIntrospector(_StubBackend(dialect), executor)
    return introspector, executor


@pytest.fixture(scope="module")
def dialect():
    """The scenario server's version shape (26.7.3)."""
    return ClickHouseDialect(version=(26, 7, 3))


class TestTheStatementsAreTrees:
    """Each catalogue family renders one ``QueryStatement``, not SQL text."""

    def test_functions_read_system_functions_in_name_order(self, dialect):
        sql, params = ClickHouseFunctionListQuery(dialect).to_sql()
        assert "FROM `system`.`functions`" in sql
        assert "ORDER BY `name`" in sql
        for column in (
            "`name`",
            "`is_aggregate`",
            "`case_insensitive`",
            "`alias_to`",
            "`origin`",
            "`description`",
            "`syntax`",
            "`arguments`",
            "`categories`",
        ):
            assert column in sql
        assert params == ()

    def test_a_function_name_is_a_filter_not_a_key(self, dialect):
        sql, params = ClickHouseFunctionListQuery(dialect, "f").to_sql()
        assert "WHERE `name` = %s" in sql
        assert params == ("f",)

    def test_dictionaries_alias_the_dotted_catalogue_columns(self, dialect):
        sql, params = ClickHouseDictionaryListQuery(dialect).to_sql()
        assert "FROM `system`.`dictionaries`" in sql
        assert "`key.names` AS `key_names`" in sql
        assert "`key.types` AS `key_types`" in sql
        assert "`attribute.names` AS `attribute_names`" in sql
        assert "`attribute.types` AS `attribute_types`" in sql
        assert "ORDER BY `database`, `name`" in sql
        assert params == ()

    def test_a_dictionary_filter_names_the_name_then_the_database(self, dialect):
        sql, params = ClickHouseDictionaryListQuery(
            dialect, name="d1", database="app"
        ).to_sql()
        assert "`name` = %s AND `database` = %s" in sql
        assert params == ("d1", "app")

    def test_a_dictionary_database_filter_can_stand_alone(self, dialect):
        sql, params = ClickHouseDictionaryListQuery(dialect, database="app").to_sql()
        assert "WHERE `database` = %s" in sql
        assert params == ("app",)

    def test_clusters_keep_the_engines_numbered_order(self, dialect):
        sql, params = ClickHouseClusterListQuery(dialect).to_sql()
        assert "FROM `system`.`clusters`" in sql
        assert "ORDER BY `cluster`, `shard_num`, `replica_num`" in sql
        assert params == ()

    def test_a_cluster_name_narrows_the_member_listing(self, dialect):
        sql, params = ClickHouseClusterListQuery(dialect, "c").to_sql()
        assert "WHERE `cluster` = %s" in sql
        assert params == ("c",)

    def test_quotas_read_system_quotas(self, dialect):
        sql, params = ClickHouseQuotaListQuery(dialect).to_sql()
        assert "FROM `system`.`quotas`" in sql
        assert "ORDER BY `name`" in sql
        assert params == ()

    def test_users_project_no_credential_parameters(self, dialect):
        sql, params = ClickHouseUserListQuery(dialect).to_sql()
        assert "FROM `system`.`users`" in sql
        assert "`auth_type`" in sql
        assert "auth_params" not in sql
        assert params == ()

    def test_roles_read_system_roles(self, dialect):
        sql, params = ClickHouseRoleListQuery(dialect).to_sql()
        assert "FROM `system`.`roles`" in sql
        assert "ORDER BY `name`" in sql
        assert params == ()


class TestTheCapabilitySwitches:
    """The six catalogue families are declared answerable."""

    @pytest.mark.parametrize(
        "switch",
        [
            "supports_function_introspection",
            "supports_dictionary_introspection",
            "supports_cluster_introspection",
            "supports_quota_introspection",
            "supports_user_introspection",
            "supports_role_introspection",
        ],
    )
    def test_the_dialect_declares_the_family(self, switch):
        assert getattr(ClickHouseDialect(), switch)() is True

    def test_foreign_keys_and_triggers_remain_absent(self):
        """No catalogue family is added for an object this engine does not have."""
        assert ClickHouseDialect().supports_foreign_key_introspection() is False
        assert ClickHouseDialect().supports_trigger_introspection() is False


class TestTheParsers:
    """Rows are normalised into stable records, without a connection."""

    def test_functions_report_flags_and_origin(self, dialect):
        introspector = ClickHouseIntrospector(_StubBackend(dialect), None)
        (function,) = introspector.parse_functions(
            [
                {
                    "name": "f",
                    "is_aggregate": 1,
                    "case_insensitive": 0,
                    "alias_to": "",
                    "origin": "SQLUserDefined",
                    "description": "",
                    "syntax": "f(x)",
                    "arguments": "x",
                    "categories": "",
                }
            ]
        )
        assert function.name == "f"
        assert function.is_aggregate is True
        assert function.case_insensitive is False
        assert function.alias_to is None
        assert function.origin == "SQLUserDefined"
        assert function.description is None
        assert function.syntax == "f(x)"
        assert function.arguments == "x"
        assert function.categories is None
        assert function.is_user_defined is True

    def test_a_system_function_is_not_user_defined(self):
        function = ClickHouseFunctionInfo(name="f", origin="System")
        assert function.is_user_defined is False

    def test_an_unknown_origin_is_not_a_user_defined_claim(self):
        function = ClickHouseFunctionInfo(name="f")
        assert function.is_user_defined is False

    def test_dictionaries_normalise_arrays_and_flags(self, dialect):
        introspector = ClickHouseIntrospector(_StubBackend(dialect), None)
        (dictionary,) = introspector.parse_dictionaries(
            [
                {
                    "name": "d",
                    "database": "app",
                    "uuid": "00000000-0000-0000-0000-000000000000",
                    "status": "LOADED",
                    "is_lazy": 0,
                    "origin": "config.xml",
                    "type": "Flat",
                    "key_names": ["id"],
                    "key_types": ["UInt64"],
                    "attribute_names": ["value"],
                    "attribute_types": ["String"],
                    "bytes_allocated": 100,
                    "element_count": 3,
                    "query_count": 0,
                    "hit_rate": None,
                    "found_rate": None,
                    "lifetime_min": 0,
                    "lifetime_max": 60,
                    "loading_start_time": None,
                    "last_successful_update_time": None,
                    "error_count": 0,
                    "last_exception": "",
                    "comment": "",
                }
            ]
        )
        assert dictionary.name == "d"
        assert dictionary.database == "app"
        assert dictionary.key_names == ["id"]
        assert dictionary.key_types == ["UInt64"]
        assert dictionary.attribute_names == ["value"]
        assert dictionary.is_lazy is False
        assert dictionary.hit_rate is None
        assert dictionary.last_exception is None
        assert dictionary.comment is None

    def test_a_configuration_dictionary_keeps_its_empty_database(self, dialect):
        introspector = ClickHouseIntrospector(_StubBackend(dialect), None)
        (dictionary,) = introspector.parse_dictionaries([{"name": "d"}])
        assert dictionary.database == ""

    def test_clusters_report_member_numbers_as_integers(self, dialect):
        introspector = ClickHouseIntrospector(_StubBackend(dialect), None)
        (cluster,) = introspector.parse_clusters(
            [
                {
                    "cluster": "c",
                    "shard_num": 1,
                    "replica_num": 2,
                    "shard_name": "shard_1",
                    "shard_weight": 1,
                    "internal_replication": 1,
                    "host_name": "host",
                    "host_address": "127.0.0.1",
                    "port": 9000,
                    "is_local": 1,
                    "user": "default",
                    "default_database": "",
                    "errors_count": 0,
                    "slowdowns_count": 0,
                    "estimated_recovery_time": 0,
                }
            ]
        )
        assert cluster.cluster == "c"
        assert cluster.shard_num == 1
        assert cluster.replica_num == 2
        assert cluster.internal_replication is True
        assert cluster.is_local is True
        assert cluster.port == 9000
        assert cluster.default_database is None

    def test_quotas_normalise_the_key_and_duration_arrays(self, dialect):
        introspector = ClickHouseIntrospector(_StubBackend(dialect), None)
        (quota,) = introspector.parse_quotas(
            [
                {
                    "name": "q",
                    "id": "00000000-0000-0000-0000-000000000000",
                    "storage": "disk",
                    "keys": ["user_name"],
                    "durations": ["60", 3600],
                    "apply_to_all": 0,
                    "apply_to_list": ["alice"],
                    "apply_to_except": [],
                    "ipv4_prefix_bits": None,
                    "ipv6_prefix_bits": None,
                }
            ]
        )
        assert quota.name == "q"
        assert quota.keys == ["user_name"]
        assert quota.durations == [60, 3600]
        assert quota.apply_to_all is False
        assert quota.apply_to_list == ["alice"]
        assert quota.ipv4_prefix_bits is None

    def test_users_report_authentication_types_not_credentials(self, dialect):
        introspector = ClickHouseIntrospector(_StubBackend(dialect), None)
        (user,) = introspector.parse_users(
            [
                {
                    "name": "alice",
                    "id": "00000000-0000-0000-0000-000000000000",
                    "storage": "disk",
                    "auth_type": ["sha256_password"],
                    "default_roles_all": 0,
                    "default_roles_list": ["reader"],
                    "default_roles_except": [],
                    "grantees_any": 0,
                    "grantees_list": [],
                    "grantees_except": [],
                    "default_database": "app",
                    "host_ip": ["127.0.0.1"],
                    "host_names": ["localhost"],
                    "host_names_regexp": [],
                    "host_names_like": [],
                }
            ]
        )
        assert user.name == "alice"
        assert user.auth_type == ["sha256_password"]
        assert user.default_roles_list == ["reader"]
        assert user.host_ip == ["127.0.0.1"]
        assert user.default_database == "app"

    def test_roles_are_the_three_catalogue_columns(self, dialect):
        introspector = ClickHouseIntrospector(_StubBackend(dialect), None)
        (role,) = introspector.parse_roles([{"name": "reader", "id": "x", "storage": ""}])
        assert role.name == "reader"
        assert role.id == "x"
        assert role.storage is None


class TestTheIntrospectorEntryPoints:
    """The methods ask one statement and hand the rows to one parser."""

    def test_list_functions_binds_the_name_and_parses_rows(self, dialect):
        introspector, executor = _sync_introspector(
            dialect,
            [{"name": "f", "is_aggregate": 0}],
        )
        functions = introspector.list_functions(name="f")
        assert executor.statements[-1][1] == ("f",)
        assert functions == [ClickHouseFunctionInfo(name="f")]

    def test_list_dictionaries_binds_name_and_database(self, dialect):
        introspector, executor = _sync_introspector(
            dialect,
            [{"name": "d", "database": "app"}],
        )
        dictionaries = introspector.list_dictionaries(name="d", database="app")
        assert executor.statements[-1][1] == ("d", "app")
        assert dictionaries == [ClickHouseDictionaryInfo(name="d", database="app")]

    def test_list_clusters_parses_member_rows(self, dialect):
        introspector, executor = _sync_introspector(
            dialect,
            [{"cluster": "c", "shard_num": 1, "replica_num": 1}],
        )
        clusters = introspector.list_clusters(name="c")
        assert executor.statements[-1][1] == ("c",)
        assert clusters == [ClickHouseClusterInfo(cluster="c", shard_num=1, replica_num=1)]

    def test_list_quotas_parses_rows(self, dialect):
        introspector, executor = _sync_introspector(dialect, [{"name": "q"}])
        quotas = introspector.list_quotas(name="q")
        assert executor.statements[-1][1] == ("q",)
        assert quotas == [ClickHouseQuotaInfo(name="q")]

    def test_list_users_parses_rows(self, dialect):
        introspector, executor = _sync_introspector(dialect, [{"name": "alice"}])
        users = introspector.list_users(name="alice")
        assert executor.statements[-1][1] == ("alice",)
        assert users == [ClickHouseUserInfo(name="alice")]

    def test_list_roles_parses_rows(self, dialect):
        introspector, executor = _sync_introspector(dialect, [{"name": "reader"}])
        roles = introspector.list_roles(name="reader")
        assert executor.statements[-1][1] == ("reader",)
        assert roles == [ClickHouseRoleInfo(name="reader")]

    def test_the_async_entry_points_ask_the_same_question(self, dialect):
        introspector, executor = _async_introspector(
            dialect,
            [{"name": "f", "is_aggregate": 1}],
        )

        functions = asyncio.run(introspector.list_functions(name="f"))
        assert executor.statements[-1][1] == ("f",)
        assert functions == [
            ClickHouseFunctionInfo(name="f", is_aggregate=True)
        ]
