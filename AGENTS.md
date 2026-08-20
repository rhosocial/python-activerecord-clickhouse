# Project Overview: rhosocial-activerecord-clickhouse

## Project Name
- **Repository Name**: python-activerecord-clickhouse
- **Python Package Name**: rhosocial-activerecord-clickhouse

## Project Purpose

This project is a ClickHouse backend implementation for the `rhosocial-activerecord` Python package. It provides ClickHouse database support with the elegant ActiveRecord pattern interface.

## Key Design Principles

1. **Backend Implementation**: Extends core ActiveRecord with ClickHouse-specific features
2. **Driver**: Uses `clickhouse-connect` (HTTP interface) for database connectivity
3. **Namespace Package**: Integrates with the rhosocial namespace package architecture
4. **Synchronous only**: clickhouse-connect is a sync-only library; no async backend is provided
5. **Fast-fail semantics**: features ClickHouse does not support (transactions, FK/UNIQUE constraints, triggers, upsert, etc.) raise `UnsupportedFeatureError` instead of being emulated

## Current Status

This project is under active development. Key features implemented:

- Basic CRUD operations
- Connection management (clickhouse-connect DB-API)
- Schema introspection (via ClickHouse `system.*` tables)
- ClickHouse-native data types (Int/UInt, Float, Decimal, String, FixedString, Date/DateTime64, Bool, UUID, IPv4/6, Enum8/16, Array/Map/Tuple, Nullable, LowCardinality, JSON)
- ClickHouse SQL dialect (ENGINE/ORDER BY/PARTITION BY/TTL clauses)
- Capability negotiation via `supports_*` switches

## Not Supported (fail fast)

- ACID transactions (no BEGIN/COMMIT/ROLLBACK)
- FOREIGN KEY / UNIQUE constraints
- Triggers, sequences
- UPSERT / ON CONFLICT / INSERT IGNORE / REPLACE INTO
- FOR UPDATE row locking
- Asynchronous backend (clickhouse-connect is sync-only)

## Python Version Support

- Python `>=3.10,<3.15` (per clickhouse-connect `Requires-Python`)

## Version Control and Changelog

This project adheres to the same version control, branching, commit message, and changelog management standards as the main `python-activerecord` project.
