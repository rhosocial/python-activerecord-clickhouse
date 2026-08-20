# Installation Guide

## System Requirements

- Python 3.8+
- ClickHouse 5.6 ~ 9.6 or MariaDB (only supports ClickHouse-compatible features)
- pip or poetry

## Installation Steps

### 1. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows
```

### 2. Install Core Library and ClickHouse Backend

```bash
# Install core library
pip install rhosocial-activerecord

# Install ClickHouse backend
pip install rhosocial-activerecord-clickhouse
```

### 3. Install ClickHouse Driver

This backend only supports clickhouse-connector-python driver:

```bash
pip install clickhouse-connector-python
```

⚠️ **Note**: This backend does not support other ClickHouse drivers (such as clickhouseclient, PyClickHouse, etc.). Please ensure you use clickhouse-connector-python.

## Verify Installation

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

backend = ClickHouseBackend(
    host='localhost',
    port=3306,
    database='test_db',
    username='root',
    password='password'
)
backend.connect()
print(f"ClickHouse version: {backend.get_server_version()}")
backend.disconnect()
```

💡 *AI Prompt:* "What are the advantages and disadvantages of clickhouse-connector-python?"
