# EXPLAIN Support

## Overview

The ClickHouse backend provides comprehensive support for the `EXPLAIN` statement, enabling query performance analysis and execution plan inspection. This feature integrates with the ActiveRecord query builder through a unified API while exposing ClickHouse-specific behaviors.

Key capabilities:
- Basic `EXPLAIN` for execution plan visualization
- `EXPLAIN ANALYZE` for actual runtime statistics (ClickHouse 8.0.18+)
- Multiple output formats: `TEXT`, `JSON` (5.6.5+), `TREE` (8.0.16+)
- Structured result parsing with `ClickHouseExplainResult`
- Index usage analysis helpers
- Full sync and async support

## Basic Usage

### Accessing EXPLAIN via Query Builder

```python
from rhosocial.activerecord.backend.expression.statements import ExplainFormat

# Simple EXPLAIN — returns ClickHouseExplainResult
result = User.query().explain().all()

# Inspect the generated SQL prefix
print(result.sql)  # EXPLAIN SELECT ...

# Print the execution time (seconds)
print(result.duration)
```

### Reading the Result Rows

```python
result = User.query().explain().all()

for row in result.rows:
    print(row.id, row.select_type, row.table, row.type)
    print("  key:", row.key, "rows:", row.rows, "extra:", row.extra)
```

Each row is a `ClickHouseExplainRow` with the following fields (corresponding to ClickHouse's 12-column output):

| Field | Type | Description |
|---|---|---|
| `id` | `Optional[int]` | Query block identifier |
| `select_type` | `Optional[str]` | Query type (`SIMPLE`, `PRIMARY`, `SUBQUERY`, etc.) |
| `table` | `Optional[str]` | Table name |
| `partitions` | `Optional[str]` | Matching partitions |
| `type` | `Optional[str]` | Join type (`ALL`, `index`, `ref`, `eq_ref`, `const`, etc.) |
| `possible_keys` | `Optional[str]` | Candidate indexes |
| `key` | `Optional[str]` | Index actually chosen |
| `key_len` | `Optional[str]` | Length of chosen key |
| `ref` | `Optional[str]` | Columns compared with the index |
| `rows` | `Optional[int]` | Estimated rows examined |
| `filtered` | `Optional[float]` | Percentage of rows filtered by table condition |
| `extra` | `Optional[str]` | Additional information (alias `Extra`) |

## Output Formats

### TEXT Format (Default)

```python
# Default — no FORMAT clause emitted
result = User.query().explain().all()
# Generates: EXPLAIN SELECT ...
```

### JSON Format (ClickHouse 5.6.5+)

```python
result = User.query().explain(format=ExplainFormat.JSON).all()
# Generates: EXPLAIN FORMAT=JSON SELECT ...
```

### TREE Format (ClickHouse 8.0.16+)

```python
result = User.query().explain(format=ExplainFormat.TREE).all()
# Generates: EXPLAIN FORMAT=TREE SELECT ...
```

**Important Notes:**
- Requesting an unsupported format on an older ClickHouse version may raise an error from the server.
- Use `backend.dialect.supports_explain_format("TREE")` to check availability before use.

## EXPLAIN ANALYZE (ClickHouse 8.0.18+)

`EXPLAIN ANALYZE` actually executes the query and returns real runtime statistics alongside cost estimates. Use it to compare estimated vs. actual row counts and timing.

```python
# Basic ANALYZE
result = User.query().explain(analyze=True).all()
# Generates: EXPLAIN ANALYZE SELECT ...

# ANALYZE with JSON format (ClickHouse 8.0.21+)
result = User.query().explain(analyze=True, format=ExplainFormat.JSON).all()
# Generates: EXPLAIN ANALYZE FORMAT=JSON SELECT ...
```

**Important Notes:**
- `EXPLAIN ANALYZE` **executes the query** against the database. Avoid using it on write statements in production without understanding the side effects.
- `EXPLAIN ANALYZE` requires ClickHouse 8.0.18+. On earlier versions the server will return an error.

## SQL Syntax Generated

ClickHouse uses a flat (non-parenthesized) option syntax, distinct from PostgreSQL's bracketed syntax:

```
EXPLAIN [ANALYZE] [FORMAT=TEXT|JSON|TREE] <statement>
```

The `ANALYZE` keyword always precedes `FORMAT`:

```python
# analyze=True only
# → EXPLAIN ANALYZE SELECT ...

# format only
# → EXPLAIN FORMAT=JSON SELECT ...

# both
# → EXPLAIN ANALYZE FORMAT=JSON SELECT ...
```

## Index Usage Analysis

`ClickHouseExplainResult` provides helpers for a quick index usage assessment based on heuristic rules derived from the `type` and `key` columns and `extra` text:

```python
result = User.query().where(User.c.email == "alice@example.com").explain().all()

usage = result.analyze_index_usage()
print(usage)  # "full_scan" | "index_with_lookup" | "covering_index"

# Convenience properties
if result.is_full_scan:
    print("Warning: full table scan detected")

if result.is_covering_index:
    print("Optimal: covering index in use")

if result.is_index_used:
    print("An index is being used")
```

### Index Usage Rules

| Condition | `analyze_index_usage()` return |
|---|---|
| `type == "ALL"` | `"full_scan"` |
| `key` is `None` (non-ALL) | `"full_scan"` |
| `key` is not `None` and `extra` contains `"Using index"` | `"covering_index"` |
| `key` is not `None`, no covering indicator | `"index_with_lookup"` |

## Async API

The async backend provides the same interface. Use `await` for the terminal method:

```python
async def analyze_queries():
    # Simple async EXPLAIN
    result = await User.query().explain().all_async()

    # ANALYZE with JSON format
    result = await User.query().explain(
        analyze=True,
        format=ExplainFormat.JSON
    ).all_async()

    for row in result.rows:
        print(row.table, row.type, row.key)
```

## Checking Format Support at Runtime

Use `dialect` methods to guard version-dependent options:

```python
dialect = backend.dialect

# Check ANALYZE support
if dialect.supports_explain_analyze():
    result = User.query().explain(analyze=True).all()

# Check a specific format
if dialect.supports_explain_format("TREE"):
    result = User.query().explain(format=ExplainFormat.TREE).all()
else:
    result = User.query().explain(format=ExplainFormat.TEXT).all()
```

## Combining EXPLAIN with Complex Queries

EXPLAIN works with the full query builder chain:

```python
# JOIN query
result = (
    User.query()
    .join(Order, User.c.id == Order.c.user_id)
    .where(User.c.status == "active")
    .explain(format=ExplainFormat.JSON)
    .all()
)

# GROUP BY / aggregate
result = (
    Order.query()
    .group_by(Order.c.user_id)
    .explain(analyze=True)
    .count(Order.c.id)
)

# Subquery
result = (
    User.query()
    .where(User.c.id.in_(Order.query().select(Order.c.user_id)))
    .explain()
    .all()
)
```

## Version Compatibility

| Feature | Minimum ClickHouse Version |
|---|---|
| Basic `EXPLAIN` | All supported versions |
| `EXPLAIN FORMAT=JSON` | 5.6.5 |
| `EXPLAIN FORMAT=TREE` | 8.0.16 |
| `EXPLAIN ANALYZE` | 8.0.18 |
| `EXPLAIN ANALYZE FORMAT=JSON` | 8.0.21 |

## API Reference

### `ExplainOptions` Fields Used by ClickHouse

| Field | Type | Default | Description |
|---|---|---|---|
| `analyze` | `bool` | `False` | Emit `ANALYZE` keyword (8.0.18+) |
| `format` | `Optional[ExplainFormat]` | `None` | Output format (`TEXT`/`JSON`/`TREE`) |

Other `ExplainOptions` fields (such as `verbose`, `buffers`, `timing`) are accepted but not emitted in the SQL by the ClickHouse dialect.

### `ClickHouseExplainResult` Methods

| Method / Property | Description |
|---|---|
| `rows` | `List[ClickHouseExplainRow]` — parsed result rows |
| `sql` | The full SQL string that was explained |
| `duration` | Query execution time in seconds |
| `raw_rows` | Raw rows as returned by the driver |
| `analyze_index_usage()` | Returns `"full_scan"`, `"index_with_lookup"`, or `"covering_index"` |
| `is_full_scan` | `True` if `analyze_index_usage() == "full_scan"` |
| `is_index_used` | `True` if any index is used |
| `is_covering_index` | `True` if a covering index is used |

### `ClickHouseDialect` Methods

| Method | Return | Description |
|---|---|---|
| `supports_explain_analyze()` | `bool` | `True` if server version ≥ 8.0.18 |
| `supports_explain_format(fmt)` | `bool` | `True` if the given format string is supported |
| `format_explain_statement(expr)` | `str` | Builds `EXPLAIN [ANALYZE] [FORMAT=X]` prefix |

## Best Practices

- **Use JSON format for programmatic analysis.** `FORMAT=JSON` provides a structured tree that is easier to parse than plain text.
- **Reserve `EXPLAIN ANALYZE` for development.** The statement executes the query, so use it only when you need actual row counts and timing figures.
- **Check format support before use.** Always call `dialect.supports_explain_format()` when targeting mixed ClickHouse version environments.
- **Combine with index analysis.** Use `result.is_full_scan` as a quick smoke test in integration tests to catch inadvertent full-table scans.

💡 *AI Prompt: Explain how to use EXPLAIN ANALYZE with JSON format on ClickHouse 8.0 to diagnose slow queries in rhosocial-activerecord.*
