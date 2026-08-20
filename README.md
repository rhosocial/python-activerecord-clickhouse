# rhosocial-activerecord-clickhouse ($\rho_{\mathbf{AR}\text{-clickhouse}}$)

[![PyPI version](https://badge.fury.io/py/rhosocial-activerecord-clickhouse.svg)](https://badge.fury.io/py/rhosocial-activerecord-clickhouse)
[![Python](https://img.shields.io/pypi/pyversions/rhosocial-activerecord-clickhouse.svg)](https://pypi.org/project/rhosocial-activerecord-clickhouse/)
[![Tests](https://github.com/rhosocial/python-activerecord-clickhouse/actions/workflows/test.yml/badge.svg)](https://github.com/rhosocial/python-activerecord-clickhouse/actions)
[![Coverage Status](https://codecov.io/gh/rhosocial/python-activerecord-clickhouse/branch/main/graph/badge.svg)](https://app.codecov.io/gh/rhosocial/python-activerecord-clickhouse/tree/main)
[![Apache 2.0 License](https://img.shields.io/github/license/rhosocial/python-activerecord-clickhouse.svg)](https://github.com/rhosocial/python-activerecord-clickhouse/blob/main/LICENSE)
[![Powered by vistart](https://img.shields.io/badge/Powered_by-vistart-blue.svg)](https://github.com/vistart)

<div align="center">
    <img src="https://raw.githubusercontent.com/rhosocial/python-activerecord/main/docs/images/logo.svg" alt="rhosocial ActiveRecord Logo" width="200"/>
    <h3>ClickHouse Backend for rhosocial-activerecord</h3>
    <p><b>Production-Ready ClickHouse Support · Sync & Async · Native Driver Integration</b></p>
</div>

> **Note**: This is a backend implementation for [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It cannot be used standalone.

## Why This Backend?

### 1. ClickHouse-Specific Optimizations

| Feature | This Backend | Generic Solutions |
|---------|-------------|-------------------|
| **Full-Text Search** | Native `MATCH ... AGAINST` | LIKE-based workarounds |
| **JSON Operations** | `JSON_EXTRACT`, `->>`, `->` | Serialize/deserialize overhead |
| **Upsert** | `ON DUPLICATE KEY UPDATE` | Manual check-then-insert |
| **Connection Pooling** | Built-in with clickhouse-connector | External pooling required |

### 2. True Sync-Async Parity

Same API surface for both sync and async operations:

```python
# Sync
users = User.query().where(User.c.age >= 18).all()

# Async - just add await
users = await User.query().where(User.c.age >= 18).all()
```

### 3. Built for Production

- **Connection pooling** with configurable pool sizes
- **Transaction support** with proper isolation levels
- **Error mapping** from ClickHouse error codes to Python exceptions
- **Type adapters** for ClickHouse-specific data types

## Quick Start

### Installation

```bash
pip install rhosocial-activerecord-clickhouse
```

### Basic Usage

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from typing import Optional

class User(ActiveRecord):
    __table_name__ = "users"
    id: Optional[int] = None
    name: str
    email: str

# Configure
config = ClickHouseConnectionConfig(
    host="localhost",
    port=3306,
    database="myapp",
    username="user",
    password="password"
)
User.configure(config, ClickHouseBackend)

# Use
user = User(name="Alice", email="alice@example.com")
user.save()

# Query with ClickHouse full-text search
results = User.query().where(
    "MATCH(name, email) AGAINST(? IN BOOLEAN MODE)",
    ("+Alice",)
).all()
```

> 💡 **AI Prompt**: "Show me how to use JSON operations in ClickHouse with this backend"

## ClickHouse-Specific Features

### Full-Text Search

Native ClickHouse full-text search support:

```python
# Boolean mode full-text search
Article.query().where(
    "MATCH(title, content) AGAINST(? IN BOOLEAN MODE)",
    ("+python -java",)
).all()

# Natural language mode
Article.query().where(
    "MATCH(title, content) AGAINST(?)",
    ("database optimization",)
).all()
```

### JSON Operations

Query JSON columns using ClickHouse's native JSON functions:

```python
# Extract JSON value
User.query().where("settings->>'$.theme' = ?", ("dark",)).all()

# JSON contains
Product.query().where("JSON_CONTAINS(tags, ?)", ('"featured"',)).all()
```

### Upsert (ON DUPLICATE KEY UPDATE)

Efficient insert-or-update operations:

```python
# Will update on duplicate key
User.insert_or_update(
    name="Alice",
    email="alice@example.com",
    update_fields=["name"]  # Only update name on conflict
)
```

## Requirements

- **Python**: 3.8+ (including 3.13t/3.14t free-threaded builds)
- **Core**: `rhosocial-activerecord>=1.0.0`
- **Driver**: `clickhouse-connect>=9.0.0`

## Get Started with AI Code Agents

This project supports AI-assisted development. Clone and open in your preferred tool:

```bash
git clone https://github.com/rhosocial/python-activerecord-clickhouse.git
cd python-activerecord-clickhouse
```

### Example AI Prompts

- "How do I configure connection pooling for ClickHouse?"
- "Show me the differences between ClickHouse and PostgreSQL backends"
- "How do I use ClickHouse-specific JSON operators?"
- "Create a model with a FULLTEXT index"

### For Any LLM

Feed the documentation files in `docs/` to your preferred LLM for context-aware assistance.

## Testing

> ⚠️ **CRITICAL**: Tests MUST run serially. Do NOT use `pytest -n auto` or parallel execution.

```bash
# Run all tests
PYTHONPATH=src pytest tests/

# Run specific feature tests
PYTHONPATH=src pytest tests/rhosocial/activerecord_clickhouse_test/feature/basic/
PYTHONPATH=src pytest tests/rhosocial/activerecord_clickhouse_test/feature/query/
```

See the [Testing Documentation](https://github.com/rhosocial/python-activerecord/blob/main/.claude/testing.md) for details.

## Documentation

- **[Getting Started](docs/en_US/getting_started/)** — Installation and configuration
- **[ClickHouse Features](docs/en_US/clickhouse_specific_features/)** — ClickHouse-specific capabilities
- **[Type Adapters](docs/en_US/type_adapters/)** — Data type handling
- **[Transaction Support](docs/en_US/transaction_support/)** — Transaction management

## Comparison with Other Backends

| Feature | ClickHouse | PostgreSQL | SQLite |
|---------|-------|------------|--------|
| **Full-Text Search** | ✅ Native | ✅ Native | ⚠️ FTS5 extension |
| **JSON Type** | ✅ JSON | ✅ JSONB | ⚠️ JSON1 extension |
| **Arrays** | ❌ | ✅ Native | ❌ |
| **Upsert** | ✅ ON DUPLICATE KEY | ✅ ON CONFLICT | ✅ ON CONFLICT |
| **Returning** | ❌ | ✅ RETURNING | ✅ RETURNING |

> 💡 **AI Prompt**: "When should I choose ClickHouse over PostgreSQL for my project?"

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[Apache License 2.0](LICENSE) — Copyright © 2026 [vistart](https://github.com/vistart)

---

<div align="center">
    <p><b>Built with ❤️ by the rhosocial team</b></p>
    <p><a href="https://github.com/rhosocial/python-activerecord-clickhouse">GitHub</a> · <a href="https://docs.python-activerecord.dev.rho.social/backends/clickhouse.html">Documentation</a> · <a href="https://pypi.org/project/rhosocial-activerecord-clickhouse/">PyPI</a></p>
</div>
