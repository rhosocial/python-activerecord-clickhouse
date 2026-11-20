# Chapter 8 — Introspection

[`introspect.py`](introspect.py) asks the connected server what it knows, through
`backend.introspector`. It creates a small partitioned table first so the
table-scoped reads have something to report.

The reads shown, in order:

- `backend.dialect.supports_*()` probes — the switches that gate each
  introspection family (the same ones the CLI consults);
- `introspector.get_database_info()` — the `system.databases` row;
- `introspector.list_tables()` and `introspector.get_table_info(table)` —
  table and column declarations from `system.tables` / `system.columns`;
- `introspector.list_partitions(table)` and
  `introspector.get_table_engine(table)` — this backend's own families, which
  take `database=` because ClickHouse has no schema layer beneath a database;
- `introspector.list_functions("toYYYYMM")` — a server-wide catalogue read.

The script calls `backend.introspect_and_adapt()` before asking the probes, so
the answers are evaluated against the connected server's adapted dialect. A
family whose switch answers `False` means "this server cannot answer the
question", never "the answer was empty".

Related docs: [Database introspection](../../en_US/introspection/README.md),
[CLI usage](../../en_US/cli/README.md).
