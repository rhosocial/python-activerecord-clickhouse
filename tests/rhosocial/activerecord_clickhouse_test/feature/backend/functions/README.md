# tests/.../feature/backend/functions/

SQL function support declarations and JSON function rendering (pure
expression-level).

- `test_dialect_function_support.py` — `SQLFunctionSupport` protocol on
  ClickHouseDialect: `supports_functions()` returns a complete bool map,
  core functions always supported, version-dependent ClickHouse functions
  gated by server version, XML constructor rejection.
- `test_json_functions.py` — JSON function capability flags
  (JSONExtract/JSONValue supported, JSONType, JSON_TABLE never) and
  formatting of extract/unquote/object/array function calls.
- `test_seconds_between_live.py` — `seconds_between` executed for real:
  sign, fraction, month/year boundaries and two-column spans. **Requires a
  live ClickHouse**.
