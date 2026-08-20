# 安装指南

## 系统要求

- Python 3.8+
- ClickHouse 5.6 ~ 9.6 或 MariaDB（仅支持与 ClickHouse 特性兼容的部分）
- pip 或 poetry

## 安装步骤

### 1. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

### 2. 安装核心库与 ClickHouse 后端

```bash
# 安装核心库
pip install rhosocial-activerecord

# 安装 ClickHouse 后端
pip install rhosocial-activerecord-clickhouse
```

### 3. 安装 ClickHouse 驱动

本后端仅支持 clickhouse-connector-python 驱动：

```bash
pip install clickhouse-connector-python
```

⚠️ **注意**：本后端不支持其他 ClickHouse 驱动（如 clickhouseclient、PyClickHouse 等）。请确保使用 clickhouse-connector-python。

## 验证安装

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

💡 *AI 提示词：* "clickhouse-connector-python 有什么优缺点？"
