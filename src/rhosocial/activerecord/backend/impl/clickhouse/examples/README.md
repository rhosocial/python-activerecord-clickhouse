# ClickHouse Backend Expression Examples

This directory contains example scripts demonstrating ClickHouse-specific expression features.

## Categories

### DDL Operations
- `ddl/create_index.py` - Create indexes on existing tables
- `ddl/alter_table.py` - Add and modify table columns

### Insert Operations
- `insert/batch.py` - Batch insert with multiple rows

### Query Operations
- `query/basic.py` - Basic SELECT queries with WHERE, ORDER BY, LIMIT
- `query/join.py` - JOIN operations
- `query/aggregate.py` - GROUP BY and HAVING clauses
- `query/subquery.py` - Subquery expressions
- `query/window.py` - Window functions
- `query/fulltext.py` - Full-text search with MATCH...AGAINST
- `query/json_table.py` - JSON_TABLE for converting JSON to relational format

### Type Operations
- `types/json_basic.py` - JSON functions (json_extract, json_unquote)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| CLICKHOUSE_HOST | localhost | ClickHouse server host |
| CLICKHOUSE_PORT | 8123 | ClickHouse server port |
| CLICKHOUSE_DATABASE | test | Database name |
| CLICKHOUSE_USERNAME | root | Username |
| CLICKHOUSE_PASSWORD | (empty) | Password |

## Running Examples

Each example is self-contained and can be run directly:

```bash
python -m rhosocial.activerecord.backend.impl.clickhouse.examples.query.basic
```

## Section Structure

Each example follows a consistent structure:
1. **SECTION: Setup** - Imports, connection, and data setup using expressions
2. **SECTION: Business Logic** - The pattern to learn
3. **SECTION: Execution** - Running the expression
4. **SECTION: Teardown** - Cleanup and disconnect
