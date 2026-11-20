# Chapter 3 — Connection

[`connect.py`](connect.py) is the minimal program: build a
`ClickHouseConnectionConfig`, hand it to `ClickHouseBackend`, connect, run two
read-only statements, and disconnect.

Run it with a server reachable through the environment variables:

```bash
CLICKHOUSE_HOST=localhost CLICKHOUSE_PORT=8123 \
CLICKHOUSE_DATABASE=test_db CLICKHOUSE_USER=root CLICKHOUSE_PASSWORD=password \
python connect.py
```

Things to notice:

- **Port 8123** is the HTTP interface `clickhouse-connect` speaks; this is not a
  native-protocol port.
- `backend.execute(sql)` returns a result whose `.data` is a list of row
  mappings — column names are the keys.
- `backend.dialect.get_server_version()` reports the version the dialect adapted
  itself to on connect.
- `backend.disconnect()` runs in a `finally` block, so the connection is closed
  even when a statement raises.

Related docs: [Connection configuration](../../en_US/installation/configuration.md),
[Quick start](../../en_US/getting_started/quick_start.md).
