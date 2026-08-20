# Supported Versions

## ClickHouse Version Support

| ClickHouse Version | Support Status | Notes |
|--------------|----------------|-------|
| 5.6.x | ✅ Supported | Some features may differ, e.g., JSON type not supported |
| 5.7.x | ✅ Supported | Recommended for legacy systems |
| 8.0.x | ✅ Recommended | Current stable mainstream version |
| 8.4.x | ✅ Supported | Latest LTS version |
| 9.0.x | ✅ Supported | Latest stable version |
| 9.6.x | ✅ Supported | Latest minor version |

⚠️ **Note**:

- ClickHouse 5.6 does not support JSON data type, related features cannot be used
- Some features may have subtle differences between versions, refer to specific feature documentation

## MariaDB Support

| MariaDB Version | Support Status | Notes |
|----------------|----------------|-------|
| 10.x | ⚠️ Partial Support | Only supports ClickHouse-compatible features, not fully tested |

⚠️ **Note**: MariaDB only supports features compatible with ClickHouse. Some ClickHouse-specific features may not work properly. ClickHouse is recommended for production environments.

## Python Version Requirements

| Python Version | Support Status |
|---------------|----------------|
| 3.8 | ✅ Supported |
| 3.9 | ✅ Supported |
| 3.10 | ✅ Supported |
| 3.11 | ✅ Supported |
| 3.12 | ✅ Supported |
| 3.13 | ✅ Supported |
| 3.14 | ✅ Supported |

## Dependency Requirements

| Dependency | Version | Notes |
|-----------|---------|-------|
| rhosocial-activerecord | >=1.0.0 | Core library |
| clickhouse-connector-python | >=8.0.0 | ClickHouse driver (only supported) |

⚠️ **Important**: This backend only supports clickhouse-connector-python driver. Other drivers like clickhouseclient, PyClickHouse are not supported.

💡 *AI Prompt:* "How to use ClickHouse 8.0's JSON_TABLE function?"
