# src/rhosocial/activerecord/backend/impl/clickhouse/examples/conftest.py
"""
Example metadata configuration.

This file defines metadata for all examples in this directory.
The inspector reads this file to get title, dialect_protocols, and priority.

ClickHouse version support: the maintained release lines 25.8 LTS, 26.3 LTS
and 26.7 (older lines may work but are untested).

Feature notes:
- Window functions, CTE (WITH clause) and JSON access are available across
  the supported release lines via ClickHouse-native syntax
  (window frames, ``WITH``, ``JSONExtract*``).
"""

EXAMPLES_META = {
    "transaction/basic.py": {
        "title": "Transaction Awareness (ClickHouse does not support transactions)",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/cte.py": {
        "title": "CTE (Common Table Expressions)",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
        "note": "ClickHouse supports CTE (WITH clause) across maintained release lines.",
    },
    "connection/quickstart.py": {
        "title": "Connect to ClickHouse and Execute Queries",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "ddl/create_table.py": {
        "title": "Create Table",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "ddl/create_index.py": {
        "title": "Create Index",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "ddl/alter_table.py": {
        "title": "Alter Table",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "ddl/drop_table.py": {
        "title": "DROP TABLE using DropTableExpression",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "ddl/view.py": {
        "title": "CREATE VIEW",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "ddl/unique_index.py": {
        "title": "CREATE UNIQUE INDEX",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/pagination.py": {
        "title": "Pagination with LIMIT/OFFSET",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "insert/batch.py": {
        "title": "Batch Insert",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "insert/single.py": {
        "title": "Single Row Insert",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "delete/basic.py": {
        "title": "DELETE using DeleteExpression",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "update/basic.py": {
        "title": "UPDATE using UpdateExpression",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/union.py": {
        "title": "UNION using SetOperationExpression",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/distinct.py": {
        "title": "SELECT DISTINCT using SelectModifier",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/basic.py": {
        "title": "Basic SELECT Query",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/join.py": {
        "title": "JOIN Query",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/aggregate.py": {
        "title": "Aggregate Query",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/subquery.py": {
        "title": "Subquery",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/window.py": {
        "title": "Window Functions",
        "dialect_protocols": ["WindowFunctionSupport"],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "types/json_basic.py": {
        "title": "JSON Operations (JSONExtract functions)",
        "dialect_protocols": ["JSONSupport"],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/predicate.py": {
        "title": "Complex Predicates",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/constants.py": {
        "title": "Query Runtime Constants and Niladic Functions",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "query/explain.py": {
        "title": "EXPLAIN Query Plan",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "schema_diff/table_changes.py": {
        "title": "Schema Diff — Table Add/Remove",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "schema_diff/column_order.py": {
        "title": "Schema Diff — ClickHouse Column Order Awareness",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
    "schema_diff/clickhouse_schema_diff.py": {
        "title": "Schema Diff — ClickHouse Table Structure Changes",
        "dialect_protocols": [],
        "priority": 10,
        "min_version": "25.8",
        "max_version": "26.7",
    },
}
