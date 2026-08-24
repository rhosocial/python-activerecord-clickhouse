# Overview

## Why a ClickHouse backend

ClickHouse is a columnar OLAP database excelling at real-time analytics and
high-volume aggregation. Its worldview, however, is fundamentally different
from row-oriented OLTP databases: no transactions, no foreign keys, no unique
constraints, and mutations (UPDATE/DELETE) are asynchronous "lightweight"
operations.

Traditional ORMs integrating ClickHouse usually take one of two approaches:

1. **Pretend it is OLTP**: emulate transactions and constraints, generate SQL
   ClickHouse cannot run, and ultimately crash at runtime or produce semantically
   wrong data.
2. **Act as a query gateway only**: pass SELECTs through and abandon the modeling
   power of the ActiveRecord pattern.

`rhosocial-activerecord-clickhouse` takes a third path — **honest semantics**:

- Capabilities ClickHouse natively supports (columnar types, `ENGINE`, `ORDER BY`
  sorting key, `PARTITION BY`, TTL, `JSONExtract*`, Array/Map/Tuple, `system.*`
  introspection) are exposed as first-class citizens and generate native
  ClickHouse SQL.
- Capabilities ClickHouse does not support (ACID transactions, foreign key / unique
  constraints, triggers, UPSERT, FOR UPDATE, FULLTEXT, JSON_TABLE, spatial/vector
  types, stored routines, MySQL admin commands, etc.) are declared as `False`
  via `supports_*` capability switches; calling the corresponding `format_*`
  methods raises `UnsupportedFeatureError` fast — **never silently emulated**.

> 💡 *AI prompt: "Why does this backend choose to fail fast instead of emulating transactions? What does that mean for calling code?"*

## Core design principles

1. **Backend implementation**: extends the core ActiveRecord Expression-Dialect-Backend
   layering with ClickHouse-specific types and dialect.
2. **Driver**: uses `clickhouse-connect` (HTTP interface) as the database connection layer.
3. **Namespace package**: integrates into the core library's namespace package
   architecture as `rhosocial.activerecord.backend.impl.clickhouse`.
4. **Synchronous only**: `clickhouse-connect` is a pure sync library; this backend
   **does not provide an async backend**. `AsyncClickHouseBackend` is a placeholder
   class that fails fast on instantiation so generic import paths keep loading,
   but any instantiation raises `NotImplementedError`.
5. **Fail-fast semantics**: unsupported features raise `UnsupportedFeatureError`
   instead of degrading into silent no-ops or emulated implementations.

## When to use

- Type-safe modeling on top of ClickHouse (deep Pydantic V2 integration).
- Writing real-time analytics applications that need an ActiveRecord-style query
  builder emitting native ClickHouse SQL.
- Reusing the core library's mixins (Timestamp, optimistic locking, soft delete)
  and relations (has_one/has_many/has_many_through).
- Ops and data exploration via the CLI and `system.*` introspection.

## When not to use

- Business logic requiring ACID cross-statement transaction guarantees (ClickHouse
  mutations are per-part atomic, with no cross-statement isolation).
- Writes relying on unique constraints for deduplication (the table engine
  `ReplacingMergeTree`/`CollapsingMergeTree` should bear that responsibility).
- High-concurrency services needing async I/O (the driver is sync; for such needs,
  use a process-level connection pool with worker threads).

## Next steps

- [Relationship with the core library](relationship.md): understand the layering
  and where this backend sits.
- [Supported versions](supported_versions.md): confirm your ClickHouse and Python versions.
- [Capability boundaries & fail-fast](capability_boundaries.md): know what can and
  cannot be done before writing code.
