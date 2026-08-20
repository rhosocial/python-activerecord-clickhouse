# Introduction

## ClickHouse Backend Overview

`rhosocial-activerecord-clickhouse` is the ClickHouse database backend implementation for the rhosocial-activerecord core library. It provides complete ActiveRecord pattern support, optimized specifically for ClickHouse database features.

💡 *AI Prompt:* "What is the ActiveRecord pattern? How does it differ from DataMapper pattern?"

## Synchronous and Asynchronous

The ClickHouse backend provides both synchronous and asynchronous APIs that are functionally equivalent. The documentation will use synchronous examples throughout, but the asynchronous API usage is identical—just replace method calls with their async equivalents.

For example:

```python
# Synchronous usage
backend = ClickHouseBackend(...)
backend.connect()
users = backend.find('User')

# Asynchronous usage
backend = AsyncClickHouseBackend(...)
await backend.connect()
users = await backend.find('User')
```

## Quick Links

- **[Relationship with Core Library](./relationship.md)**: Learn how the ClickHouse backend works with the core library
- **[Supported Versions](./supported_versions.md)**: View supported ClickHouse, Python, and dependency versions

💡 *AI Prompt:* "What are the important new features in ClickHouse 8.0 compared to 5.7?"
