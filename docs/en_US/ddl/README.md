# DDL

This section covers ClickHouse table structure definition, focusing on the MergeTree family and the sorting key.

- [Table engines & sorting key](table_engine.md): `ENGINE`, `ORDER BY`, `PARTITION BY`, `TTL`
- [Skip indexes](skip_indexes.md): `INDEX ... USING` skip indexes

> ⚠️ ClickHouse's `ORDER BY` is both the sorting key and the primary key index, which differs from the "primary key = unique constraint" semantics of OLTP databases. Primary key columns **cannot be updated**.
