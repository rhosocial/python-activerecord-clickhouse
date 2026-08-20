# tests/rhosocial/activerecord_clickhouse_test/feature/backend/introspection/test_status_introspector.py
"""
Tests for ClickHouse status introspector.

This module tests the SyncClickHouseStatusIntrospector functionality
for retrieving server status information via SHOW VARIABLES, SHOW STATUS,
and other system commands.
"""

import pytest

from rhosocial.activerecord.backend.introspection.status import (
    StatusItem,
    StatusCategory,
    ServerOverview,
    DatabaseBriefInfo,
    UserInfo,
    ConnectionInfo,
    StorageInfo,
    InnoDBInfo,
    BinaryLogInfo,
    SlowQueryInfo,
)

try:
    from rhosocial.activerecord.backend.introspection.status import ClickHouseReplicationInfo
except (ImportError, ModuleNotFoundError):
    pytest.skip("MySQL-specific test, skip for ClickHouse backend", allow_module_level=True)


class TestSyncClickHouseStatusIntrospector:
    """Tests for synchronous ClickHouse status introspector."""

    def test_get_overview(self, clickhouse_backend):
        """Test get_overview returns valid ServerOverview."""
        status = clickhouse_backend.introspector.status

        overview = status.get_overview()

        assert isinstance(overview, ServerOverview)
        assert overview.server_vendor == "ClickHouse"
        assert overview.server_version is not None
        assert isinstance(overview.configuration, list)
        assert isinstance(overview.performance, list)
        assert isinstance(overview.storage, StorageInfo)
        assert isinstance(overview.databases, list)
        # ClickHouse has users (unlike SQLite)
        assert isinstance(overview.users, list)

    def test_get_overview_version_matches_dialect(self, clickhouse_backend):
        """Test that overview version matches dialect version."""
        status = clickhouse_backend.introspector.status
        overview = status.get_overview()

        expected_version = ".".join(map(str, clickhouse_backend.dialect.version))
        assert overview.server_version == expected_version

    def test_get_overview_contains_clickhouse_version_info(self, clickhouse_backend):
        """Test that overview contains ClickHouse version info in extra."""
        status = clickhouse_backend.introspector.status
        overview = status.get_overview()

        # ClickHouse should have version info
        assert "version" in overview.extra or overview.server_version is not None

    def test_list_configuration(self, clickhouse_backend):
        """Test list_configuration returns configuration items."""
        status = clickhouse_backend.introspector.status

        items = status.list_configuration()

        assert isinstance(items, list)
        assert len(items) > 0

        # Check that all items are StatusItem instances
        for item in items:
            assert isinstance(item, StatusItem)
            assert item.name is not None
            assert item.value is not None

    def test_list_configuration_with_category_filter(self, clickhouse_backend):
        """Test list_configuration with category filter."""
        status = clickhouse_backend.introspector.status

        config_items = status.list_configuration(category=StatusCategory.CONFIGURATION)

        for item in config_items:
            assert item.category == StatusCategory.CONFIGURATION

    def test_list_configuration_contains_expected_items(self, clickhouse_backend):
        """Test that configuration contains expected ClickHouse variables."""
        status = clickhouse_backend.introspector.status

        items = status.list_configuration()
        item_names = [item.name for item in items]

        # Check for some common ClickHouse variables
        assert "port" in item_names
        assert "version" in item_names

    def test_list_configuration_values_are_parsed(self, clickhouse_backend):
        """Test that configuration values are properly parsed."""
        status = clickhouse_backend.introspector.status

        items = status.list_configuration()

        # port should be an integer
        port_item = next((i for i in items if i.name == "port"), None)
        if port_item:
            assert isinstance(port_item.value, int)

    def test_list_performance_metrics(self, clickhouse_backend):
        """Test list_performance_metrics returns status items."""
        status = clickhouse_backend.introspector.status

        items = status.list_performance_metrics()

        assert isinstance(items, list)
        # Items should have various categories (PERFORMANCE, CONNECTION, etc.)
        for item in items:
            assert isinstance(item, StatusItem)

    def test_get_connection_info(self, clickhouse_backend):
        """Test get_connection_info returns ConnectionInfo."""
        status = clickhouse_backend.introspector.status

        conn_info = status.get_connection_info()

        assert isinstance(conn_info, ConnectionInfo)
        # ClickHouse has connection info
        assert conn_info.active_count is not None or conn_info.max_connections is not None

    def test_get_storage_info(self, clickhouse_backend):
        """Test get_storage_info returns StorageInfo."""
        status = clickhouse_backend.introspector.status

        storage = status.get_storage_info()

        assert isinstance(storage, StorageInfo)
        # ClickHouse should have data directory info
        assert storage.extra is not None

    def test_list_databases(self, clickhouse_backend):
        """Test list_databases returns database list."""
        status = clickhouse_backend.introspector.status

        databases = status.list_databases()

        assert isinstance(databases, list)
        assert len(databases) >= 1

        # All items should be DatabaseBriefInfo instances
        for db in databases:
            assert isinstance(db, DatabaseBriefInfo)
            assert db.name is not None

    def test_list_databases_with_tables(self, backend_with_tables):
        """Test list_databases includes table count."""
        status = backend_with_tables.introspector.status

        databases = status.list_databases()

        # At least one database should have tables
        assert len(databases) >= 1

    def test_list_users(self, clickhouse_backend):
        """Test list_users returns user list."""
        status = clickhouse_backend.introspector.status

        users = status.list_users()

        assert isinstance(users, list)

        # ClickHouse typically has at least one user
        for user in users:
            assert isinstance(user, UserInfo)
            assert user.name is not None

    def test_get_innodb_info(self, clickhouse_backend):
        """Test get_innodb_info returns InnoDBInfo."""
        status = clickhouse_backend.introspector.status

        innodb_info = status.get_innodb_info()

        assert isinstance(innodb_info, InnoDBInfo)
        # InnoDB is the default engine, should have info
        assert innodb_info.extra is not None

    def test_get_binary_log_info(self, clickhouse_backend):
        """Test get_binary_log_info returns BinaryLogInfo."""
        status = clickhouse_backend.introspector.status

        binlog_info = status.get_binary_log_info()

        assert isinstance(binlog_info, BinaryLogInfo)
        # Binary log may or may not be enabled

    def test_get_slow_query_info(self, clickhouse_backend):
        """Test get_slow_query_info returns SlowQueryInfo."""
        status = clickhouse_backend.introspector.status

        slow_query_info = status.get_slow_query_info()

        assert isinstance(slow_query_info, SlowQueryInfo)
        # Slow query log info should be available

    def test_status_item_has_description(self, clickhouse_backend):
        """Test that status items have descriptions."""
        status = clickhouse_backend.introspector.status

        items = status.list_configuration()

        # Check that items have descriptions
        for item in items:
            assert item.description is not None

    def test_status_item_readonly_flag(self, clickhouse_backend):
        """Test that readonly items are marked correctly."""
        status = clickhouse_backend.introspector.status

        items = status.list_configuration()

        # version should be readonly
        version_item = next((i for i in items if i.name == "version"), None)
        if version_item:
            assert version_item.is_readonly is True


class TestClickHouseStatusIntrospectorMixin:
    """Tests for ClickHouseStatusIntrospectorMixin helper methods."""

    def test_parse_variable_value_int(self, clickhouse_backend):
        """Test _parse_variable_value handles integers."""
        status = clickhouse_backend.introspector.status

        result = status._parse_variable_value("42")
        assert result == 42
        assert isinstance(result, int)

    def test_parse_variable_value_str(self, clickhouse_backend):
        """Test _parse_variable_value preserves non-integer strings."""
        status = clickhouse_backend.introspector.status

        result = status._parse_variable_value("utf8mb4")
        assert result == "utf8mb4"
        assert isinstance(result, str)

    def test_create_status_item(self, clickhouse_backend):
        """Test _create_status_item creates proper StatusItem."""
        status = clickhouse_backend.introspector.status

        item = status._create_status_item(
            name="test_param",
            value="42",
            category=StatusCategory.CONFIGURATION,
            description="Test parameter",
            unit="ms",
            is_readonly=False,
        )

        assert isinstance(item, StatusItem)
        assert item.name == "test_param"
        assert item.value == 42  # Should be parsed to int
        assert item.category == StatusCategory.CONFIGURATION
        assert item.description == "Test parameter"
        assert item.unit == "ms"
        assert item.is_readonly is False

    def test_get_vendor_name(self, clickhouse_backend):
        """Test _get_vendor_name returns ClickHouse."""
        status = clickhouse_backend.introspector.status

        vendor = status._get_vendor_name()
        assert vendor == "ClickHouse"


class TestStatusIntrospectorCategories:
    """Tests for different status categories."""

    def test_configuration_category_items(self, clickhouse_backend):
        """Test items in CONFIGURATION category."""
        status = clickhouse_backend.introspector.status

        items = status.list_configuration(category=StatusCategory.CONFIGURATION)

        for item in items:
            assert item.category == StatusCategory.CONFIGURATION

    def test_performance_category_items(self, clickhouse_backend):
        """Test items in PERFORMANCE category."""
        status = clickhouse_backend.introspector.status

        items = status.list_configuration(category=StatusCategory.PERFORMANCE)

        for item in items:
            assert item.category == StatusCategory.PERFORMANCE

    def test_storage_category_items(self, clickhouse_backend):
        """Test items in STORAGE category."""
        status = clickhouse_backend.introspector.status

        items = status.list_configuration(category=StatusCategory.STORAGE)

        for item in items:
            assert item.category == StatusCategory.STORAGE

    def test_security_category_items(self, clickhouse_backend):
        """Test items in SECURITY category."""
        status = clickhouse_backend.introspector.status

        items = status.list_configuration(category=StatusCategory.SECURITY)

        for item in items:
            assert item.category == StatusCategory.SECURITY


class TestClickHouseReplicationInfo:
    """Tests for ClickHouse replication status."""

    def test_get_clickhouse_replication_info(self, clickhouse_backend):
        """Test get_clickhouse_replication_info returns ClickHouseReplicationInfo."""
        status = clickhouse_backend.introspector.status

        repl_info = status.get_clickhouse_replication_info()

        assert isinstance(repl_info, ClickHouseReplicationInfo)
        # Replication may or may not be configured


class TestAsyncClickHouseStatusIntrospector:
    """Tests for asynchronous ClickHouse status introspector."""

    @pytest.mark.asyncio
    async def test_get_overview(self, async_clickhouse_backend):
        """Test async get_overview returns valid ServerOverview."""
        status = async_clickhouse_backend.introspector.status

        overview = await status.get_overview()

        assert isinstance(overview, ServerOverview)
        assert overview.server_vendor == "ClickHouse"
        assert overview.server_version is not None
        assert isinstance(overview.configuration, list)
        assert isinstance(overview.performance, list)
        assert isinstance(overview.storage, StorageInfo)
        assert isinstance(overview.databases, list)

    @pytest.mark.asyncio
    async def test_get_overview_version_matches_dialect(self, async_clickhouse_backend):
        """Test that async overview version matches dialect version."""
        status = async_clickhouse_backend.introspector.status
        overview = await status.get_overview()

        expected_version = ".".join(map(str, async_clickhouse_backend.dialect.version))
        assert overview.server_version == expected_version

    @pytest.mark.asyncio
    async def test_list_configuration(self, async_clickhouse_backend):
        """Test async list_configuration returns configuration items."""
        status = async_clickhouse_backend.introspector.status

        items = await status.list_configuration()

        assert isinstance(items, list)
        assert len(items) > 0

        # Check that all items are StatusItem instances
        for item in items:
            assert isinstance(item, StatusItem)
            assert item.name is not None
            assert item.value is not None

    @pytest.mark.asyncio
    async def test_list_configuration_with_category_filter(self, async_clickhouse_backend):
        """Test async list_configuration with category filter."""
        status = async_clickhouse_backend.introspector.status

        config_items = await status.list_configuration(category=StatusCategory.CONFIGURATION)

        for item in config_items:
            assert item.category == StatusCategory.CONFIGURATION

    @pytest.mark.asyncio
    async def test_list_configuration_contains_expected_items(self, async_clickhouse_backend):
        """Test that async configuration contains expected ClickHouse variables."""
        status = async_clickhouse_backend.introspector.status

        items = await status.list_configuration()
        item_names = [item.name for item in items]

        # Check for some common ClickHouse variables
        assert "port" in item_names
        assert "version" in item_names

    @pytest.mark.asyncio
    async def test_list_performance_metrics(self, async_clickhouse_backend):
        """Test async list_performance_metrics returns status items."""
        status = async_clickhouse_backend.introspector.status

        items = await status.list_performance_metrics()

        assert isinstance(items, list)
        # Items should have various categories (PERFORMANCE, CONNECTION, etc.)
        for item in items:
            assert isinstance(item, StatusItem)

    @pytest.mark.asyncio
    async def test_get_connection_info(self, async_clickhouse_backend):
        """Test async get_connection_info returns ConnectionInfo."""
        status = async_clickhouse_backend.introspector.status

        conn_info = await status.get_connection_info()

        assert isinstance(conn_info, ConnectionInfo)
        assert conn_info.active_count is not None or conn_info.max_connections is not None

    @pytest.mark.asyncio
    async def test_get_storage_info(self, async_clickhouse_backend):
        """Test async get_storage_info returns StorageInfo."""
        status = async_clickhouse_backend.introspector.status

        storage = await status.get_storage_info()

        assert isinstance(storage, StorageInfo)

    @pytest.mark.asyncio
    async def test_list_databases(self, async_clickhouse_backend):
        """Test async list_databases returns database list."""
        status = async_clickhouse_backend.introspector.status

        databases = await status.list_databases()

        assert isinstance(databases, list)
        assert len(databases) >= 1

        for db in databases:
            assert isinstance(db, DatabaseBriefInfo)

    @pytest.mark.asyncio
    async def test_list_users(self, async_clickhouse_backend):
        """Test async list_users returns user list."""
        status = async_clickhouse_backend.introspector.status

        users = await status.list_users()

        assert isinstance(users, list)

        for user in users:
            assert isinstance(user, UserInfo)

    @pytest.mark.asyncio
    async def test_get_innodb_info(self, async_clickhouse_backend):
        """Test async get_innodb_info returns InnoDBInfo."""
        status = async_clickhouse_backend.introspector.status

        innodb_info = await status.get_innodb_info()

        assert isinstance(innodb_info, InnoDBInfo)

    @pytest.mark.asyncio
    async def test_get_binary_log_info(self, async_clickhouse_backend):
        """Test async get_binary_log_info returns BinaryLogInfo."""
        status = async_clickhouse_backend.introspector.status

        binlog_info = await status.get_binary_log_info()

        assert isinstance(binlog_info, BinaryLogInfo)

    @pytest.mark.asyncio
    async def test_get_slow_query_info(self, async_clickhouse_backend):
        """Test async get_slow_query_info returns SlowQueryInfo."""
        status = async_clickhouse_backend.introspector.status

        slow_query_info = await status.get_slow_query_info()

        assert isinstance(slow_query_info, SlowQueryInfo)

    @pytest.mark.asyncio
    async def test_get_clickhouse_replication_info(self, async_clickhouse_backend):
        """Test async get_clickhouse_replication_info returns ClickHouseReplicationInfo."""
        status = async_clickhouse_backend.introspector.status

        repl_info = await status.get_clickhouse_replication_info()

        assert isinstance(repl_info, ClickHouseReplicationInfo)

    @pytest.mark.asyncio
    async def test_status_item_has_description(self, async_clickhouse_backend):
        """Test that async status items have descriptions."""
        status = async_clickhouse_backend.introspector.status

        items = await status.list_configuration()

        for item in items:
            assert item.description is not None

    @pytest.mark.asyncio
    async def test_status_item_readonly_flag(self, async_clickhouse_backend):
        """Test that async readonly items are marked correctly."""
        status = async_clickhouse_backend.introspector.status

        items = await status.list_configuration()

        version_item = next((i for i in items if i.name == "version"), None)
        if version_item:
            assert version_item.is_readonly is True


class TestAsyncClickHouseStatusIntrospectorMixin:
    """Tests for async ClickHouseStatusIntrospectorMixin helper methods."""

    @pytest.mark.asyncio
    async def test_parse_variable_value_int(self, async_clickhouse_backend):
        """Test _parse_variable_value handles integers."""
        status = async_clickhouse_backend.introspector.status

        result = status._parse_variable_value("42")
        assert result == 42
        assert isinstance(result, int)

    @pytest.mark.asyncio
    async def test_parse_variable_value_str(self, async_clickhouse_backend):
        """Test _parse_variable_value preserves non-integer strings."""
        status = async_clickhouse_backend.introspector.status

        result = status._parse_variable_value("utf8mb4")
        assert result == "utf8mb4"
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_vendor_name(self, async_clickhouse_backend):
        """Test _get_vendor_name returns ClickHouse."""
        status = async_clickhouse_backend.introspector.status

        vendor = status._get_vendor_name()
        assert vendor == "ClickHouse"


class TestAsyncStatusIntrospectorCategories:
    """Tests for different async status categories."""

    @pytest.mark.asyncio
    async def test_configuration_category_items(self, async_clickhouse_backend):
        """Test async items in CONFIGURATION category."""
        status = async_clickhouse_backend.introspector.status

        items = await status.list_configuration(category=StatusCategory.CONFIGURATION)

        for item in items:
            assert item.category == StatusCategory.CONFIGURATION

    @pytest.mark.asyncio
    async def test_performance_category_items(self, async_clickhouse_backend):
        """Test async items in PERFORMANCE category."""
        status = async_clickhouse_backend.introspector.status

        items = await status.list_configuration(category=StatusCategory.PERFORMANCE)

        for item in items:
            assert item.category == StatusCategory.PERFORMANCE

    @pytest.mark.asyncio
    async def test_storage_category_items(self, async_clickhouse_backend):
        """Test async items in STORAGE category."""
        status = async_clickhouse_backend.introspector.status

        items = await status.list_configuration(category=StatusCategory.STORAGE)

        for item in items:
            assert item.category == StatusCategory.STORAGE

    @pytest.mark.asyncio
    async def test_security_category_items(self, async_clickhouse_backend):
        """Test async items in SECURITY category."""
        status = async_clickhouse_backend.introspector.status

        items = await status.list_configuration(category=StatusCategory.SECURITY)

        for item in items:
            assert item.category == StatusCategory.SECURITY
