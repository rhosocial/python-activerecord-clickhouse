# tests/.../feature/backend/query/

Query execution and EXPLAIN features (mostly require a live ClickHouse).

- `test_explain.py` — EXPLAIN protocol conformance and ClickHouse variants
  (EXPLAIN ANALYZE, EXPLAIN PIPELINE): result shape, rows/SQL/duration
  fields. **Requires a live ClickHouse**.
- `test_query_features.py` — SELECT-side feature matrix executed for real:
  CTE/recursive CTE, window functions and frame clauses, ROLLUP/CUBE,
  UNION/INTERSECT/EXCEPT, LIMIT/OFFSET. **Requires a live ClickHouse**.
