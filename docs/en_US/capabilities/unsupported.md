# Unsupported features

This backend always fails fast (`UnsupportedFeatureError`) on features ClickHouse does not support, without silent emulation. The tables below are the complete list with alternatives.

## Transactions & constraints

| Feature | Behavior | Alternative |
|------|------|------|
| ACID cross-statement transactions | `transaction()` is a no-op; rollback raises | design per-part atomic mutations |
| `FOREIGN KEY` | not generated in DDL — **and note the server accepts one spelling without effect; see below** | maintain referential integrity at the application layer |
| `UNIQUE` constraint | not generated in DDL, and the server rejects it outright | `ReplacingMergeTree` dedup |
| Triggers | raise | — |
| Sequences | raise | client-side snowflake id |

## DML / Locks

| Feature | Behavior | Alternative |
|------|------|------|
| UPSERT / `ON CONFLICT` / `INSERT IGNORE` / `REPLACE INTO` | raise | `ReplacingMergeTree` + explicit `INSERT` |
| `FOR UPDATE` row lock | raise | OLAP does not do pessimistic locking |
| `FOR SHARE` / `NOWAIT` / `SKIP LOCKED` | raise | same as above |

## Indexes & full-text

| Feature | Behavior | Alternative |
|------|------|------|
| `FULLTEXT` index | raise | `text` inverted index + `hasAllTokens`/`hasAnyTokens` |
| `MATCH ... AGAINST` | raise | same as above |
| `JSON_TABLE` | raise | `JSONExtract*` / `arrayJoin` |
| SQL-standard spatial indexes | raise | skip indexes |

ClickHouse's own full-text facility is the `text` inverted index (GA from 26.2).
It is a skip index, so it is declared through `storage_options` like any other:

```sql
CREATE TABLE docs (
    body String,
    INDEX idx_body body TYPE text(tokenizer = splitByNonAlpha) GRANULARITY 4
) ENGINE = MergeTree ORDER BY tuple();

SELECT * FROM docs WHERE hasAllTokens(body, ['clickhouse', 'index']);
```

Two details worth knowing, both measured on 26.7.3.19 and both recorded in
<https://clickhouse.com/docs/reference/engines/table-engines/mergetree-family/textindexes>:

- `tokenbf_v1` and `ngrambf_v1` are **deprecated for full-text search from
  26.2**. The server still accepts them — `CREATE TABLE ... INDEX i body TYPE
  tokenbf_v1(32768, 3, 0)` succeeds and `hasToken(body, 'beta')` still matches —
  so an existing table keeps working, but new work should use `text`.
- `splitByNonAlpha` is case-sensitive. Add `preprocessor = lower(<col>)` for
  case-insensitive matching, otherwise `hasAnyTokens(body, ['fox'])` misses
  `'Fox'`.

## Types

| Feature | Behavior | Alternative |
|------|------|------|
| Spatial types (`GEOMETRY`/`POINT`/...) | raise | a `Geometry` / `Point` column, or WKT as `String` |
| `ST_*` function family | raise | the 7 `ST_*` names ClickHouse has (WKB/MVT codecs) plus `geoDistance` |
| MySQL 9.0 `VECTOR` type | not offered — the API is absent | `ClickHouseVectorType` → `QBit(Float32, n)`, or `Array(Float32)` |
| `STRING_TO_VECTOR`/`VECTOR_TO_STRING`/`VECTOR_DIM`/`DISTANCE_*` | not offered — the API is absent | `L2Distance`/`cosineDistance`/`dotProduct` |
| `SET` type | raise | `Enum16` or `Array(String)` |
| `FIND_IN_SET` | raise | `has()`/`indexOf()` |

On the two spatial rows, measured on 26.7.3.19: ClickHouse **does** have
`Geometry` and `Point` column types (`CREATE TABLE t (g Geometry) ENGINE =
MergeTree` is accepted) and exactly seven `ST_*` functions — `ST_AsMVT`,
`ST_AsMVTGeom`, `ST_LineFromWKB`, `ST_MLineFromWKB`, `ST_PolyFromWKB`,
`ST_MPolyFromWKB`, `ST_PointFromWKB` — every one of them a WKB / MVT codec.
What is absent is the OGC surface this backend's `ST_*` mixin would emit:
`ST_Distance` / `ST_AsText` answer `UNKNOWN_FUNCTION`, and WKT parsing for the
`Geometry` type answers `Cannot parse text value of type Geometry here:
POINT(1 2)`. `geoDistance(lon1, lat1, lon2, lat2)` is the distance helper that
does exist.

## Statements

| Feature | Behavior | Alternative |
|------|------|------|
| Stored procedures / stored functions / `CALL` | raise | ClickHouse SQL UDF (`CREATE FUNCTION ... AS`) |
| `LOAD DATA INFILE` | raise | format parsers / `input()` table function |
| `LOAD XML` | raise | same as above |
| `TABLE` / `VALUES` table-value constructor (MySQL 8.0.19+) | raise | `SELECT ... UNION ALL SELECT ...` |
| Whole-table maintenance (`ANALYZE`/`CHECKSUM`/`REPAIR TABLE`) | raise. `CHECK TABLE` is the exception and *does* work — see below | `OPTIMIZE TABLE ... FINAL` or `SYSTEM` commands |
| MySQL optimizer hints (`/*+ SET_VAR */`) | raise, and the refusal is not redundant: the server **parses the comment and ignores its contents** | `SETTINGS` clause |
| JSON Relational Duality Views | raise | `JSON` type + `JSONExtract*` |
| `SHOW TABLE STATUS` / `SHOW TRIGGERS` / `SHOW CREATE TRIGGER` / `SHOW WARNINGS` / `SHOW ERRORS` / `SHOW VARIABLES` / `SHOW STATUS` / `SHOW CHARACTER SET` / `SHOW COLLATION` / `SHOW PLUGINS` | raise | the `system.*` tables each names, via `ClickHouseStatusIntrospector` |
| `SHOW [FULL] COLUMNS` / `SHOW INDEX` / `SHOW PROCESSLIST` / `SHOW ENGINES` / `SHOW GRANTS` | **not refused — these work** and are read via `backend.introspector.show.*()` | `DESCRIBE TABLE` / `system.columns`, `system.tables` + `system.data_skipping_indices`, `system.processes`, `system.table_engines`, `system.grants` if you prefer the system tables directly |

### The `SHOW` set ClickHouse actually has

Five statements in the MySQL `SHOW` set that this backend used to refuse all work
on the server, and are now rendered and parsed. Each reads the column names the
server actually sends, which differ from MySQL's in ways that fail silently
rather than loudly — a parser looking for MySQL's names returns `None` fields, not
an exception:

| statement | ClickHouse columns | differs from MySQL |
|-----------|-------------------|--------------------|
| `SHOW [FULL] COLUMNS FROM db.t` | `field`, `type`, `null`, `key`, `default`, `extra` (+ `collation`, `comment`, `privileges` under `FULL`) | `key` is `PRI SOR` / `PRI` / `''`, not `PRI`/`UNI`/`MUL`; `default` carries the expression of an `ALIAS`, `DEFAULT` **or** `MATERIALIZED` column; rows come back in **name** order, not declaration order |
| `SHOW INDEX FROM db.t` | `table`, `non_unique`, `key_name`, `seq_in_index`, `pk_col`, `collation`, `cardinality`, `sub_part`, `packed`, `null`, `index_type`, `comment`, `index_comment`, `visible`, `expression` | the indexed column is `pk_col`, not `Column_name`; `index_type` is `PRIMARY`/`MINMAX`/`BLOOM_FILTER`/…, not `BTREE` |
| `SHOW PROCESSLIST` | all 43 of `system.processes`' columns | lower-cased; there is no per-process `Command` or `State`, so those result fields are always `None`; and there is **no `FULL` variant** (`SHOW FULL PROCESSLIST` is a `SYNTAX_ERROR`) |
| `SHOW ENGINES` | `name`, eight `supports_*` flags, `description`, `syntax`, `examples`, `introduced_in`, `related` | none of MySQL's `Support`/`Transactions`/`XA`/`Savepoints` |
| `SHOW GRANTS [FOR user]` | **one column whose name is the statement text plus the output format** — `GRANTS`, `GRANTS FORMAT JSONEachRow`, `GRANTS FORMAT Native`, `GRANTS FOR root` — never MySQL's `Grants for` | so the single column's *value* is read, not a named key. `FOR user@host` is also not ClickHouse's: an access entity is a role name, and `SHOW GRANTS FOR root@localhost` is `UNKNOWN_ROLE` |

Two further statements remain refusals because the server really does not have
them: `SHOW VARIABLES` and `SHOW STATUS` — the server's grammar after `SHOW`
offers no such keyword, and the configuration lives in `system.settings` /
`system.server_settings` while runtime counters live in `system.metrics`,
`system.events` and `system.asynchronous_metrics`, all read by
`ClickHouseStatusIntrospector`. Likewise `SHOW TABLE STATUS`, `SHOW TRIGGERS`,
`SHOW CREATE TRIGGER`, `SHOW WARNINGS`, `SHOW ERRORS`, `SHOW CHARACTER SET`,
`SHOW COLLATION` and `SHOW PLUGINS`.

The inventory that proves those absences is the server's own grammar. On
26.7.3.19 the complete set of keywords `SHOW` accepts is `CREATE`, `FULL`,
`DATABASES`, `CLUSTERS`, `MERGES`, `FILESYSTEM CACHES`, `CLUSTER`, `CHANGED`,
`SETTINGS`, `TEMPORARY`, `TABLES`, `DICTIONARIES`, `EXTENDED`, `COLUMNS`,
`FIELDS`, `ENGINES`, `FUNCTIONS`, `INDEX`, `INDEXES`, `INDICES`, `KEYS`,
`SETTING`, `DATABASE`, `VIEW`, `PROCESSLIST`, `ACCESS`, `USERS`, `ROLES`,
`PROFILES`, `POLICIES`, `QUOTAS`, `MASKING POLICIES`, `CURRENT ROLES`,
`ENABLED ROLES`, `CURRENT QUOTA`, `QUOTA`, `GRANTS`, `PRIVILEGES` — no
`VARIABLES`, no `STATUS`, no `TRIGGERS`, no `PLUGINS`. See also
<https://clickhouse.com/docs/reference/statements/show>.

### FOREIGN KEY is accepted without effect

`FOREIGN KEY` is worth calling out because the server does **not** simply reject
it. Three of the four spellings are rejected outright, and the fourth — the one a
generic SQL writer is most likely to produce — is **accepted, silently discarded,
and has no effect whatsoever**. All measured on 26.7.3.19:

| spelling | result |
|----------|--------|
| `CREATE TABLE c (id UInt32, pid UInt32, FOREIGN KEY (pid) REFERENCES p(id)) ENGINE = MergeTree ORDER BY id` | **succeeds.** `SHOW CREATE TABLE c` reports no foreign key, `system.tables.create_table_query` does not contain the string `FOREIGN`, and an orphan row inserts and reads back fine |
| `CREATE TABLE c (id UInt32, CONSTRAINT fk FOREIGN KEY (id) REFERENCES p(id)) ...` | `Code: 62. Syntax error: failed at position 57 (FOREIGN) ... Expected one of: CHECK, ASSUME. (SYNTAX_ERROR)` |
| `CREATE TABLE c (id UInt32 REFERENCES p(id)) ...` (inline column reference) | `Code: 62. Syntax error: failed at position 43 (REFERENCES) ...` |
| `CREATE TABLE c (id UInt32) ENGINE = MergeTree ORDER BY id FOREIGN KEY (id) REFERENCES p(id)` (after the storage clauses) | `Code: 62. Syntax error: failed at position 75 (FOREIGN) ...` |

Dropping the referenced parent table also succeeds, and the orphan row is still
readable — so the clause is not a deferred check either, it is gone.

Two consequences for this backend:

* **Emitting it would be the worst of the three outcomes.** It would not raise,
  so the failure would surface later as missing referential integrity, in
  production data, with nothing in the server's metadata to explain it. That is
  precisely the "silent emulation" this backend's
  [design principle](../introduction/capability_boundaries.md) exists to avoid,
  and it is why `format_table_constraint` raises for `FOREIGN KEY` rather than
  rendering the clause that happens to parse.
* **"Not generated in DDL" is not the same claim as "the server rejects it."** A
  reader who assumed the second would test it by pasting `FOREIGN KEY` into a
  `CREATE TABLE` and, for the unnamed spelling, conclude the server supports it.

For contrast, the constraint forms ClickHouse *does* have are `CHECK` and
`ASSUME` (both documented at
<https://clickhouse.com/docs/reference/statements/create/table#constraints>, and
`CHECK` is enforced — an out-of-range `UInt32` is stored wrapped rather than
rejected only because the comparison is done on the stored value). And `UNIQUE
(col)` is rejected outright: `Code: 62. Syntax error: failed at position 50
(() ... Expected one of: NULL, NOT, DEFAULT, MATERIALIZED, EPHEMERAL, ALIAS,
AUTO_INCREMENT, TTL, PRIMARY KEY, data type, identifier. (SYNTAX_ERROR)`.

### CHECK TABLE works

`CHECK TABLE` is a real ClickHouse statement and this backend now emits it; it
is not in the fail-fast list above. It dispatches on the table engine, so what it
verifies depends on the engine.

## Partitioning

ClickHouse *does* partition, but not the way MySQL does: `PARTITION BY <expr>` on a
`MergeTree` table, with no strategy keyword, no `VALUES LESS THAN` /
`VALUES IN` / `MAXVALUE` boundary and no subpartitioning. The clause is declared
through `storage_options`; maintenance is by partition id
(`DROP` / `DETACH` / `ATTACH PARTITION ID`); introspection is `system.parts`.
The MySQL statements below have no ClickHouse spelling and are absent rather
than switched off one at a time — the inventory that proves the absence is
<https://clickhouse.com/docs/sql-reference/statements/alter/partition>.

| Feature | Behavior | Alternative |
|------|------|------|
| Declarative `PARTITION BY RANGE/LIST/HASH/KEY` with `PARTITION ... VALUES ...` | raise | `PARTITION BY <expr>` in `storage_options` |
| `ADD PARTITION` | raise | a partition appears when a row lands in it |
| `TRUNCATE PARTITION` | raise | `ALTER TABLE ... DELETE IN PARTITION ... WHERE ...`, or `TRUNCATE TABLE` |
| `REORGANIZE` / `EXCHANGE` / `COALESCE PARTITION`, `REMOVE PARTITIONING` | raise | `REPLACE PARTITION` / `MOVE PARTITION TO TABLE` |
| `ANALYZE`/`CHECK`/`OPTIMIZE`/`REBUILD`/`REPAIR PARTITION` | raise | `SYSTEM RESTART`/`SYSTEM RELOAD`, `OPTIMIZE TABLE ... PARTITION` |
| `SUBPARTITION BY` | raise | a tuple partition key (`PARTITION BY (a, b)`) |
| `MAXVALUE` partition boundary | raise | the partition-key value itself |
| `information_schema.PARTITIONS` | raise | `system.parts` |

## Admin commands (MySQL admin set)

`FLUSH`/`RESET`/`CACHE INDEX`/`LOAD INDEX INTO CACHE`/`INSTALL`/`UNINSTALL COMPONENT`/`PLUGIN`/`CLONE`/`RESTART`/`BINLOG`/`HANDLER`/`DO`/`KILL`/`SHUTDOWN`/`HELP` — all raise. Use ClickHouse's `SYSTEM` command family instead (`SYSTEM RELOAD`/`SYSTEM KILL`/`SYSTEM FLUSH`/...). `KILL` is not a single MySQL-shaped statement: ClickHouse's is `KILL QUERY|MUTATION|PART_MOVE_TO_SHARD|TRANSACTION ...`, and `KILL 1` answers "Expected one of: QUERY, MUTATION, PART_MOVE_TO_SHARD, TRANSACTION".

Four names on that list used to sit here and are not MySQL-only at all:
`CREATE USER`, `ALTER USER`, `DROP USER`, `GRANT` and `REVOKE` are ClickHouse's
own access-control statements and all succeed on 26.7.3.19 — the backend simply
offers no core API that emits them, so nothing in this backend routes a
`CREATE USER` to the server. Access management from the SQL console is not
blocked; only this backend's expression layer has no spelling for it.

## Async

| Feature | Behavior | Alternative |
|------|------|------|
| `AsyncClickHouseBackend` | instantiating it raises `NotImplementedError` | `ClickHouseBackend` (sync) + out-of-process concurrency |

The narrow claim is the true one: **there is no async backend class you can
build a connection with.** `AsyncClickHouseBackend(connection_config=...)` raises
`NotImplementedError` from `__init__`, because `clickhouse-connect` is a
synchronous-only driver, and `AsyncClickHouseTransactionManager` raises the same
way.

It is not true that this package ships no async code. It ships two complete
async introspectors — `AsyncClickHouseStatusIntrospector` and
`AsyncShowIntrospector` — each implementing every method of core's async status /
SHOW contracts with real `await`ed queries, none of which raises
`NotImplementedError`. They are reachable by any caller that supplies its own
async backend object (an async ClickHouse driver, or a wrapper); only the stock
`AsyncClickHouseBackend` refuses. The async test fixtures skip for that same
single reason: they have no instantiable backend to hand them.

## How to probe

```python
if dialect.supports_on_conflict_clause():
    ...   # 走 UPSERT
else:
    ...   # 走 INSERT + ReplacingMergeTree
```

Callers should probe explicitly via `supports_*` rather than `try/except UnsupportedFeatureError`, so they can switch across backends (e.g., SQLite for development, ClickHouse for production).

## Next steps

- [Capability boundaries & fail-fast](../introduction/capability_boundaries.md)
- [Mutations (UPDATE/DELETE)](mutations.md)
