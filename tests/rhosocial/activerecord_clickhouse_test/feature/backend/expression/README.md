# tests/.../feature/backend/expression/

ClickHouse-specific value-expression rendering (pure expression-level).

- `test_datetime_interval_expressions.py` — date/time expression families
  mapped to ClickHouse functions: `extract`/date-part fields, `date_trunc`,
  INTERVAL, `date_add`/`date_sub` (column and literal sources, parameter
  ordering), `dateDiff`.
- `test_json_expressions.py` — JSON expression builders: `JSONExtract`
  (basic/alias/array-path), `JSONObject` (positional and kwargs),
  `JSONArray` rendering against the ClickHouse dialect.
