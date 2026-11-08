# Database Introspection

The ClickHouse backend answers three layers of questions: what the database
declares (from `system.tables`, `system.columns` and their neighbours), what
the server keeps about itself (six operational families it is offered and
declines), and what a column's rows actually hold (three families that read
them). `backend.introspector` is the entry point for all three, and every
answer on this page is ClickHouse's own: what this engine says, not the shape
a cross-dialect consumer can expect. The contract those answers are shaped
against — what a probe promises, what a data profile carries, what an
operational family means — is the core library's to state, and this page does
not restate it.

## What ClickHouse Answers

Every question in the introspection contract has a probe on the dialect, and a
probe is a question about the server in front of you rather than about the
product. Run `backend.introspect_and_adapt()` before asking: it reads the
server's version and adapts the dialect the probes are evaluated on, so a
capability below a floor is answered for the connection in hand.

The CLI derives its type list from the same mapping, so the sixteen types it
offers and the switches behind them cannot drift apart. Ten answer `True` for
this dialect — the seven catalogue families and the three that read the rows.
The other six are offered and refused, because ClickHouse has no statistics
collector, no dependency graph and no native DDL retrieval this backend reads.
Read the `False` rows first: `False` says the question cannot be asked of this
server, never that the answer was empty or zero.

| Type | Probe | Answer | Reads | `NAME` |
|------|-------|--------|-------|--------|
| `tables` | `supports_table_introspection()` | `True` | `system.tables` | refused |
| `views` | `supports_view_introspection()` | `True` | `system.tables` (view engines) | view, optional |
| `columns` | `supports_column_introspection()` | `True` | `system.columns` | table, required |
| `indexes` | `supports_index_introspection()` | `True` | `system.data_skipping_indices` | table, required |
| `partitions` | `supports_partition_introspection()` | `True` | `system.parts`, active parts only | table, required |
| `table-engine` | `supports_table_engine_introspection()` | `True` | `system.tables` | table, required |
| `database` | `supports_database_info()` | `True` | `system.databases` | refused |
| `unused-indexes` | `supports_unused_indexes_detection()` | `False` | — | refused |
| `table-stats` | `supports_table_stats()` | `False` | — | refused |
| `runtime` | `supports_runtime_stats()` | `False` | — | refused |
| `index-stats` | `supports_index_stats()` | `False` | — | refused |
| `dependencies` | `supports_object_dependencies()` | `False` | — | object, optional |
| `ddl` | `supports_ddl_extraction()` | `False` | — | table, required |
| `column-profiles` | `supports_column_data_profile()` | `True` | the rows themselves | table, required |
| `value-samples` | `supports_column_value_sample()` | `True` | the rows themselves | table, required |
| `join-coverage` | `supports_join_coverage()` | `True` | the rows themselves, two tables | left table, required |

`partitions` and `table-engine` are this backend's own families, not core's:
each is gated on the switch declared beside it in the mixin, and each has a
result type of its own. Core's `supports_partition_info()` stays `False` by
inheritance, because there is no core partition method here for a `True` to
oblige; the CLI reads the backend's switch, not core's.

Probes with no CLI type say something too. `supports_foreign_key_introspection()`
and `supports_trigger_introspection()` answer `False` because the engine
neither declares nor enforces foreign keys and has no triggers at all — and
their types are absent from the CLI's vocabulary rather than offered and
refused, because a switch that answers `False` means "this server cannot
answer" while a missing word means "this backend never asks". The same
distinction keeps `show.*` out of `introspect`: `SHOW` and `system.*` are not
equivalent, and every type here reads `system.*`. `supports_table_storage_introspection()`
answers `True` and is the reason a table row carries `size_bytes`, read from
`system.tables.total_bytes`; `data_size_bytes` and `index_size_bytes` stay
`None`, because ClickHouse's storage is parts on disk and its skipping indices
are sparse structures the engine maintains, not a second copy of the data —
the split is a fact this engine does not keep, not a gap. `supports_extensions()`
stays `False`: this backend declares no catalogue of add-on components.

### The Six That Answer False

`unused-indexes` has nothing to read. ClickHouse keeps no per-index access
counter: its only index rows are the primary key and data skipping indices,
and neither is instrumented with "was this ever used", so there is no view
whose rows could be called unused. Answering `True` would oblige a query
formatter that does not exist here.

`table-stats` asks for per-table read and write counters, and ClickHouse keeps
none. `system.parts` describes how the data is stored — part sizes, row counts,
partition bounds — not how often a table was read, and there is no
`performance_schema` analogue to supply the difference.

`runtime` is the one of the six whose absence is a wiring choice rather than a
missing measurement: this backend exposes the engine's live gauges and counters
through its own `status` introspector over `system.metrics` and `system.events`,
and nothing here renders core's runtime family. The CLI's `runtime` type is
therefore refused rather than answered from a different shape.

`index-stats` is the other half of `unused-indexes`, and fails for the same
reason one step further: there is no counter to read even for the question
"how much", so the family has neither a source nor a query.

`dependencies` needs a catalogue that records which object depends on which.
ClickHouse declares no foreign keys, and this backend reads no dependency
graph from it, so there is no edge to return and a name cannot narrow a graph
that does not exist.

`ddl` needs text the engine retained. This backend has no reader for a
`SHOW CREATE` statement, so `get_ddl_statement()` has nothing to hand back and
the CLI's handler exits 1 when it reaches that branch. The switch stays `False`
so the branch is normally never reached; `supports_ddl_extraction_native()`
stays `False` with it.

## The Data Families Are Aggregates

Nothing in `system.*` holds a per-column distribution to read.
`system.columns` describes a column's declaration — type, default, codec,
comment — and `system.parts` describes how the data sits on disk; neither
answers how many rows are NULL in one column or how many distinct values it
holds. Every figure in a profile is therefore computed from the rows, exact,
and paid for in time: one arm per column, each a scan of the table.

The statement is one `UNION ALL` over those arms, so a table of ten columns
costs ten scans but one round trip. The aggregate is `COUNT(DISTINCT ...)`,
exact, rather than `uniq` or `uniqCombined`: those are this engine's
approximate distinct counts, and the profile has no word for what they produce
— `aggregate` would claim an exact count and `sample` would claim a subset of
rows was read, while the approximation reads every row and rounds the answer.
The exact form also keeps `distinct_count == row_count` usable as the
uniqueness signal, which no estimate can carry.

Every row is stamped `source='aggregate'`, projected into the row rather than
added afterwards, so a consumer comparing this profile with another engine's
estimate can tell them apart without knowing which engine answered. There is
no `collected_at`: an aggregate is current by construction, and a timestamp
would make it look like a stale estimate.

Two shapes are the union's price. ClickHouse refuses a `UNION ALL` whose arms
disagree on a column's type — it looks for a supertype and raises when there is
none — so `min_value` and `max_value` are cast to `Nullable(String)` in every
arm rather than left to be the column's own type. The figures are exact; the
endpoints arrive as text, and a numeric one is read back through `Decimal`. An
empty column list answers with no rows, read from `system.one` rather than a
bare `SELECT`, because ClickHouse allows a `WHERE` only over a source; a real
table always has at least one column, so that branch exists for a statement
that has to render.

One column whose type these aggregates refuse fails the whole statement rather
than dropping that column's arm: `Array`, `Map` and `Tuple` have no
`MIN`/`MAX` and no `COUNT(DISTINCT)` in ClickHouse. A silently missing column
would be a profile claiming a table has fewer columns than it does.

The profile's null count is a `SUM` over a `CASE`, not `countIf`, and it rides
`COUNT(*)`'s scan because the two are halves of one fraction. `SUM` is a
spelling the shared renderer produces correctly; `SUM` also makes an empty
table answer `0`, which the parser reads as "no fraction" because the row
count is zero — not as a column that holds no NULLs. The two remaining data
families keep their own prices. `value-samples` is a `GROUP BY` over the
column plus a sort of the groups: `ORDER BY COUNT(*) DESC` is what makes the
answer "the most frequent values" rather than "the first values", ties break
by the value so two runs agree, and the limit is a bind parameter. ClickHouse
groups NULLs into a real row, so a column holding NULLs has a NULL entry in
its listing — usually the most frequent one — and that is a member of the
domain, not a value the formatter filters out; `frequency` stays `None`
because the engine reports a count and the denominator is the row count the
profile carries. `join-coverage` counts distinct non-NULL values on both
sides, with the denominators `NULLIF`-guarded so a column with nothing to
match answers `None` rather than `0.0`: "nothing matched" and "nothing to
match" stay distinct. There is no `* 1.0`, because ClickHouse's `/` over two
integers already answers a floating-point share. Types are not reconciled:
values compare by their own type, so unrelated types never match and the
fractions are a genuine zero for that join, not a measurement of a conversion
the engine did not perform.

### The Runtime Types

A profile returned by this backend is a `ClickHouseColumnDataProfile`, which is
the core profile plus one named field: `runtime_types`. It exists because of
how ClickHouse stores a value. Elsewhere a column's type is a property of the
*column*; ClickHouse composes types — `Nullable`, `LowCardinality`, `Enum8`,
`DateTime64(3, 'UTC')`, `Array(Tuple(...))` — and names the type of the
expression it evaluated rather than the declaration it stored. Grouping that
name over the column is therefore a query about the *data*: an ordinary column
holds the one type the engine resolved for every row, and a column whose values
do not all resolve the same way holds each of them, which is exactly what a
reader of the declaration cannot see.

Core keeps this slot out on purpose — it is a real dialect difference — so the
fact lives on the backend's own subclass, where a caller who asked ClickHouse
can find it and a caller who asked another engine never has to ignore it. The
projection is one aggregate over the same scan, so the fact costs no extra
pass:

```
groupUniqArray(toTypeName(`note`)) AS `runtime_types`
```

The list is sorted in the parser, not in SQL, because the aggregate's own
order is not defined and two runs of the same profile must compare equal. A
driver that hands the array back as a list and one that hands back a tuple
both work; a bare string is treated as the single-entry set it is. `None`
becomes an empty list rather than a missing slot: the array exists on every
row the statement returns, so `None` can only mean the column produced no
values — an empty table — and there is no type to name. The parser lifts
`runtime_types` out of the row before the core parser sees it, so it is a
named field rather than a dictionary key a caller has to discover by reading
the source.

```python
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host="localhost", port=8123, database="analytics",
    username="root", password="password",
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()

for profile in backend.introspector.list_column_data_profiles("events"):
    print(profile.column_name, profile.null_fraction, profile.runtime_types)
```

An `Int32` column reports the one name `Int32`. A column declared
`Nullable(String)` reports a name from the string family, and which spelling
the engine chose — `String` or `Nullable(String)` — is the server's answer,
not something to pin against the declaration.

## The Function-Name Casing Trap

This is the single most useful fact a reader can take from this backend, and
it is the reason the profile is written the way it is. The shared function
renderer upper-cases every function name it renders. On ClickHouse that is
right for exactly the SQL-standard spellings, and wrong for everything
camelCase.

ClickHouse resolves a function name through its `FunctionFactory` and
`AggregateFunctionFactory`, which try an exact match first and then a
*lowercased* match against a map that holds only the names registered
`Case::Insensitive`. That registry is small: `sum`, `count`, `min`, `max`,
`nullIf` and a handful of SQL-standard spellings are in it, so `SUM` and
`COUNT` upper-case happily. `groupUniqArray`, `toTypeName` and `currentUser`
are registered `Case::Sensitive`, the default, and every combinator suffix
(`OrNull`, `If`, `State`) is matched against the tail of the name *as written*.
An upper-cased camelCase name therefore matches neither map.

The cost is not theoretical. `minOrNull` rendered as `MINORNULL`, and the
server answered ``Function with name `MINORNULL` does not exist`` — two CI
runs on the same commit, five failing jobs each. The renderer cannot know
which map a name lands in, so the backend asks for the spellings that are
registered, verbatim, through `_engine_function()`:

```python
sql = self._engine_function("groupUniqArray", self._engine_function("toTypeName", column))
```

`_engine_function()` hands the optional operator text to SQL as a `RawSQL`
node rather than a `FunctionCall`, precisely so no companion code path
re-applies the case rule to it. The operands are still their own nodes: a
column is quoted and catalog-qualified by the dialect's identifier renderer,
and a literal binds where `Literal` says it binds. Only the name is raw, never
the whole call. The same helper carries `currentUser` and `version`, the two
status reads whose casing is not the shared renderer's to decide — and the
second is the read the backend's version detection rests on.

One trap sat behind the other: the engine answers only the first unresolved
name in a query, so fixing `MINORNULL` exposed the next one. The first form of
the profile asked for `groupUniqArray(typeof(col))`, and `typeof` is **not a
ClickHouse function at all** — it never shipped. Checked against the function
catalogue ClickHouse publishes (the regular functions, all 195 aggregate
functions, the table functions and the window functions), the string `typeof`
occurs zero times, case-insensitively; `toTypeName` is the function that
exists, and a live server proved it. The rendered arm is now

```
groupUniqArray(toTypeName(`id`)) AS `runtime_types`
CAST(MIN(`id`) AS Nullable(String)) AS `min_value`
```

and the offline case guard rejects `MINORNULL`, `MAXORNULL`,
`GROUPUNIQARRAY`, `TOTYPENAME` and `CURRENTUSER` in the rendered statements,
so a future edit that hands one of them back to the shared renderer fails
there instead of on five CI jobs.

### The All-NULL Endpoint

The endpoints are `MIN`/`MAX`, not `minOrNull`/`maxOrNull`, because those
names cannot survive the shared renderer — that is the same casing trap, and
`MIN`/`MAX` are the two names in this arm that do survive it. The difference
is one figure for one kind of column, and it is a real limitation rather than
a rounding detail.

The plain aggregates answer with the *default of the result type* when no
non-NULL value was ever accumulated, while the `OrNull` combinator forces the
NULL answer. So a column where **every** row is NULL reports that default as
both endpoints — the empty string for a string column — where `minOrNull`
would have produced NULL and the parser would have read `None`. The profile's
other two figures still say what happened: `null_count` equals `row_count` and
`null_fraction` is `1.0`, so "every value is NULL" survives. What is lost is
the endpoints' own claim to have measured no value.

## Command Line

`python -m rhosocial.activerecord.backend.impl.clickhouse introspect` asks the
same introspector, so what the CLI prints is what the library sees rather than
a second implementation. The sixteen types are listed above with their switches
and their `NAME` rule. `NAME` is the table for `columns`, `indexes`,
`partitions`, `table-engine`, `ddl`, `column-profiles`, `value-samples` and
`join-coverage`, and the view itself for `views`; `dependencies` takes an
optional object name that narrows the graph; `tables`, `database` and the four
whole-scope operational families refuse a name rather than parse and drop it.
A required name that is missing is an incomplete invocation (exit 1); a name
the type cannot use is a request the command declines (exit 2); a switch that
answers `False` is a refusal with exit 2 and
`Error: <type> introspection is not supported by this server`; a failed
connection or a missing view is exit 1.

`--column` names the column for `value-samples` and the left column for
`join-coverage`; `--right-table` and `--right-column` are read only by
`join-coverage`. A flag a type does not read is refused (exit 2) for the same
reason a name nothing reads is: a silently dropped argument produces a
successful run that looks like it answered a narrower question. `--limit` is
forwarded only when it is given, so the introspector's own default owns the
number. `column-profiles` prints one note to stderr — the profiles are
aggregated, `source='aggregate'`, and paid for with a full scan per column —
leaving the machine formats parseable.

```bash
python -m rhosocial.activerecord.backend.impl.clickhouse introspect column-profiles events \
    --host localhost --database analytics --user root --password password

python -m rhosocial.activerecord.backend.impl.clickhouse introspect value-samples events \
    --column status --limit 20 --database analytics --user root --password password
```

`runtime_types` rides the row through serialisation without becoming a shared
column. The serializer walks the dataclass, so the field reaches a JSON caller
as its own array beside the five core figures, and the table format shows it
in its own cell. It is never folded into `extra` and never promoted into the
common profile shape, because a fact only this engine can answer does not
belong in a slot every engine must fill.

## Version and Availability Floors

There is no version floor established for these families. The sixteen types
are gated on capability switches evaluated against the connected server's
adapted dialect, not on a version number written here, and the three data
families need only ordinary aggregates and `system.*` relations that every
version this backend declares — 25.8, 26.3 and 26.7 — provides. A probe that
answers `False` remains the complete answer: it says the question cannot be
asked here, which is a different statement from a database that has nothing
to report.

Continue with [CLI usage](../cli/README.md) for the other subcommands, and
[Unsupported features](../capabilities/unsupported.md) for the boundaries this
backend refuses instead of emulating.
