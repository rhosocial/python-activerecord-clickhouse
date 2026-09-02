# src/rhosocial/activerecord/backend/impl/clickhouse/protocols.py
"""ClickHouse dialect-specific protocol definitions.

This module defines protocols for features exclusive to ClickHouse,
which are not part of the SQL standard and not supported by other
mainstream databases.

Note: ClickHouse-specific protocols extend generic protocols to avoid interface overlap.
When a ClickHouse protocol extends a generic protocol, dialects only need to implement
the ClickHouse-specific protocol - isinstance checks for the generic protocol will still work.
"""

from typing import Protocol, runtime_checkable, Tuple, Any, Optional, List, Dict, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import OnConflictClause
    from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
        ModifyColumn,
        ChangeColumn,
    )
    from rhosocial.activerecord.backend.expression.statements.ddl_table import CreateTableExpression
    from rhosocial.activerecord.backend.expression.statements.ddl_trigger import (
        CreateTriggerExpression,
        DropTriggerExpression,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.admin import (
        ClickHouseCacheIndexExpression,
        ClickHouseCloneExpression,
        ClickHouseCreateUserExpression,
        ClickHouseDoExpression,
        ClickHouseDropUserExpression,
        ClickHouseFlushExpression,
        ClickHouseGrantExpression,
        ClickHouseHelpExpression,
        ClickHouseHandlerCloseExpression,
        ClickHouseHandlerOpenExpression,
        ClickHouseHandlerReadExpression,
        ClickHouseInstallComponentExpression,
        ClickHouseInstallPluginExpression,
        ClickHouseKillExpression,
        ClickHouseLoadIndexIntoCacheExpression,
        ClickHouseResetExpression,
        ClickHouseRestartExpression,
        ClickHouseRevokeExpression,
        ClickHouseShutdownExpression,
        ClickHouseBinlogExpression,
        ClickHouseUninstallComponentExpression,
        ClickHouseUninstallPluginExpression,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
        CreateJsonDualityViewExpression,
        DropJsonDualityViewExpression,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.load_data import (
        ClickHouseLoadDataExpression,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.load_xml import (
        ClickHouseLoadXMLEXpression,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.optimizer_hint import (
        ClickHouseOptimizerHintExpression,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
        ClickHouseAddPartitionExpression,
        ClickHouseAnalyzePartitionExpression,
        ClickHouseCheckPartitionExpression,
        ClickHouseCoalescePartitionExpression,
        ClickHouseDropPartitionExpression,
        ClickHouseExchangePartitionExpression,
        ClickHouseGetPartitionsExpression,
        ClickHouseOptimizePartitionExpression,
        ClickHousePartitionByHash,
        ClickHousePartitionByKey,
        ClickHousePartitionByList,
        ClickHousePartitionByListColumns,
        ClickHousePartitionByRange,
        ClickHousePartitionByRangeColumns,
        ClickHousePartitionDefinition,
        ClickHousePartitionMaxValue,
        ClickHousePartitionValue,
        ClickHouseRebuildPartitionExpression,
        ClickHouseRemovePartitioningExpression,
        ClickHouseRepairPartitionExpression,
        ClickHouseReorganizePartitionExpression,
        ClickHouseSubpartitionClause,
        ClickHouseSubpartitionDefinition,
        ClickHouseTruncatePartitionExpression,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.rename_table import (
        ClickHouseRenameTableExpression,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.routine import (
        ClickHouseCallExpression,
        ClickHouseCreateFunctionExpression,
        ClickHouseCreateProcedureExpression,
        ClickHouseDropFunctionExpression,
        ClickHouseDropProcedureExpression,
    )
    from rhosocial.activerecord.backend.impl.clickhouse.expression.table_statement import (
        ClickHouseTableExpression,
        ClickHouseValuesExpression,
    )

from rhosocial.activerecord.backend.dialect.protocols import (
    IndexSupport,
    JSONSupport,
    LockingSupport,
    PartitionSupport,
    TableSupport,
)


@runtime_checkable
class ClickHouseDMLOperationSupport(Protocol):
    """ClickHouse-specific DML operations protocol.

    Feature Source: Not supported by ClickHouse (MySQL-originated concepts)

    ClickHouse does NOT support the following MySQL DML features:
    - INSERT IGNORE: Not supported (no duplicate-key silencing)
    - REPLACE INTO: Not supported (no delete-and-re-insert on duplicate key)
    - LOAD DATA INFILE: Not supported (use INSERT or clickhouse-client --query)

    All ``supports_*`` methods return False and ``format_*`` methods raise
    ``UnsupportedFeatureError``.
    """

    def supports_insert_ignore(self) -> bool:
        """Whether INSERT IGNORE is supported.

        ClickHouse does not support INSERT IGNORE (no duplicate-key handling).
        """
        ...

    def supports_replace_into(self) -> bool:
        """Whether REPLACE INTO is supported.

        ClickHouse does not support REPLACE INTO (no delete-and-re-insert on
        duplicate key).
        """
        ...

    def supports_load_data(self) -> bool:
        """Whether LOAD DATA INFILE is supported.

        ClickHouse does not support LOAD DATA INFILE.
        """
        ...

    def format_load_data_statement(self, expr: "ClickHouseLoadDataExpression") -> Tuple[str, tuple]:
        """Format LOAD DATA INFILE statement.

        Raises:
            UnsupportedFeatureError: ClickHouse does not support LOAD DATA INFILE.

        Args:
            expr: ClickHouseLoadDataExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_on_conflict_clause(self, expr: "OnConflictClause") -> Tuple[str, tuple]:
        """Format ON CONFLICT / ON DUPLICATE KEY UPDATE clause.

        ClickHouse does not support upsert clauses (ON CONFLICT or MySQL's
        ON DUPLICATE KEY UPDATE).

        Args:
            expr: OnConflictExpression or equivalent instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...


@runtime_checkable
class ClickHouseTriggerSupport(Protocol):
    """ClickHouse trigger DDL protocol.

    Feature Source: Native support (no extension required)

    ClickHouse triggers:
    - BEFORE/AFTER: Timing
    - INSERT/UPDATE/DELETE: Event
    - FOR EACH ROW: Level (only row-level triggers supported)
    - NEW/OLD: Row references

    Official Documentation:
    - CREATE TRIGGER: https://dev.clickhouse.com/doc/refman/8.0/en/create-trigger.html

    Version Requirements:
    - Triggers: ClickHouse 5.0.2+
    - Trigger IF EXISTS: ClickHouse 8.0.4+
    """

    def supports_trigger(self) -> bool:
        """Whether triggers are supported."""
        ...

    def supports_trigger_if_not_exists(self) -> bool:
        """Whether CREATE TRIGGER IF NOT EXISTS is supported (ClickHouse 8.0.4+)."""
        ...

    def supports_instead_of_trigger(self) -> bool:
        """Whether INSTEAD OF triggers are supported.

        ClickHouse does NOT support INSTEAD OF triggers (only BEFORE/AFTER).
        This method always returns False for ClickHouse.
        """
        ...

    def supports_statement_trigger(self) -> bool:
        """Whether statement-level triggers are supported.

        ClickHouse only supports row-level triggers (FOR EACH ROW).
        This method always returns False for ClickHouse.
        """
        ...

    def supports_trigger_referencing(self) -> bool:
        """Whether trigger referencing (NEW/OLD) is supported.

        ClickHouse supports NEW and OLD row references in triggers.
        """
        ...

    def supports_trigger_when(self) -> bool:
        """Whether WHEN condition on triggers is supported.

        ClickHouse does NOT support WHEN condition on triggers.
        This method always returns False for ClickHouse.
        """
        ...

    def format_create_trigger_statement(self, expr: "CreateTriggerExpression") -> Tuple[str, tuple]:
        """Format CREATE TRIGGER statement.

        Args:
            expr: CreateTriggerExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_drop_trigger_statement(self, expr: "DropTriggerExpression") -> Tuple[str, tuple]:
        """Format DROP TRIGGER statement.

        Args:
            expr: DropTriggerExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...


@runtime_checkable
class ClickHouseTableSupport(TableSupport, Protocol):
    """ClickHouse table DDL protocol.

    Feature Source: Native support (no extension required)

    ClickHouse table features beyond SQL standard:
    - ENGINE storage engine selection
    - CHARSET/COLLATE character set options
    - AUTO_INCREMENT column attribute
    - Inline index definitions in CREATE TABLE
    - Table-level COMMENT
    - CREATE TABLE ... LIKE syntax
    - Row format options

    Official Documentation:
    - CREATE TABLE: https://dev.clickhouse.com/doc/refman/8.0/en/create-table.html
    - CREATE TABLE ... LIKE: https://dev.clickhouse.com/doc/refman/8.0/en/create-table-like.html

    Version Requirements:
    - Basic features: All versions
    - Various storage engines: ClickHouse 5.5+
    """

    def supports_table_like_syntax(self) -> bool:
        """Whether CREATE TABLE ... LIKE is supported.

        ClickHouse supports copying table structure with LIKE syntax.
        """
        ...

    def supports_inline_index(self) -> bool:
        """Whether inline index definitions are supported.

        ClickHouse allows INDEX/KEY definitions within CREATE TABLE.
        """
        ...

    def supports_storage_engine_option(self) -> bool:
        """Whether ENGINE option is supported.

        ClickHouse supports multiple storage engines (InnoDB, MyISAM, etc.).
        """
        ...

    def supports_charset_option(self) -> bool:
        """Whether CHARSET/COLLATE options are supported.

        ClickHouse supports character set and collation at table level.
        """
        ...

    def format_create_table_statement(
        self, expr, dialect_options: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, tuple]:
        """Format CREATE TABLE statement."""
        ...

    def format_create_table_like(self, expr: "CreateTableExpression") -> Tuple[str, tuple]:
        """Format CREATE TABLE ... LIKE statement."""
        ...

    def format_column_definition(self, col_def: Any) -> Tuple[str, List]:
        """Format a column definition with ClickHouse-specific syntax (AUTO_INCREMENT, etc.)."""
        ...

    def format_table_constraint(self, t_const: Any) -> Tuple[str, List]:
        """Format a table-level constraint."""
        ...

    def format_inline_index(self, idx_def: Any) -> str:
        """Format inline INDEX definition within CREATE TABLE."""
        ...

    def format_storage_options(self, storage_options: Dict[str, Any]) -> str:
        """Format ClickHouse table storage options (ENGINE, CHARSET, etc.)."""
        ...


@runtime_checkable
class ClickHousePartitionSupport(PartitionSupport, Protocol):
    """ClickHouse table partitioning protocol.

    ClickHouse extends the generic PartitionSupport contract with ClickHouse-specific
    partitioning strategies and ALTER TABLE partition maintenance statements.
    Executable maintenance statements are represented by ClickHouse-specific
    expressions and formatted by the methods declared here.
    """

    def supports_range_columns_partitioning(self) -> bool:
        """Whether RANGE COLUMNS partitioning is supported."""
        ...

    def supports_list_columns_partitioning(self) -> bool:
        """Whether LIST COLUMNS partitioning is supported."""
        ...

    def supports_key_table_partitioning(self) -> bool:
        """Whether KEY partitioning is supported."""
        ...

    def supports_linear_hash_partitioning(self) -> bool:
        """Whether LINEAR HASH partitioning is supported."""
        ...

    def supports_linear_key_partitioning(self) -> bool:
        """Whether LINEAR KEY partitioning is supported."""
        ...

    def supports_partition_definition_options(self) -> bool:
        """Whether partition definitions support extra ClickHouse options."""
        ...

    def supports_partition_value_maxvalue(self) -> bool:
        """Whether MAXVALUE partition boundary token is supported."""
        ...

    def supports_remove_partitioning(self) -> bool:
        """Whether ALTER TABLE ... REMOVE PARTITIONING is supported."""
        ...

    def supports_coalesce_partition(self) -> bool:
        """Whether ALTER TABLE ... COALESCE PARTITION is supported."""
        ...

    def supports_exchange_partition(self) -> bool:
        """Whether ALTER TABLE ... EXCHANGE PARTITION is supported."""
        ...

    def supports_analyze_partition(self) -> bool:
        """Whether ALTER TABLE ... ANALYZE PARTITION is supported."""
        ...

    def supports_check_partition(self) -> bool:
        """Whether ALTER TABLE ... CHECK PARTITION is supported."""
        ...

    def supports_optimize_partition(self) -> bool:
        """Whether ALTER TABLE ... OPTIMIZE PARTITION is supported."""
        ...

    def supports_rebuild_partition(self) -> bool:
        """Whether ALTER TABLE ... REBUILD PARTITION is supported."""
        ...

    def supports_repair_partition(self) -> bool:
        """Whether ALTER TABLE ... REPAIR PARTITION is supported."""
        ...

    def format_partition_definition(self, definition: "ClickHousePartitionDefinition") -> Tuple[str, tuple]:
        """Format a ClickHouse PARTITION definition."""
        ...

    def format_partition_definition_options(self, options: dict) -> Tuple[str, tuple]:
        """Format ClickHouse PARTITION definition options."""
        ...

    def format_get_partitions_expression(self, expr: "ClickHouseGetPartitionsExpression") -> Tuple[str, tuple]:
        """Format a ``SELECT ... FROM information_schema.PARTITIONS`` query.

        Args:
            expr: ClickHouseGetPartitionsExpression with the target table name.

        Returns:
            Tuple of (SQL string, parameters tuple).
        """
        ...

    def format_partition_value(
        self,
        expr: "ClickHousePartitionValue | ClickHousePartitionMaxValue",
    ) -> Tuple[str, tuple]:
        """Format a ClickHouse partition boundary value."""
        ...

    def format_subpartition_by(self, expr: "ClickHouseSubpartitionClause") -> Tuple[str, tuple]:
        """Format ``SUBPARTITION BY {HASH|KEY}(...) SUBPARTITIONS N``.

        Args:
            expr: ClickHouseSubpartitionClause with strategy, optional expression,
                  optional count, and optional explicit definitions.

        Returns:
            Tuple of (SQL string, parameters tuple).

        Raises:
            UnsupportedFeatureError: if subpartitioning is not supported.
        """
        ...

    def format_subpartition_definition(self, definition: "ClickHouseSubpartitionDefinition") -> Tuple[str, tuple]:
        """Format a single ``SUBPARTITION name ...`` clause.

        Args:
            definition: ClickHouseSubpartitionDefinition with name and optional
                        dialect_options.

        Returns:
            Tuple of (SQL string, parameters tuple).

        Raises:
            ValueError: if the definition name is empty.
        """
        ...

    def format_partition_by_range(self, expr: "ClickHousePartitionByRange") -> Tuple[str, tuple]:
        """Format PARTITION BY RANGE."""
        ...

    def format_partition_by_range_columns(self, expr: "ClickHousePartitionByRangeColumns") -> Tuple[str, tuple]:
        """Format PARTITION BY RANGE COLUMNS."""
        ...

    def format_partition_by_list(self, expr: "ClickHousePartitionByList") -> Tuple[str, tuple]:
        """Format PARTITION BY LIST."""
        ...

    def format_partition_by_list_columns(self, expr: "ClickHousePartitionByListColumns") -> Tuple[str, tuple]:
        """Format PARTITION BY LIST COLUMNS."""
        ...

    def format_partition_by_hash(self, expr: "ClickHousePartitionByHash") -> Tuple[str, tuple]:
        """Format PARTITION BY HASH or LINEAR HASH."""
        ...

    def format_partition_by_key(self, expr: "ClickHousePartitionByKey") -> Tuple[str, tuple]:
        """Format PARTITION BY KEY or LINEAR KEY."""
        ...

    def format_add_partition_statement(self, expr: "ClickHouseAddPartitionExpression") -> Tuple[str, tuple]:
        """Format ALTER TABLE ... ADD PARTITION."""
        ...

    def format_drop_partition_statement(self, expr: "ClickHouseDropPartitionExpression") -> Tuple[str, tuple]:
        """Format ALTER TABLE ... DROP PARTITION."""
        ...

    def format_truncate_partition_statement(self, expr: "ClickHouseTruncatePartitionExpression") -> Tuple[str, tuple]:
        """Format ALTER TABLE ... TRUNCATE PARTITION."""
        ...

    def format_reorganize_partition_statement(
        self,
        expr: "ClickHouseReorganizePartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... REORGANIZE PARTITION."""
        ...

    def format_exchange_partition_statement(
        self,
        expr: "ClickHouseExchangePartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... EXCHANGE PARTITION."""
        ...

    def format_remove_partitioning_statement(
        self,
        expr: "ClickHouseRemovePartitioningExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... REMOVE PARTITIONING."""
        ...

    def format_coalesce_partition_statement(
        self,
        expr: "ClickHouseCoalescePartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... COALESCE PARTITION."""
        ...

    def format_analyze_partition_statement(
        self,
        expr: "ClickHouseAnalyzePartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... ANALYZE PARTITION."""
        ...

    def format_check_partition_statement(
        self,
        expr: "ClickHouseCheckPartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... CHECK PARTITION."""
        ...

    def format_optimize_partition_statement(
        self,
        expr: "ClickHouseOptimizePartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... OPTIMIZE PARTITION."""
        ...

    def format_rebuild_partition_statement(
        self,
        expr: "ClickHouseRebuildPartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... REBUILD PARTITION."""
        ...

    def format_repair_partition_statement(
        self,
        expr: "ClickHouseRepairPartitionExpression",
    ) -> Tuple[str, tuple]:
        """Format ALTER TABLE ... REPAIR PARTITION."""
        ...

    def format_partition_name_list(self, partitions: Sequence[str]) -> str:
        """Format a list of partition names: `p0`, `p1`, ..."""
        ...


@runtime_checkable
class ClickHouseSetTypeSupport(Protocol):
    """ClickHouse SET type protocol.

    Feature Source: ClickHouse native (not SQL standard)

    ClickHouse SET features:
    - String object with zero or more values from predefined list
    - Stored as integer (bit flags) internally
    - Maximum 64 members
    - Supports FIND_IN_SET, LIKE operations
    - Automatically sorted on storage

    Official Documentation:
    - SET Type: https://dev.clickhouse.com/doc/refman/8.0/en/set.html

    Version Requirements:
    - All ClickHouse versions
    """

    def supports_set_type(self) -> bool:
        """Whether SET type is supported."""
        ...

    def format_set_literal(self, values: List[str], column_values: Optional[List[str]] = None) -> Tuple[str, tuple]:
        """Format SET type literal.

        Args:
            values: Allowed values for the SET type
            column_values: Values being inserted/compared

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_find_in_set(self, value: str, set_column: str) -> Tuple[str, tuple]:
        """Format FIND_IN_SET function call.

        Args:
            value: Value to search for
            set_column: SET column or expression to search in

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_set_contains(self, column: str, values: List[str]) -> Tuple[str, tuple]:
        """Format SET contains check expression.

        Args:
            column: SET column name
            values: Values to check for containment

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...


@runtime_checkable
class ClickHouseJSONFunctionSupport(JSONSupport, Protocol):
    """ClickHouse JSON function protocol.

    Feature Source: ClickHouse 5.7+

    ClickHouse JSON functions:
    - JSON_ARRAY, JSON_OBJECT
    - JSON_EXTRACT, JSON_SET, JSON_REMOVE
    - JSON_SEARCH, JSON_CONTAINS, JSON_KEYS

    Official Documentation:
    - JSON Functions: https://dev.clickhouse.com/doc/refman/8.0/en/json-functions.html

    Version Requirements:
    - JSON type: ClickHouse 5.7+
    - JSONTABLE: ClickHouse 8.0.4+
    """

    def supports_json_type(self) -> bool:
        """Whether JSON data type is supported (ClickHouse 5.7+)."""
        ...

    def supports_json_merge_patch(self) -> bool:
        """Whether JSON_MERGE_PATCH is supported (ClickHouse 8.0.3+)."""
        ...

    def supports_json_table(self) -> bool:
        """Whether JSON_TABLE is supported (ClickHouse 8.0.4+)."""
        ...

    def supports_json_function(self, function_name: str) -> bool:
        """Whether a specific JSON function is supported.

        Args:
            function_name: Name of the JSON function (e.g. 'json_extract')

        Returns:
            True if the function is supported
        """
        ...

    def format_json_extract(self, json_doc: str, path: str, paths: Optional[List[str]] = None) -> Tuple[str, tuple]:
        """Format JSON_EXTRACT function call.

        Args:
            json_doc: JSON document or column
            path: JSON path expression
            paths: Additional path expressions (ClickHouse 5.7.9+ multi-path)

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_json_unquote(self, json_val: str) -> Tuple[str, tuple]:
        """Format JSON_UNQUOTE function call.

        Args:
            json_val: JSON value to unquote

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_json_object(self, key_value_pairs: List[Tuple[str, Any]]) -> Tuple[str, tuple]:
        """Format JSON_OBJECT function call.

        Args:
            key_value_pairs: List of (key, value) tuples

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_json_array(self, values: List[Any]) -> Tuple[str, tuple]:
        """Format JSON_ARRAY function call.

        Args:
            values: Values to include in the JSON array

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_json_contains(self, target: str, candidate: str, path: Optional[str] = None) -> Tuple[str, tuple]:
        """Format JSON_CONTAINS function call.

        Args:
            target: JSON document or column to search in
            candidate: JSON value to search for
            path: Optional path within the target document

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_json_set(
        self, json_doc: str, path: str, value: Any, path_value_pairs: Optional[List[Tuple[str, Any]]] = None
    ) -> Tuple[str, tuple]:
        """Format JSON_SET function call.

        Args:
            json_doc: JSON document or column
            path: JSON path expression
            value: Value to set at the path
            path_value_pairs: Additional (path, value) pairs

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_json_remove(self, json_doc: str, path: str, paths: Optional[List[str]] = None) -> Tuple[str, tuple]:
        """Format JSON_REMOVE function call.

        Args:
            json_doc: JSON document or column
            path: JSON path to remove
            paths: Additional paths to remove

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_json_type(self, json_val: str) -> Tuple[str, tuple]:
        """Format JSON_TYPE function call.

        Args:
            json_val: JSON value to type-check

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_json_valid(self, json_val: str) -> Tuple[str, tuple]:
        """Format JSON_VALID function call.

        Args:
            json_val: Value to check for valid JSON

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_json_search(
        self, json_doc: str, search_str: str, path: Optional[str] = None, all: bool = False
    ) -> Tuple[str, tuple]:
        """Format JSON_SEARCH function call.

        Args:
            json_doc: JSON document or column to search in
            search_str: Search string (supports % and _ wildcards)
            path: Optional path to search within
            all: If True, return all matches; if False, return first match

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...


@runtime_checkable
class ClickHouseSpatialSupport(Protocol):
    """ClickHouse spatial data type protocol.

    Feature Source: ClickHouse 5.7+ with InnoDB, all versions with MyISAM

    ClickHouse spatial features:
    - SPATIAL data types: GEOMETRY, POINT, LINESTRING, POLYGON, etc.
    - Spatial indexes (only for MyISAM with NOT NULL)
    - SPATIAL KEY/MULTIPLE KEY for indexes

    Official Documentation:
    - Spatial Data Types: https://dev.clickhouse.com/doc/refman/8.0/en/spatial-type.html

    Version Requirements:
    - Basic spatial types: ClickHouse 5.7+ (InnoDB), all versions (MyISAM)
    - Spatial index restrictions: ClickHouse 5.7.5+ for correct SRID handling
    """

    def supports_spatial_type(self, type_name: str) -> bool:
        """Whether a specific spatial data type is supported.

        Args:
            type_name: Spatial type name (e.g. 'POINT', 'LINESTRING')

        Returns:
            True if the spatial type is supported
        """
        ...

    def supports_spatial_index(self) -> bool:
        """Whether SPATIAL index is supported."""
        ...

    def supports_geojson(self) -> bool:
        """Whether GeoJSON functions (ST_AsGeoJSON) are supported (ClickHouse 5.7+)."""
        ...

    def supports_geometry_type(self) -> bool:
        """Whether GEOMETRY type is supported."""
        ...

    def supports_point_type(self) -> bool:
        """Whether POINT type is supported."""
        ...

    def supports_curve_type(self) -> bool:
        """Whether curve types (LINESTRING, MULTILINESTRING) are supported."""
        ...

    def supports_surface_type(self) -> bool:
        """Whether surface types (POLYGON, MULTIPOLYGON) are supported."""
        ...

    def supports_geometry_collection_type(self) -> bool:
        """Whether GEOMETRYCOLLECTION is supported."""
        ...

    def format_spatial_literal(self, wkt: str, srid: Optional[int] = None) -> Tuple[str, tuple]:
        """Format spatial literal from WKT.

        Args:
            wkt: Well-Known Text representation
            srid: Optional Spatial Reference System Identifier

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_st_geom_from_text(self, wkt: str, srid: Optional[int] = None) -> Tuple[str, tuple]:
        """Format ST_GeomFromText function call.

        Args:
            wkt: Well-Known Text representation
            srid: Optional Spatial Reference System Identifier

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_st_geom_from_wkb(self, wkb: bytes, srid: Optional[int] = None) -> Tuple[str, tuple]:
        """Format ST_GeomFromWKB function call.

        Args:
            wkb: Well-Known Binary representation
            srid: Optional Spatial Reference System Identifier

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_st_as_text(self, geom: str) -> Tuple[str, tuple]:
        """Format ST_AsText function call.

        Args:
            geom: Geometry column or expression

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_st_as_geojson(self, geom: str) -> Tuple[str, tuple]:
        """Format ST_AsGeoJSON function call.

        Args:
            geom: Geometry column or expression

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_st_distance(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        """Format ST_Distance function call.

        Args:
            geom1: First geometry
            geom2: Second geometry

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_st_within(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        """Format ST_Within function call.

        Args:
            geom1: Geometry to test
            geom2: Geometry to test against

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_st_contains(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        """Format ST_Contains function call.

        Args:
            geom1: Geometry to test
            geom2: Geometry to test against

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_create_spatial_index(self, index: str, table: str, column: str) -> Tuple[str, tuple]:
        """Format CREATE SPATIAL INDEX statement.

        Args:
            index: Index name
            table: Table name
            column: Column name

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...


@runtime_checkable
class ClickHouseVectorSupport(Protocol):
    """ClickHouse vector data type protocol.

    Feature Source: ClickHouse 8.0+ (optional feature in 8.0.16+, GA in 8.0.17+)

    ClickHouse vector features:
    - VECTOR data type for embedding vectors
    - Vector operations and functions

    Official Documentation:
    - Vector Type: https://dev.clickhouse.com/doc/refman/8.0/en/vector-type.html

    Version Requirements:
    - VECTOR type: ClickHouse 8.0.16+ (experimental), 8.0.17+ (GA)
    """

    def supports_vector_type(self) -> bool:
        """Whether VECTOR data type is supported (ClickHouse 8.0.17+)."""
        ...

    def supports_vector_index(self) -> bool:
        """Whether vector index is supported (ClickHouse 8.0.17+)."""
        ...

    def get_max_vector_dimension(self) -> int:
        """Get the maximum supported vector dimension.

        Returns:
            Maximum number of dimensions supported for VECTOR type
        """
        ...

    def format_vector_literal(self, values: List[float]) -> Tuple[str, tuple]:
        """Format vector literal from a list of float values.

        Args:
            values: List of float values representing the vector

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_string_to_vector(self, vector_str: str) -> Tuple[str, tuple]:
        """Format STRING_TO_VECTOR function call.

        Args:
            vector_str: String representation of a vector

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_vector_to_string(self, vector_col: str) -> Tuple[str, tuple]:
        """Format VECTOR_TO_STRING function call.

        Args:
            vector_col: Vector column or expression

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_vector_dim(self, vector_col: str) -> Tuple[str, tuple]:
        """Format VECTOR_DIM function call to get vector dimension.

        Args:
            vector_col: Vector column or expression

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_distance_euclidean(self, vector1: str, vector2: str) -> Tuple[str, tuple]:
        """Format EUCLIDEAN_DISTANCE function call.

        Args:
            vector1: First vector
            vector2: Second vector

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_distance_cosine(self, vector1: str, vector2: str) -> Tuple[str, tuple]:
        """Format COSINE_DISTANCE function call.

        Args:
            vector1: First vector
            vector2: Second vector

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_distance_dot(self, vector1: str, vector2: str) -> Tuple[str, tuple]:
        """Format DOT_PRODUCT function call.

        Args:
            vector1: First vector
            vector2: Second vector

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_create_vector_index(self, index: str, table: str, column: str) -> Tuple[str, tuple]:
        """Format CREATE VECTOR INDEX statement.

        Args:
            index: Index name
            table: Table name
            column: Column name

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...


@runtime_checkable
class ClickHouseFullTextSearchSupport(IndexSupport, Protocol):
    """ClickHouse full-text search protocol.

    Note: Most interfaces are defined in generic IndexSupport protocol.
    This protocol only defines ClickHouse-specific interfaces.

    Feature Source: ClickHouse 5.6+

    ClickHouse full-text features:
    - FULLTEXT index on CHAR, VARCHAR, TEXT columns
    - FULLTEXT index on multiple columns
    - Natural language, Boolean, Query expansion modes
    - IN NATURAL LANGUAGE MODE, IN BOOLEAN MODE, WITH QUERY EXPANSION
    - Stopwords, minimum word length

    Official Documentation:
    - Full-Text Search Functions: https://dev.clickhouse.com/doc/refman/8.0/en/fulltext-search.html

    Version Requirements:
    - FULLTEXT index: ClickHouse 5.6+ (InnoDB), all versions (MyISAM)
    - FULLTEXT parser: ClickHouse 5.1+
    - IN BOOLEAN MODE: ClickHouse 5.6+
    - WITH QUERY EXPANSION: ClickHouse 5.6.7+
    """

    def supports_fulltext_index(self) -> bool:
        """Whether FULLTEXT index is supported (ClickHouse 5.6+ InnoDB)."""
        ...

    def supports_fulltext_search(self) -> bool:
        """Whether ``MATCH ... AGAINST`` querying is supported (ClickHouse 5.6+).

        ClickHouse couples DDL and query capabilities — a FULLTEXT index
        enables MATCH ... AGAINST. This delegates to
        :meth:`supports_fulltext_index`.
        """
        ...

    def supports_fulltext_parser(self) -> bool:
        """Whether custom full-text parser plugins are supported (ClickHouse 5.1+)."""
        ...

    def supports_fulltext_query_expansion(self) -> bool:
        """Whether query expansion mode is supported (ClickHouse 5.6.7+)."""
        ...

    def format_match_against(
        self, columns: List[str], search_string: str, mode: Optional[str] = None
    ) -> Tuple[str, tuple]:
        """Format MATCH ... AGAINST expression.

        Args:
            columns: Column names to search
            search_string: Search string
            mode: Search mode (None, 'NATURAL_LANGUAGE', 'BOOLEAN', 'QUERY_EXPANSION')

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_fulltext_index_options(
        self, index: str, columns: List[str], index_type: Optional[str] = None, parser_name: Optional[str] = None
    ) -> Tuple[str, tuple]:
        """Format FULLTEXT index options.

        Args:
            index: Index name (usually 'FULLTEXT')
            columns: Indexed columns
            index_type: Index type (BTREE, HASH - ignored for FULLTEXT)
            parser_name: Parser name for full-text search

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...


@runtime_checkable
class ClickHouseLockingSupport(LockingSupport, Protocol):
    """ClickHouse row-level locking protocol.

    Feature Source: ClickHouse native (FOR UPDATE all versions, FOR SHARE ClickHouse 8.0+)

    ClickHouse locking features beyond SQL standard:
    - FOR SHARE: Shared lock (ClickHouse 8.0+, replaces LOCK IN SHARE MODE)
    - NOWAIT: Fail immediately if rows are locked (ClickHouse 8.0+)
    - SKIP LOCKED: Skip locked rows (ClickHouse 8.0+)

    Note: ClickHouse does NOT support PostgreSQL's FOR NO KEY UPDATE or
    FOR KEY SHARE lock strengths.

    Official Documentation:
    - SELECT ... FOR UPDATE: https://dev.clickhouse.com/doc/refman/8.0/en/innodb-locking-reads.html
    - LOCK IN SHARE MODE: https://dev.clickhouse.com/doc/refman/8.0/en/innodb-locking-reads.html

    Version Requirements:
    - FOR UPDATE: All ClickHouse versions
    - FOR SHARE (replacing LOCK IN SHARE MODE): ClickHouse 8.0+
    - NOWAIT: ClickHouse 8.0+
    - SKIP LOCKED: ClickHouse 8.0+
    """

    def supports_for_share(self) -> bool:
        """Whether FOR SHARE clause is supported (ClickHouse 8.0+)."""
        ...

    def supports_for_update_nowait(self) -> bool:
        """Whether FOR UPDATE NOWAIT is supported (ClickHouse 8.0+)."""
        ...

    def supports_for_update_skip_locked(self) -> bool:
        """Whether FOR UPDATE SKIP LOCKED is supported (ClickHouse 8.0+)."""
        ...

    def format_for_update_clause(self, clause: Any) -> Tuple[str, tuple]:
        """Format ClickHouse-specific FOR UPDATE clause.

        Args:
            clause: ClickHouseForUpdateClause instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...


@runtime_checkable
class ClickHouseModifyColumnSupport(Protocol):
    """ClickHouse MODIFY COLUMN and CHANGE COLUMN protocol.

    Feature Source: ClickHouse native (not SQL standard)

    ClickHouse ALTER TABLE features beyond SQL standard:
    - MODIFY COLUMN: Redefine a column with new specification (name unchanged)
    - CHANGE COLUMN: Rename and redefine a column in one operation
    - FIRST/AFTER: Column positioning within the table

    Official Documentation:
    - ALTER TABLE: https://dev.clickhouse.com/doc/refman/8.0/en/alter-table.html

    Version Requirements:
    - MODIFY COLUMN: All ClickHouse versions
    - CHANGE COLUMN: All ClickHouse versions
    """

    def supports_modify_column(self) -> bool:
        """Whether MODIFY COLUMN is supported."""
        ...

    def supports_change_column(self) -> bool:
        """Whether CHANGE COLUMN is supported."""
        ...

    def format_modify_column_action(self, action: "ModifyColumn") -> Tuple[str, tuple]:
        """Format MODIFY COLUMN action for ALTER TABLE.

        Args:
            action: ModifyColumn action instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_change_column_action(self, action: "ChangeColumn") -> Tuple[str, tuple]:
        """Format CHANGE COLUMN action for ALTER TABLE.

        Args:
            action: ChangeColumn action instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...


@runtime_checkable
class ClickHouseJsonDualityViewSupport(Protocol):
    """ClickHouse JSON Duality View protocol (ClickHouse 9.7+).

    Feature Source: ClickHouse 9.7.0 (2026-04-21)

    JSON Duality Views provide a document-relational duality layer:
    - CREATE JSON RELATIONAL DUALITY VIEW with JSON_DUALITY_OBJECT
    - WITH(INSERT,UPDATE,DELETE) annotations per object level
    - DML via single JSON `data` column
    - Optimistic locking via _metadata.etag on UPDATE

    Official Documentation:
    - JSON Duality Views: https://dev.clickhouse.com/doc/refman/9.7/en/json-duality-views.html

    Version Requirements:
    - JSON Duality Views: ClickHouse 9.7.0+
    """

    def supports_json_duality_view(self) -> bool:
        """Whether JSON Duality Views are supported (ClickHouse 9.7+)."""
        ...

    def supports_json_duality_view_dml(self) -> bool:
        """Whether DML on JSON Duality Views is supported (ClickHouse 9.7+)."""
        ...

    def format_create_json_duality_view_statement(self, expr: "CreateJsonDualityViewExpression") -> Tuple[str, tuple]:
        """Format CREATE JSON RELATIONAL DUALITY VIEW statement.

        Args:
            expr: CreateJsonDualityViewExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        ...

    def format_drop_json_duality_view_statement(self, expr: "DropJsonDualityViewExpression") -> Tuple[str, tuple]:
        """Format DROP VIEW statement for a JSON Duality View."""
        ...

    def format_duality_object_select(self, spec: Any) -> str:
        """Format SELECT JSON_DUALITY_OBJECT(...) FROM table clause."""
        ...

    def format_duality_object_body(self, spec: Any) -> str:
        """Format JSON_DUALITY_OBJECT(...) body."""
        ...

    def format_nested_duality(self, nested: Any) -> str:
        """Format nested JSON_ARRAYAGG(JSON_DUALITY_OBJECT(...)) subquery."""
        ...


@runtime_checkable
class ClickHouseOptimizerHintSupport(Protocol):
    """ClickHouse optimizer hint protocol.

    Feature Source: ClickHouse 5.7+ (hint syntax), ClickHouse 9.7+ (hypergraph optimizer)

    Supports per-statement optimizer hints using /*+ ... */ syntax,
    including SET_VAR hints for controlling optimizer switches.

    Official Documentation:
    - Optimizer Hints: https://dev.clickhouse.com/doc/refman/8.0/en/optimizer-hints.html
    - SET_VAR: https://dev.clickhouse.com/doc/refman/8.0/en/optimizer-hints.html#optimizer-hints-set-var

    Version Requirements:
    - Optimizer hints: ClickHouse 5.7+
    - SET_VAR hint: ClickHouse 8.0+
    - Hypergraph optimizer: ClickHouse 9.7+ (Community Edition)
    """

    def supports_optimizer_hint(self) -> bool:
        """Whether optimizer hints (/*+ ... */) are supported."""
        ...

    def supports_hypergraph_optimizer(self) -> bool:
        """Whether the hypergraph optimizer is available (ClickHouse 9.7+)."""
        ...

    def format_optimizer_hint(self, expr: "ClickHouseOptimizerHintExpression") -> Tuple[str, tuple]:
        """Format optimizer hint expression.

        Args:
            expr: ClickHouseOptimizerHintExpression instance

        Returns:
            Tuple of (SQL hint string, parameters tuple)
        """
        ...


@runtime_checkable
class ClickHouseRenameTableSupport(Protocol):
    """ClickHouse RENAME TABLE support protocol.

    Feature Source: ClickHouse 5.0+

    ClickHouse supports atomic multi-table renames in a single statement:

        RENAME TABLE t1 TO t2 [, t3 TO t4, ...]

    Official Documentation:
    - RENAME TABLE: https://dev.clickhouse.com/doc/refman/8.0/en/rename-table.html
    """

    def supports_rename_table(self) -> bool:
        """Whether RENAME TABLE is supported."""
        ...

    def supports_multi_table_rename(self) -> bool:
        """Whether multiple rename pairs in one statement are supported."""
        ...

    def format_rename_table_statement(self, expr: "ClickHouseRenameTableExpression") -> Tuple[str, tuple]:
        """Format a ClickHouse RENAME TABLE statement."""
        ...


@runtime_checkable
class ClickHouseTableStatementSupport(Protocol):
    """ClickHouse TABLE statement / VALUES constructor support protocol.

    Feature Source: ClickHouse 8.0.19+

    Official Documentation:
    - TABLE statement: https://dev.clickhouse.com/doc/refman/8.0/en/table.html
    - VALUES statement: https://dev.clickhouse.com/doc/refman/8.0/en/values.html
    """

    def supports_table_statement(self) -> bool:
        """Whether the TABLE statement is supported."""
        ...

    def supports_values_table_constructor(self) -> bool:
        """Whether VALUES as a table value constructor is supported."""
        ...

    def format_table_statement(self, expr: "ClickHouseTableExpression") -> Tuple[str, tuple]:
        """Format a TABLE statement."""
        ...

    def format_values_statement(self, expr: "ClickHouseValuesExpression") -> Tuple[str, tuple]:
        """Format a VALUES table value constructor."""
        ...


@runtime_checkable
class ClickHouseMaintenanceSupport(Protocol):
    """ClickHouse whole-table maintenance statements support protocol.

    Feature Source: ClickHouse native

    Covers ANALYZE / CHECK / CHECKSUM / OPTIMIZE / REPAIR TABLE (whole-table,
    distinct from the partition-level variants).

    Official Documentation:
    - Table maintenance: https://dev.clickhouse.com/doc/refman/8.0/en/table-maintenance-sql.html
    """

    def supports_analyze_table(self) -> bool:
        """Whether ANALYZE TABLE is supported."""
        ...

    def supports_check_table(self) -> bool:
        """Whether CHECK TABLE is supported."""
        ...

    def supports_checksum_table(self) -> bool:
        """Whether CHECKSUM TABLE is supported."""
        ...

    def supports_optimize_table(self) -> bool:
        """Whether OPTIMIZE TABLE is supported."""
        ...

    def supports_repair_table(self) -> bool:
        """Whether REPAIR TABLE is supported."""
        ...

    def format_table_maintenance_statement(self, expr) -> Tuple[str, tuple]:
        """Format a whole-table maintenance statement."""
        ...


@runtime_checkable
class ClickHouseRoutineSupport(Protocol):
    """ClickHouse stored routine support protocol.

    Feature Source: ClickHouse 5.0+

    Covers CREATE/DROP PROCEDURE, CREATE/DROP FUNCTION (stored), and CALL.

    Official Documentation:
    - Stored routines: https://dev.clickhouse.com/doc/refman/8.0/en/stored-programs-views.html
    - CALL: https://dev.clickhouse.com/doc/refman/8.0/en/call.html
    """

    def supports_procedure(self) -> bool:
        """Whether stored procedures are supported."""
        ...

    def supports_stored_function(self) -> bool:
        """Whether stored functions are supported."""
        ...

    def supports_call(self) -> bool:
        """Whether CALL is supported."""
        ...

    def format_create_procedure_statement(self, expr: "ClickHouseCreateProcedureExpression") -> Tuple[str, tuple]:
        """Format CREATE PROCEDURE."""
        ...

    def format_drop_procedure_statement(self, expr: "ClickHouseDropProcedureExpression") -> Tuple[str, tuple]:
        """Format DROP PROCEDURE."""
        ...

    def format_create_function_statement(self, expr: "ClickHouseCreateFunctionExpression") -> Tuple[str, tuple]:
        """Format CREATE FUNCTION (stored function)."""
        ...

    def format_drop_function_statement(self, expr: "ClickHouseDropFunctionExpression") -> Tuple[str, tuple]:
        """Format DROP FUNCTION."""
        ...

    def format_call_statement(self, expr: "ClickHouseCallExpression") -> Tuple[str, tuple]:
        """Format CALL."""
        ...


@runtime_checkable
class ClickHouseLoadXMLSupport(Protocol):
    """ClickHouse LOAD XML statement support protocol.

    Feature Source: ClickHouse 5.0+

    Official Documentation:
    - LOAD XML: https://dev.clickhouse.com/doc/refman/8.0/en/load-xml.html
    """

    def supports_load_xml(self) -> bool:
        """Whether LOAD XML is supported."""
        ...

    def format_load_xml_statement(self, expr: "ClickHouseLoadXMLEXpression") -> Tuple[str, tuple]:
        """Format a LOAD XML statement."""
        ...


@runtime_checkable
class ClickHouseAdminCommandSupport(Protocol):
    """ClickHouse administrative / utility command support protocol.

    Feature Source: ClickHouse native (instance administration)

    Covers FLUSH, RESET, CACHE INDEX, LOAD INDEX INTO CACHE, INSTALL /
    UNINSTALL COMPONENT / PLUGIN, CLONE, RESTART, BINLOG, HANDLER, DO,
    KILL, SHUTDOWN, HELP, and account management (CREATE/DROP USER, GRANT,
    REVOKE).

    Official Documentation:
    - Administrative statements: https://dev.clickhouse.com/doc/refman/8.0/en/sql-statements.html#sql-statements-administrative
    """

    def supports_flush(self) -> bool:
        ...

    def format_flush_statement(self, expr: "ClickHouseFlushExpression") -> Tuple[str, tuple]:
        ...

    def supports_reset(self) -> bool:
        ...

    def format_reset_statement(self, expr: "ClickHouseResetExpression") -> Tuple[str, tuple]:
        ...

    def supports_cache_index(self) -> bool:
        ...

    def format_cache_index_statement(self, expr: "ClickHouseCacheIndexExpression") -> Tuple[str, tuple]:
        ...

    def supports_load_index_into_cache(self) -> bool:
        ...

    def format_load_index_into_cache_statement(
        self, expr: "ClickHouseLoadIndexIntoCacheExpression"
    ) -> Tuple[str, tuple]:
        ...

    def supports_install_component(self) -> bool:
        ...

    def format_install_component_statement(self, expr: "ClickHouseInstallComponentExpression") -> Tuple[str, tuple]:
        ...

    def supports_uninstall_component(self) -> bool:
        ...

    def format_uninstall_component_statement(
        self, expr: "ClickHouseUninstallComponentExpression"
    ) -> Tuple[str, tuple]:
        ...

    def supports_install_plugin(self) -> bool:
        ...

    def format_install_plugin_statement(self, expr: "ClickHouseInstallPluginExpression") -> Tuple[str, tuple]:
        ...

    def supports_uninstall_plugin(self) -> bool:
        ...

    def format_uninstall_plugin_statement(self, expr: "ClickHouseUninstallPluginExpression") -> Tuple[str, tuple]:
        ...

    def supports_clone(self) -> bool:
        ...

    def format_clone_statement(self, expr: "ClickHouseCloneExpression") -> Tuple[str, tuple]:
        ...

    def supports_restart(self) -> bool:
        ...

    def format_restart_statement(self, expr: "ClickHouseRestartExpression") -> Tuple[str, tuple]:
        ...

    def supports_binlog(self) -> bool:
        ...

    def format_binlog_statement(self, expr: "ClickHouseBinlogExpression") -> Tuple[str, tuple]:
        ...

    def supports_handler(self) -> bool:
        ...

    def format_handler_open_statement(self, expr: "ClickHouseHandlerOpenExpression") -> Tuple[str, tuple]:
        ...

    def format_handler_read_statement(self, expr: "ClickHouseHandlerReadExpression") -> Tuple[str, tuple]:
        ...

    def format_handler_close_statement(self, expr: "ClickHouseHandlerCloseExpression") -> Tuple[str, tuple]:
        ...

    def supports_do(self) -> bool:
        ...

    def format_do_statement(self, expr: "ClickHouseDoExpression") -> Tuple[str, tuple]:
        ...

    def supports_kill(self) -> bool:
        ...

    def format_kill_statement(self, expr: "ClickHouseKillExpression") -> Tuple[str, tuple]:
        ...

    def supports_shutdown(self) -> bool:
        ...

    def format_shutdown_statement(self, expr: "ClickHouseShutdownExpression") -> Tuple[str, tuple]:
        ...

    def supports_help(self) -> bool:
        ...

    def format_help_statement(self, expr: "ClickHouseHelpExpression") -> Tuple[str, tuple]:
        ...

    def supports_create_user(self) -> bool:
        ...

    def format_create_user_statement(self, expr: "ClickHouseCreateUserExpression") -> Tuple[str, tuple]:
        ...

    def supports_drop_user(self) -> bool:
        ...

    def format_drop_user_statement(self, expr: "ClickHouseDropUserExpression") -> Tuple[str, tuple]:
        ...

    def supports_grant(self) -> bool:
        ...

    def format_grant_statement(self, expr: "ClickHouseGrantExpression") -> Tuple[str, tuple]:
        ...

    def supports_revoke(self) -> bool:
        ...

    def format_revoke_statement(self, expr: "ClickHouseRevokeExpression") -> Tuple[str, tuple]:
        ...
