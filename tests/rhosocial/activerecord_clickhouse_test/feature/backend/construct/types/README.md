# tests/.../feature/backend/types/

ClickHouse native type round-trip tests through the backend.

- `test_native_types.py` — create tables with native ClickHouse column
  types (UInt/Int, Float, Decimal, String/FixedString, Date/DateTime64,
  Bool, UUID, Array, Map, Nullable), insert values, and read them back;
  also asserts the dialect's native-type capability switches. **Requires a
  live ClickHouse**.
