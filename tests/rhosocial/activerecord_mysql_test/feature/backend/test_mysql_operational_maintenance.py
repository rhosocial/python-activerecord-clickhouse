# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_operational_maintenance.py
"""Real ClickHouse operational maintenance tests."""

import pytest


OP_TABLE = "ar_clickhouse_operational_items"


def _create_table(backend):
    backend.execute(f"DROP TABLE IF EXISTS `{OP_TABLE}`")
    backend.execute(f"""
        CREATE TABLE `{OP_TABLE}` (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            category VARCHAR(50) NOT NULL,
            UNIQUE KEY uq_name (name),
            KEY idx_category (category)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='operational smoke table'
    """)
    backend.execute(
        f"INSERT INTO `{OP_TABLE}` (name, category) VALUES (%s, %s), (%s, %s), (%s, %s)",
        ("alpha", "a", "beta", "b", "gamma", "a"),
    )


async def _async_create_table(backend):
    await backend.execute(f"DROP TABLE IF EXISTS `{OP_TABLE}`")
    await backend.execute(f"""
        CREATE TABLE `{OP_TABLE}` (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            category VARCHAR(50) NOT NULL,
            UNIQUE KEY uq_name (name),
            KEY idx_category (category)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='operational smoke table'
    """)
    await backend.execute(
        f"INSERT INTO `{OP_TABLE}` (name, category) VALUES (%s, %s), (%s, %s), (%s, %s)",
        ("alpha", "a", "beta", "b", "gamma", "a"),
    )


@pytest.fixture
def clickhouse_operational_table(clickhouse_backend):
    """Create a real table for ClickHouse operational maintenance tests."""
    _create_table(clickhouse_backend)
    yield OP_TABLE
    clickhouse_backend.execute(f"DROP TABLE IF EXISTS `{OP_TABLE}`")


@pytest.fixture
async def async_clickhouse_operational_table(async_clickhouse_backend):
    """Create a real table for async ClickHouse operational maintenance tests."""
    await _async_create_table(async_clickhouse_backend)
    yield OP_TABLE
    await async_clickhouse_backend.execute(f"DROP TABLE IF EXISTS `{OP_TABLE}`")


class TestClickHouseOperationalMaintenance:
    """Synchronous common operational maintenance tests for ClickHouse."""

    def test_show_create_table_reflects_table_options(self, clickhouse_backend, clickhouse_operational_table):
        """SHOW CREATE TABLE should expose engine, charset, comment, and indexes."""
        row = clickhouse_backend.fetch_one(f"SHOW CREATE TABLE `{clickhouse_operational_table}`")
        create_sql = row.get("Create Table") or row.get("Create Table".lower())

        assert "ENGINE=InnoDB" in create_sql
        assert "utf8mb4" in create_sql
        assert "operational smoke table" in create_sql
        assert "idx_category" in create_sql

    def test_analyze_and_check_table(self, clickhouse_backend, clickhouse_operational_table):
        """ANALYZE TABLE and CHECK TABLE should execute on a real table."""
        analyze_rows = clickhouse_backend.fetch_all(f"ANALYZE TABLE `{clickhouse_operational_table}`")
        check_rows = clickhouse_backend.fetch_all(f"CHECK TABLE `{clickhouse_operational_table}`")

        assert analyze_rows
        assert check_rows
        assert any("OK" in str(row).upper() for row in check_rows)

    def test_optimize_table_keeps_data_usable(self, clickhouse_backend, clickhouse_operational_table):
        """OPTIMIZE TABLE should not make the table unusable."""
        clickhouse_backend.fetch_all(f"OPTIMIZE TABLE `{clickhouse_operational_table}`")
        count = clickhouse_backend.fetch_one(f"SELECT COUNT(*) AS count FROM `{clickhouse_operational_table}`")
        assert count["count"] == 3

    def test_truncate_resets_auto_increment(self, clickhouse_backend, clickhouse_operational_table):
        """TRUNCATE TABLE should clear data and reset AUTO_INCREMENT."""
        clickhouse_backend.execute(f"TRUNCATE TABLE `{clickhouse_operational_table}`")
        clickhouse_backend.execute(
            f"INSERT INTO `{clickhouse_operational_table}` (name, category) VALUES (%s, %s)",
            ("delta", "d"),
        )
        row = clickhouse_backend.fetch_one(f"SELECT id, name FROM `{clickhouse_operational_table}`")
        assert row["id"] == 1
        assert row["name"] == "delta"


class TestAsyncClickHouseOperationalMaintenance:
    """Asynchronous common operational maintenance tests for ClickHouse."""

    @pytest.mark.asyncio
    async def test_show_create_table_reflects_table_options(
        self,
        async_clickhouse_backend,
        async_clickhouse_operational_table,
    ):
        """SHOW CREATE TABLE should expose engine, charset, comment, and indexes."""
        row = await async_clickhouse_backend.fetch_one(f"SHOW CREATE TABLE `{async_clickhouse_operational_table}`")
        create_sql = row.get("Create Table") or row.get("Create Table".lower())

        assert "ENGINE=InnoDB" in create_sql
        assert "utf8mb4" in create_sql
        assert "operational smoke table" in create_sql
        assert "idx_category" in create_sql

    @pytest.mark.asyncio
    async def test_analyze_and_check_table(self, async_clickhouse_backend, async_clickhouse_operational_table):
        """ANALYZE TABLE and CHECK TABLE should execute on a real table."""
        analyze_rows = await async_clickhouse_backend.fetch_all(f"ANALYZE TABLE `{async_clickhouse_operational_table}`")
        check_rows = await async_clickhouse_backend.fetch_all(f"CHECK TABLE `{async_clickhouse_operational_table}`")

        assert analyze_rows
        assert check_rows
        assert any("OK" in str(row).upper() for row in check_rows)

    @pytest.mark.asyncio
    async def test_optimize_table_keeps_data_usable(
        self,
        async_clickhouse_backend,
        async_clickhouse_operational_table,
    ):
        """OPTIMIZE TABLE should not make the table unusable."""
        await async_clickhouse_backend.fetch_all(f"OPTIMIZE TABLE `{async_clickhouse_operational_table}`")
        count = await async_clickhouse_backend.fetch_one(f"SELECT COUNT(*) AS count FROM `{async_clickhouse_operational_table}`")
        assert count["count"] == 3

    @pytest.mark.asyncio
    async def test_truncate_resets_auto_increment(
        self,
        async_clickhouse_backend,
        async_clickhouse_operational_table,
    ):
        """TRUNCATE TABLE should clear data and reset AUTO_INCREMENT."""
        await async_clickhouse_backend.execute(f"TRUNCATE TABLE `{async_clickhouse_operational_table}`")
        await async_clickhouse_backend.execute(
            f"INSERT INTO `{async_clickhouse_operational_table}` (name, category) VALUES (%s, %s)",
            ("delta", "d"),
        )
        row = await async_clickhouse_backend.fetch_one(f"SELECT id, name FROM `{async_clickhouse_operational_table}`")
        assert row["id"] == 1
        assert row["name"] == "delta"
