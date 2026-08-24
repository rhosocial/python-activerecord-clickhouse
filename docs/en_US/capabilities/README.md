# Capabilities

This section covers the key runtime behaviors and capability boundaries of the ClickHouse backend.

- [Client-side snowflake IDs](snowflake_ids.md): ClickHouse has no AUTO_INCREMENT; IDs are generated client-side
- [Mutations (UPDATE/DELETE)](mutations.md): `mutations_sync=1` and `affected_rows` semantics
- [Unsupported features](unsupported.md): complete fail-fast list with alternatives
