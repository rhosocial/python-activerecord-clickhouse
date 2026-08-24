# Installation guide

## System requirements

| Component | Version |
|-----------|---------|
| Python | `>=3.10,<3.15` (dictated by `clickhouse-connect`'s `Requires-Python`) |
| ClickHouse server | 25.8 LTS / 26.3 LTS / 26.7 (maintained release lines; earlier untested) |
| Core library `rhosocial-activerecord` | `>=1.0.0.dev30,<2.0.0` (hard dependency) |
| Driver `clickhouse-connect` | `>=1.7.0` |

## Install from source (required during the current dev phase)

Until the core library `dev30` is published to PyPI, install both the core and
this backend from source.

### 1. Clone the repositories

```bash
git clone https://github.com/rhosocial/python-activerecord.git
git clone https://github.com/rhosocial/python-activerecord-clickhouse.git
```

### 2. Create a virtual environment

```bash
cd python-activerecord-clickhouse
python3.14 -m venv .venv3.14   # name per your Python version
source .venv3.14/bin/activate
```

### 3. Install the core library (editable)

```bash
pip install -e ../python-activerecord
```

> To run the test suite, also install the testsuite:
> ```bash
> git clone https://github.com/rhosocial/python-activerecord-testsuite.git
> pip install -e ../python-activerecord-testsuite
> ```

### 4. Install this backend (editable, with dev dependencies)

```bash
pip install -e ".[dev]"
# or runtime dependencies only:
pip install -e .
```

### 5. Verify the installation

```bash
python -c "from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend; print('ok')"
```

## Install from PyPI (once dev30 is published)

After the core library `1.0.0.dev30` is on PyPI:

```bash
pip install rhosocial-activerecord-clickhouse
```

This pulls the core library and `clickhouse-connect` automatically.

## Start a local ClickHouse (optional, for testing)

The easiest way is the official Docker image:

```bash
docker run -d --name clickhouse \
  -p 8123:8123 -p 9000:9000 \
  -e CLICKHOUSE_USER=root \
  -e CLICKHOUSE_PASSWORD=password \
  -e CLICKHOUSE_DB=test_db \
  clickhouse/clickhouse-server:26.7
```

> Port **8123** is ClickHouse's HTTP interface (used by this backend); **9000** is
> the native protocol (not used by this backend).

## Next steps

- [Connection configuration](configuration.md)
- [Quick start](../getting_started/quick_start.md)
