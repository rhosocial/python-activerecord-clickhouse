# Supported versions

## ClickHouse versions

The release lines verified in the CI matrix are below. In principle, the
maintained LTS and stable lines are covered:

| ClickHouse version | Status | Notes |
|--------------------|--------|-------|
| 25.8.x (LTS) | ✅ CI verified | Maintained LTS |
| 26.3.x (LTS) | ✅ CI verified | Maintained LTS |
| 26.7.x | ✅ CI verified | Current stable line |
| Earlier versions | ⚠️ untested | May work but not guaranteed; capability probes degrade per actual version |

> ⚠️ **Note**: The docs and code **no longer contain** MySQL version numbers like
> `5.6`/`5.7`/`8.0`/`9.0`/`9.6`. They were migration leftovers and have been
> cleaned up. ClickHouse uses calendar versioning (`YY.M.patch`), e.g. `26.7`.

The dialect and type adapters probe the actual server version on connect and
adjust capability switches accordingly (some functions or settings are only
available in newer versions).

## Python versions

| Python version | Status |
|---------------|--------|
| 3.10 | ✅ CI verified |
| 3.11 | ✅ CI verified |
| 3.12 | ✅ CI verified |
| 3.13 | ✅ CI verified |
| 3.14 | ✅ CI verified |

The Python range `>=3.10,<3.15` is dictated by `clickhouse-connect`'s
`Requires-Python`. This backend adds no further Python version restriction.

## Core library version

| Dependency | Constraint |
|------------|------------|
| `rhosocial-activerecord` | `>=1.0.0.dev30,<2.0.0` |
| `clickhouse-connect` | `>=1.7.0` |

`dev30` is a hard dependency (see [Relationship with the core library](relationship.md#dependency-version)).
Until `dev30` is published to PyPI, install the core library from source.

## CI matrix

CI runs the following matrix on `main` push / PR (`.github/workflows/test.yml`):

```
Python 3.10 × ClickHouse 25.8
Python 3.11 × ClickHouse 25.8
Python 3.12 × ClickHouse 26.3
Python 3.13 × ClickHouse 26.3
Python 3.14 × ClickHouse 26.7   ← also collects coverage
```

The test suite is composed of the shared feature tests (basic/events/interface/
mixins/query/relation) from
[python-activerecord-testsuite](https://github.com/rhosocial/python-activerecord-testsuite)
and this backend's own ClickHouse-specific tests. Unsupported capabilities are
sensibly skipped via `pytest.skip` rather than failing.

## Next steps

- [Capability boundaries & fail-fast](capability_boundaries.md)
- [Installation guide](../installation/installation.md)
