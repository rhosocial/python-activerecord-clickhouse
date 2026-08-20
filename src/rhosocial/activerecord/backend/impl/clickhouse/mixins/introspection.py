# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/introspection.py
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
    from rhosocial.activerecord.backend.expression.introspection import (
        DatabaseInfoExpression,
        TableListExpression,
        ColumnInfoExpression,
        IndexInfoExpression,
        ForeignKeyExpression,
        ViewListExpression,
        ViewInfoExpression,
        TriggerListExpression,
    )


class ClickHouseIntrospectionMixin:
    """ClickHouse introspection capability declaration and query formatting.

    This mixin implements the IntrospectionSupport protocol by:
    1. Declaring which introspection features ClickHouse supports (supports_* methods)
    2. Formatting SQL queries for introspection (format_*_query methods)

    The format_*_query methods are called by Expression.to_sql() to generate
    database-specific SQL using the ClickHouse system database
    (system.databases, system.tables, system.columns, system.views,
    system.data_skipping_indices, system.parts).

    Architecture flow:
        Introspector._build_*_sql() [base class]
            → Expression(Dialect).to_sql()
                → Dialect.format_*_query() [this mixin]
                    → Returns SQL and parameters

    ClickHouse supports introspection via system tables. Foreign key and
    trigger introspection are NOT supported (ClickHouse has neither FKs nor
    triggers), so those supports_* methods return False.

    NOTE: The format_*_query methods below currently generate MySQL-style
    information_schema SQL inherited from the MySQL backend. They are known
    MySQL remnants that still need to be rewritten against ClickHouse system
    tables (system.databases / system.tables / system.columns / system.views
    / system.data_skipping_indices). index/foreign_key/trigger queries have
    no direct system-table equivalent in ClickHouse.
    """

    # ========== Capability Detection ==========

    def supports_introspection(self) -> bool:
        """ClickHouse supports introspection via system tables."""
        return True

    def supports_database_info(self) -> bool:
        """ClickHouse supports database info via system.databases."""
        return True

    def supports_table_introspection(self) -> bool:
        """ClickHouse supports table introspection via system.tables."""
        return True

    def supports_column_introspection(self) -> bool:
        """ClickHouse supports column introspection via system.columns."""
        return True

    def supports_index_introspection(self) -> bool:
        """ClickHouse supports index introspection via system.data_skipping_indices."""
        return True

    def supports_foreign_key_introspection(self) -> bool:
        """ClickHouse does not support foreign keys, so no FK introspection."""
        return False

    def supports_view_introspection(self) -> bool:
        """ClickHouse supports view introspection via system.views."""
        return True

    def supports_trigger_introspection(self) -> bool:
        """ClickHouse does not support triggers, so no trigger introspection."""
        return False

    def get_supported_introspection_scopes(self) -> List["IntrospectionScope"]:
        """Get list of supported introspection scopes."""
        from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

        return [
            IntrospectionScope.DATABASE,
            IntrospectionScope.TABLE,
            IntrospectionScope.COLUMN,
            IntrospectionScope.INDEX,
            IntrospectionScope.VIEW,
        ]

    # ========== Query Formatting ==========

    def format_database_info_query(self, expr: "DatabaseInfoExpression") -> Tuple[str, tuple]:
        """Format database information query against ClickHouse system.databases."""
        params = expr.get_params()
        schema = params.get("schema", "")
        sql = (
            "SELECT engine AS DEFAULT_CHARACTER_SET_NAME, '' AS DEFAULT_COLLATION_NAME "
            "FROM system.databases "
            "WHERE name = %s"
        )
        return (sql, (schema,))

    def format_table_list_query(self, expr: "TableListExpression") -> Tuple[str, tuple]:
        """Format table list query against ClickHouse system.tables."""
        params = expr.get_params()
        schema = params.get("schema", "")
        include_views = params.get("include_views", True)
        include_system = params.get("include_system", False)
        table_type = params.get("table_type")

        conditions = ["database = %s"]
        sql_params: list = [schema]

        if not include_system:
            conditions.append("database != 'system'")
        if not include_views:
            conditions.append("engine NOT LIKE '%%View'")
        if table_type:
            conditions.append("engine = %s")
            sql_params.append(table_type)

        where = " AND ".join(conditions)
        sql = (
            "SELECT name AS TABLE_NAME, engine AS TABLE_TYPE, "
            "comment AS TABLE_COMMENT, total_rows AS TABLE_ROWS, "
            "total_bytes AS DATA_LENGTH, 0 AS AUTO_INCREMENT, "
            "metadata_modification_time AS MODIFICATION_TIME "
            f"FROM system.tables WHERE {where} ORDER BY name"
        )
        return (sql, tuple(sql_params))

    def format_column_info_query(self, expr: "ColumnInfoExpression") -> Tuple[str, tuple]:
        """Format column information query against ClickHouse system.columns."""
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")
        sql = (
            "SELECT name AS COLUMN_NAME, position AS ORDINAL_POSITION, "
            "default_expression AS COLUMN_DEFAULT, "
            "IF(type LIKE 'Nullable(%%', 'YES', 'NO') AS IS_NULLABLE, "
            "type AS DATA_TYPE, 0 AS CHARACTER_MAXIMUM_LENGTH, "
            "numeric_precision AS NUMERIC_PRECISION, "
            "numeric_scale AS NUMERIC_SCALE, "
            "type AS COLUMN_TYPE, '' AS COLUMN_KEY, '' AS EXTRA, "
            "comment AS COLUMN_COMMENT, '' AS CHARACTER_SET_NAME, "
            "'' AS COLLATION_NAME "
            "FROM system.columns "
            "WHERE database = %s AND table = %s "
            "ORDER BY position"
        )
        return (sql, (schema, table_name))

    def format_index_info_query(self, expr: "IndexInfoExpression") -> Tuple[str, tuple]:
        """Format index information query against ClickHouse system.data_skipping_indices."""
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")
        sql = (
            "SELECT name AS INDEX_NAME, 0 AS NON_UNIQUE, 1 AS SEQ_IN_INDEX, "
            "'' AS COLUMN_NAME, type AS INDEX_TYPE, NULL AS SUB_PART, 'YES' AS NULLABLE "
            "FROM system.data_skipping_indices "
            "WHERE database = %s AND table = %s "
            "ORDER BY name"
        )
        return (sql, (schema, table_name))

    def format_foreign_key_query(self, expr: "ForeignKeyExpression") -> Tuple[str, tuple]:
        """ClickHouse has no foreign keys; raise UnsupportedFeatureError."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            "ClickHouse", "foreign key introspection",
            "ClickHouse does not support foreign keys."
        )

    def format_view_list_query(self, expr: "ViewListExpression") -> Tuple[str, tuple]:
        """Format view list query against ClickHouse system.tables (View engines)."""
        params = expr.get_params()
        schema = params.get("schema", "")
        include_system = params.get("include_system", False)

        conditions = ["database = %s", "engine LIKE '%%View'"]
        sql_params: list = [schema]

        if not include_system:
            conditions.append("database != 'system'")

        where = " AND ".join(conditions)
        sql = (
            "SELECT name AS TABLE_NAME, create_table_query AS VIEW_DEFINITION, "
            "'NONE' AS CHECK_OPTION, 'NO' AS IS_UPDATABLE "
            f"FROM system.tables WHERE {where} ORDER BY name"
        )
        return (sql, tuple(sql_params))

    def format_view_info_query(self, expr: "ViewInfoExpression") -> Tuple[str, tuple]:
        """Format single view information query against ClickHouse system.tables."""
        params = expr.get_params()
        view_name = params.get("view_name", "")
        schema = params.get("schema", "")
        sql = (
            "SELECT name AS TABLE_NAME, create_table_query AS VIEW_DEFINITION, "
            "'NONE' AS CHECK_OPTION, 'NO' AS IS_UPDATABLE "
            "FROM system.tables "
            "WHERE database = %s AND name = %s AND engine LIKE '%%View'"
        )
        return (sql, (schema, view_name))

    def format_trigger_list_query(self, expr: "TriggerListExpression") -> Tuple[str, tuple]:
        """ClickHouse has no triggers; raise UnsupportedFeatureError."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        raise UnsupportedFeatureError(
            "ClickHouse", "trigger introspection",
            "ClickHouse does not support triggers."
        )