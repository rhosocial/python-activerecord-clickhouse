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
        """Format database information query.

        NOTE: MySQL-style information_schema.SCHEMATA SQL; should be rewritten
        against ClickHouse system.databases.
        """
        params = expr.get_params()
        schema = params.get("schema", "")
        sql = (
            "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
            "FROM information_schema.SCHEMATA "
            "WHERE SCHEMA_NAME = %s"
        )
        return (sql, (schema,))

    def format_table_list_query(self, expr: "TableListExpression") -> Tuple[str, tuple]:
        """Format table list query.

        NOTE: MySQL-style information_schema.TABLES SQL; should be rewritten
        against ClickHouse system.tables.
        """
        params = expr.get_params()
        schema = params.get("schema", "")
        include_views = params.get("include_views", True)
        include_system = params.get("include_system", False)
        table_type = params.get("table_type")

        conditions = ["TABLE_SCHEMA = %s"]
        sql_params: list = [schema]

        if not include_system:
            conditions.append("TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'clickhouse', 'sys')")
        if not include_views:
            conditions.append("TABLE_TYPE = 'BASE TABLE'")
        if table_type:
            conditions.append("TABLE_TYPE = %s")
            sql_params.append(table_type)

        where = " AND ".join(conditions)
        sql = (
            "SELECT TABLE_NAME, TABLE_TYPE, TABLE_COMMENT, TABLE_ROWS, "
            "DATA_LENGTH, AUTO_INCREMENT, CREATE_TIME, UPDATE_TIME "
            f"FROM information_schema.TABLES WHERE {where}"
        )
        return (sql, tuple(sql_params))

    def format_column_info_query(self, expr: "ColumnInfoExpression") -> Tuple[str, tuple]:
        """Format column information query.

        NOTE: MySQL-style information_schema.COLUMNS SQL; should be rewritten
        against ClickHouse system.columns.
        """
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")
        sql = (
            "SELECT COLUMN_NAME, ORDINAL_POSITION, COLUMN_DEFAULT, IS_NULLABLE, "
            "DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE, "
            "COLUMN_TYPE, COLUMN_KEY, EXTRA, COLUMN_COMMENT, "
            "CHARACTER_SET_NAME, COLLATION_NAME "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION"
        )
        return (sql, (schema, table_name))

    def format_index_info_query(self, expr: "IndexInfoExpression") -> Tuple[str, tuple]:
        """Format index information query.

        NOTE: MySQL-style information_schema.STATISTICS SQL. There is no direct
        ClickHouse equivalent (skip indexes live in system.data_skipping_indices,
        which has a different schema). Still needs to be rewritten.
        """
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")
        sql = (
            "SELECT INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, "
            "INDEX_TYPE, SUB_PART, NULLABLE "
            "FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY INDEX_NAME, SEQ_IN_INDEX"
        )
        return (sql, (schema, table_name))

    def format_foreign_key_query(self, expr: "ForeignKeyExpression") -> Tuple[str, tuple]:
        """Format foreign key information query.

        NOTE: MySQL-style information_schema SQL. ClickHouse has no foreign keys,
        so this has no system-table equivalent. The supporting capability is off
        (supports_foreign_key_introspection() returns False); this SQL should be
        removed or turned into an UnsupportedFeatureError.
        """
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")
        sql = (
            "SELECT kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME, kcu.ORDINAL_POSITION, "
            "kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME, "
            "rc.UPDATE_RULE, rc.DELETE_RULE "
            "FROM information_schema.KEY_COLUMN_USAGE kcu "
            "JOIN information_schema.REFERENTIAL_CONSTRAINTS rc "
            "  ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME "
            "  AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA "
            "WHERE kcu.TABLE_SCHEMA = %s AND kcu.TABLE_NAME = %s "
            "  AND kcu.REFERENCED_TABLE_NAME IS NOT NULL "
            "ORDER BY kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
        )
        return (sql, (schema, table_name))

    def format_view_list_query(self, expr: "ViewListExpression") -> Tuple[str, tuple]:
        """Format view list query.

        NOTE: MySQL-style information_schema.VIEWS SQL; should be rewritten
        against ClickHouse system.views.
        """
        params = expr.get_params()
        schema = params.get("schema", "")
        include_system = params.get("include_system", False)

        conditions = ["TABLE_SCHEMA = %s"]
        sql_params: list = [schema]

        if not include_system:
            conditions.append("TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'clickhouse', 'sys')")

        where = " AND ".join(conditions)
        sql = (
            "SELECT TABLE_NAME, VIEW_DEFINITION, CHECK_OPTION, IS_UPDATABLE "
            f"FROM information_schema.VIEWS WHERE {where} "
            "ORDER BY TABLE_NAME"
        )
        return (sql, tuple(sql_params))

    def format_view_info_query(self, expr: "ViewInfoExpression") -> Tuple[str, tuple]:
        """Format single view information query.

        NOTE: MySQL-style information_schema.VIEWS SQL; should be rewritten
        against ClickHouse system.views.
        """
        params = expr.get_params()
        view_name = params.get("view_name", "")
        schema = params.get("schema", "")
        sql = (
            "SELECT TABLE_NAME, VIEW_DEFINITION, CHECK_OPTION, IS_UPDATABLE "
            "FROM information_schema.VIEWS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s"
        )
        return (sql, (schema, view_name))

    def format_trigger_list_query(self, expr: "TriggerListExpression") -> Tuple[str, tuple]:
        """Format trigger list query.

        NOTE: MySQL-style information_schema.TRIGGERS SQL. ClickHouse has no
        triggers, so this has no system-table equivalent. The supporting
        capability is off (supports_trigger_introspection() returns False);
        this SQL should be removed or turned into an UnsupportedFeatureError.
        """
        params = expr.get_params()
        table_name = params.get("table_name")
        schema = params.get("schema", "")

        conditions = ["TRIGGER_SCHEMA = %s"]
        sql_params: list = [schema]

        if table_name:
            conditions.append("EVENT_OBJECT_TABLE = %s")
            sql_params.append(table_name)

        where = " AND ".join(conditions)
        sql = (
            "SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE, "
            "ACTION_TIMING, ACTION_STATEMENT, CREATED "
            f"FROM information_schema.TRIGGERS WHERE {where} "
            "ORDER BY TRIGGER_NAME"
        )
        return (sql, tuple(sql_params))