# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_spatial_types_backend.py
"""
ClickHouse spatial data type integration tests using real database connection.

This module tests the ClickHouse-specific spatial data type functionality with actual database operations.
Tests use the dialect mixin methods to generate SQL, validating our implementation.
"""

import pytest
from rhosocial.activerecord.testsuite.utils import requires_protocol
from rhosocial.activerecord.backend.impl.clickhouse.protocols import ClickHouseSpatialSupport


class TestClickHouseSpatialTypeBackend:
    """Synchronous tests for ClickHouse spatial types with real database."""

    def test_supports_spatial_type_detection(self, clickhouse_backend):
        """Test that dialect correctly detects spatial type support."""
        dialect = clickhouse_backend.dialect

        if dialect.version >= (5, 7, 0):
            assert dialect.supports_spatial_type("POINT")
            assert dialect.supports_spatial_type("GEOMETRY")
            assert not dialect.supports_spatial_type("INVALID_TYPE")
        else:
            assert not dialect.supports_spatial_type("POINT")

    def test_supports_spatial_index_detection(self, clickhouse_backend):
        """Test that dialect correctly detects SPATIAL index support."""
        dialect = clickhouse_backend.dialect

        if dialect.version >= (5, 7, 0):
            assert dialect.supports_spatial_index()
        else:
            assert not dialect.supports_spatial_index()

    def test_supports_geojson_detection(self, clickhouse_backend):
        """Test that dialect correctly detects GeoJSON support."""
        dialect = clickhouse_backend.dialect

        if dialect.version >= (5, 7, 5):
            assert dialect.supports_geojson()
        else:
            assert not dialect.supports_geojson()

    @requires_protocol(ClickHouseSpatialSupport, "supports_spatial_type")
    def test_format_spatial_literal_without_srid(self, clickhouse_backend):
        """Test format_spatial_literal generates correct SQL without SRID."""
        clickhouse_backend.execute("""
            CREATE TEMPORARY TABLE test_spatial_literal (
                id INT AUTO_INCREMENT PRIMARY KEY,
                location GEOMETRY
            )
        """)

        dialect = clickhouse_backend.dialect
        sql, params = dialect.format_spatial_literal("POINT(5 5)")

        clickhouse_backend.execute(f"INSERT INTO test_spatial_literal (location) VALUES ({sql})", params)

        result = clickhouse_backend.execute("SELECT ST_AsText(location) as wkt FROM test_spatial_literal WHERE id = 1")

        assert "POINT(5 5)" in result.data[0]["wkt"]

        clickhouse_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_spatial_literal")

    @requires_protocol(ClickHouseSpatialSupport, "supports_spatial_type")
    def test_format_spatial_literal_with_srid(self, clickhouse_backend):
        """Test format_spatial_literal generates correct SQL with SRID."""
        clickhouse_backend.execute("""
            CREATE TEMPORARY TABLE test_spatial_srid (
                id INT AUTO_INCREMENT PRIMARY KEY,
                location GEOMETRY
            )
        """)

        dialect = clickhouse_backend.dialect
        sql, params = dialect.format_spatial_literal("POINT(10 20)", 4326)

        clickhouse_backend.execute(f"INSERT INTO test_spatial_srid (location) VALUES ({sql})", params)

        result = clickhouse_backend.execute(
            "SELECT ST_SRID(location) as srid, ST_AsText(location) as wkt FROM test_spatial_srid WHERE id = 1"
        )

        assert result.data[0]["srid"] == 4326
        assert "POINT(10 20)" in result.data[0]["wkt"]

        clickhouse_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_spatial_srid")

    @requires_protocol(ClickHouseSpatialSupport)
    def test_format_st_geom_from_text_without_srid(self, clickhouse_backend):
        """Test format_st_geom_from_text generates correct SQL without SRID."""
        dialect = clickhouse_backend.dialect
        sql, params = dialect.format_st_geom_from_text("POINT(3 4)")

        result = clickhouse_backend.execute(f"SELECT ST_AsText({sql}) as wkt", params)

        assert "POINT(3 4)" in result.data[0]["wkt"]

    @requires_protocol(ClickHouseSpatialSupport)
    def test_format_st_geom_from_text_with_srid(self, clickhouse_backend):
        """Test format_st_geom_from_text generates correct SQL with SRID."""
        dialect = clickhouse_backend.dialect
        sql, params = dialect.format_st_geom_from_text("POINT(1 1)", 4326)

        result = clickhouse_backend.execute(f"SELECT ST_SRID({sql}) as srid", params)

        assert result.data[0]["srid"] == 4326

    @requires_protocol(ClickHouseSpatialSupport)
    def test_format_st_as_text(self, clickhouse_backend):
        """Test format_st_as_text generates correct SQL."""
        clickhouse_backend.execute("""
            CREATE TEMPORARY TABLE test_astext (
                id INT AUTO_INCREMENT PRIMARY KEY,
                location GEOMETRY
            )
        """)

        clickhouse_backend.execute("INSERT INTO test_astext (location) VALUES (ST_GeomFromText('POINT(7 8)'))")

        dialect = clickhouse_backend.dialect
        sql, params = dialect.format_st_as_text("location")

        result = clickhouse_backend.execute(f"SELECT {sql} as wkt FROM test_astext", params)

        assert "POINT(7 8)" in result.data[0]["wkt"]

        clickhouse_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_astext")

    @requires_protocol(ClickHouseSpatialSupport, "supports_geojson")
    def test_format_st_as_geojson(self, clickhouse_backend):
        """Test format_st_as_geojson generates correct SQL."""
        clickhouse_backend.execute("""
            CREATE TEMPORARY TABLE test_geojson (
                id INT AUTO_INCREMENT PRIMARY KEY,
                location GEOMETRY
            )
        """)

        clickhouse_backend.execute("INSERT INTO test_geojson (location) VALUES (ST_GeomFromText('POINT(2 3)'))")

        dialect = clickhouse_backend.dialect
        sql, params = dialect.format_st_as_geojson("location")

        result = clickhouse_backend.execute(f"SELECT {sql} as geojson FROM test_geojson", params)

        assert "type" in result.data[0]["geojson"]
        assert "Point" in result.data[0]["geojson"]

        clickhouse_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_geojson")

    @requires_protocol(ClickHouseSpatialSupport)
    def test_format_st_distance(self, clickhouse_backend):
        """Test format_st_distance generates correct SQL."""
        dialect = clickhouse_backend.dialect

        point1_sql, point1_params = dialect.format_st_geom_from_text("POINT(0 0)")
        point2_sql, point2_params = dialect.format_st_geom_from_text("POINT(3 4)")

        distance_sql, _ = dialect.format_st_distance(point1_sql, point2_sql)

        result = clickhouse_backend.execute(f"SELECT {distance_sql} as distance", point1_params + point2_params)

        assert abs(result.data[0]["distance"] - 5.0) < 0.001

    @requires_protocol(ClickHouseSpatialSupport)
    def test_format_st_within(self, clickhouse_backend):
        """Test format_st_within generates correct SQL."""
        dialect = clickhouse_backend.dialect

        point_sql, point_params = dialect.format_st_geom_from_text("POINT(5 5)")
        polygon_sql, polygon_params = dialect.format_st_geom_from_text("POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))")

        within_sql, _ = dialect.format_st_within(point_sql, polygon_sql)

        result = clickhouse_backend.execute(f"SELECT {within_sql} as is_within", point_params + polygon_params)

        assert result.data[0]["is_within"] == 1

    @requires_protocol(ClickHouseSpatialSupport)
    def test_format_st_contains(self, clickhouse_backend):
        """Test format_st_contains generates correct SQL."""
        dialect = clickhouse_backend.dialect

        polygon_sql, polygon_params = dialect.format_st_geom_from_text("POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))")
        point_sql, point_params = dialect.format_st_geom_from_text("POINT(5 5)")

        contains_sql, _ = dialect.format_st_contains(polygon_sql, point_sql)

        result = clickhouse_backend.execute(f"SELECT {contains_sql} as contains_point", polygon_params + point_params)

        assert result.data[0]["contains_point"] == 1

    @requires_protocol(ClickHouseSpatialSupport, "supports_spatial_index")
    def test_format_create_spatial_index(self, clickhouse_backend):
        """Test format_create_spatial_index generates valid SQL."""
        clickhouse_backend.execute("""
            CREATE TEMPORARY TABLE test_spatial_idx (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100),
                location GEOMETRY NOT NULL
            )
        """)

        dialect = clickhouse_backend.dialect
        index_sql, params = dialect.format_create_spatial_index("idx_location", "test_spatial_idx", "location")

        clickhouse_backend.execute(index_sql)

        insert_sql, insert_params = dialect.format_spatial_literal("POINT(1 1)")
        clickhouse_backend.execute(
            f"INSERT INTO test_spatial_idx (name, location) VALUES ('test', {insert_sql})", insert_params
        )

        result = clickhouse_backend.execute("SELECT COUNT(*) as cnt FROM test_spatial_idx")

        assert result.data[0]["cnt"] == 1

        clickhouse_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_spatial_idx")


class TestAsyncClickHouseSpatialTypeBackend:
    """Asynchronous tests for ClickHouse spatial types with real database."""

    @pytest.mark.asyncio
    async def test_async_supports_spatial_type_detection(self, async_clickhouse_backend):
        """Test that dialect correctly detects spatial type support (async)."""
        dialect = async_clickhouse_backend.dialect

        if dialect.version >= (5, 7, 0):
            assert dialect.supports_spatial_type("POINT")
            assert dialect.supports_spatial_type("GEOMETRY")
        else:
            assert not dialect.supports_spatial_type("POINT")

    @pytest.mark.asyncio
    @requires_protocol(ClickHouseSpatialSupport)
    async def test_async_format_spatial_literal(self, async_clickhouse_backend):
        """Test format_spatial_literal generates correct SQL (async)."""
        await async_clickhouse_backend.execute("""
            CREATE TEMPORARY TABLE test_async_spatial (
                id INT AUTO_INCREMENT PRIMARY KEY,
                location GEOMETRY
            )
        """)

        dialect = async_clickhouse_backend.dialect
        sql, params = dialect.format_spatial_literal("POINT(5 5)")

        await async_clickhouse_backend.execute(f"INSERT INTO test_async_spatial (location) VALUES ({sql})", params)

        result = await async_clickhouse_backend.execute(
            "SELECT ST_AsText(location) as wkt FROM test_async_spatial WHERE id = 1"
        )

        assert "POINT(5 5)" in result.data[0]["wkt"]

        await async_clickhouse_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_spatial")

    @pytest.mark.asyncio
    @requires_protocol(ClickHouseSpatialSupport)
    async def test_async_format_st_geom_from_text(self, async_clickhouse_backend):
        """Test format_st_geom_from_text generates correct SQL (async)."""
        dialect = async_clickhouse_backend.dialect
        sql, params = dialect.format_st_geom_from_text("POINT(10 20)", 4326)

        result = await async_clickhouse_backend.execute(f"SELECT ST_SRID({sql}) as srid", params)

        assert result.data[0]["srid"] == 4326

    @pytest.mark.asyncio
    @requires_protocol(ClickHouseSpatialSupport)
    async def test_async_format_st_distance(self, async_clickhouse_backend):
        """Test format_st_distance generates correct SQL (async)."""
        dialect = async_clickhouse_backend.dialect

        point1_sql, point1_params = dialect.format_st_geom_from_text("POINT(0 0)")
        point2_sql, point2_params = dialect.format_st_geom_from_text("POINT(3 4)")

        distance_sql, _ = dialect.format_st_distance(point1_sql, point2_sql)

        result = await async_clickhouse_backend.execute(f"SELECT {distance_sql} as distance", point1_params + point2_params)

        assert abs(result.data[0]["distance"] - 5.0) < 0.001

    @pytest.mark.asyncio
    @requires_protocol(ClickHouseSpatialSupport)
    async def test_async_format_st_within(self, async_clickhouse_backend):
        """Test format_st_within generates correct SQL (async)."""
        dialect = async_clickhouse_backend.dialect

        point_sql, point_params = dialect.format_st_geom_from_text("POINT(5 5)")
        polygon_sql, polygon_params = dialect.format_st_geom_from_text("POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))")

        within_sql, _ = dialect.format_st_within(point_sql, polygon_sql)

        result = await async_clickhouse_backend.execute(f"SELECT {within_sql} as is_within", point_params + polygon_params)

        assert result.data[0]["is_within"] == 1

    @pytest.mark.asyncio
    @requires_protocol(ClickHouseSpatialSupport, "supports_geojson")
    async def test_async_format_st_as_geojson(self, async_clickhouse_backend):
        """Test format_st_as_geojson generates correct SQL (async)."""
        await async_clickhouse_backend.execute("""
            CREATE TEMPORARY TABLE test_async_geojson (
                id INT AUTO_INCREMENT PRIMARY KEY,
                location GEOMETRY
            )
        """)

        await async_clickhouse_backend.execute(
            "INSERT INTO test_async_geojson (location) VALUES (ST_GeomFromText('POINT(1 2)'))"
        )

        dialect = async_clickhouse_backend.dialect
        sql, params = dialect.format_st_as_geojson("location")

        result = await async_clickhouse_backend.execute(f"SELECT {sql} as geojson FROM test_async_geojson", params)

        assert "Point" in result.data[0]["geojson"]

        await async_clickhouse_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_geojson")

    @pytest.mark.asyncio
    @requires_protocol(ClickHouseSpatialSupport, "supports_spatial_index")
    async def test_async_format_create_spatial_index(self, async_clickhouse_backend):
        """Test format_create_spatial_index generates valid SQL (async)."""
        await async_clickhouse_backend.execute("""
            CREATE TEMPORARY TABLE test_async_idx (
                id INT AUTO_INCREMENT PRIMARY KEY,
                location GEOMETRY NOT NULL
            )
        """)

        dialect = async_clickhouse_backend.dialect
        index_sql, _ = dialect.format_create_spatial_index("idx_loc", "test_async_idx", "location")

        await async_clickhouse_backend.execute(index_sql)

        insert_sql, insert_params = dialect.format_spatial_literal("POINT(1 1)")
        await async_clickhouse_backend.execute(f"INSERT INTO test_async_idx (location) VALUES ({insert_sql})", insert_params)

        result = await async_clickhouse_backend.execute("SELECT COUNT(*) as cnt FROM test_async_idx")

        assert result.data[0]["cnt"] == 1

        await async_clickhouse_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_idx")
