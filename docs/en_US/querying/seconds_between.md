# Signed seconds between two instants

`seconds_between` answers one question: how many seconds elapsed from `start`
to `end`, with the sign carrying the direction and the fraction kept. It is the
fractional sibling of `date_diff` (`date_diff("second", ...)` still counts
whole seconds, and a caller who wants whole seconds rounds the result).

```python
from rhosocial.activerecord.backend.expression import Column, seconds_between

elapsed = seconds_between(
    dialect,
    Column(dialect, "queued_at"),
    Column(dialect, "started_at"),
).as_("queue_seconds")
sql, params = elapsed.to_sql()
# sql: "dateDiff('millisecond', `queued_at`, `started_at`) / 1000.0 AS `queue_seconds`"
# params: ()
```

The same question can be asked from the column side; the receiver must be a
timestamp column (`TimestampColumn`, or a `datetime` field reached through
`Model.c.<field>`):

```python
queue_seconds = queued_at.seconds_between(started_at)
```

## How ClickHouse renders it

```sql
dateDiff('millisecond', start, end) / 1000.0
```

`dateDiff` counts whole units only, so this backend asks it for the finest unit
ClickHouse offers — milliseconds — and divides by `1000.0`. The division turns
the integer count into a `Float64`, which is what preserves the fraction;
`dateDiff(..., 'second', ...)` alone would round a sub-second span to `0`.

The sign needs no special case. `dateDiff(unit, start, end)` is
`end - start`, so an `end` earlier than the `start` subtracts to a negative
value while the SQL stays identical:

| Case | Result |
|------|--------|
| `end` later than `start` | positive |
| `end` earlier than `start` | negative |
| same instant | `0` |
| fraction present in either value | kept to the millisecond (see below) |

A `DateTime` or `Date` column has no fraction, so the result is an integral
number of seconds. `DateTime64(3)` keeps the millisecond and the result carries
it. `DateTime64(6)` stores microseconds, but `dateDiff` counts at millisecond
resolution here: the microseconds are truncated, not rounded. A caller who
needs better than a millisecond should compute the difference at that
precision (`dateDiff('microsecond', ...) / 1000000.0`), rather than expect this
node to reach beyond the finest unit the spelling names.

## Bind parameters

The SQL writes `start` before `end`, so the bind parameters are collected in
that order as well:

```python
expr = seconds_between(
    dialect,
    Literal(dialect, "2026-01-01 00:00:00"),
    Literal(dialect, "2026-01-02 00:00:00"),
)
sql, params = expr.to_sql()
# sql: "dateDiff('millisecond', %s, %s) / 1000.0"
# params: ("2026-01-01 00:00:00", "2026-01-02 00:00:00")
```

`end` is the later value in the result, but it is the second placeholder in the
SQL; the parameter order follows the statement text, not the node's role names.

## See also

- The core library's `docs/en_US/backend/expression/functions.md`, where the
  `seconds_between` node and the backend formatter contract are documented.
- [Querying overview](README.md) for the ClickHouse-specific query features.
