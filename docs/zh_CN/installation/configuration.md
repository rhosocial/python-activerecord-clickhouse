# 连接配置

本后端使用 `ClickHouseConnectionConfig` 描述连接参数，它是核心库 `ConnectionConfig` 的子类，叠加了 ClickHouse 专属选项。

## 最小配置

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host="localhost",
    port=8123,            # ClickHouse HTTP 端口
    database="test_db",
    username="root",
    password="password",
)
```

> ⚠️ 端口是 **8123**（HTTP），不是 3306。`clickhouse-connect` 通过 HTTP 与 ClickHouse 通信。

## 完整配置项

`ClickHouseConnectionConfig` 继承自核心库的多个 mixin，可用字段如下：

| 字段 | 来源 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | `ConnectionConfig` | — | ClickHouse 主机 |
| `port` | `ConnectionConfig` | — | **8123**（HTTP） |
| `database` | `ConnectionConfig` | — | 数据库名 |
| `username` | `ConnectionConfig` | — | 用户名 |
| `password` | `ConnectionConfig` | — | 密码 |
| `autocommit` | ClickHouse 专属 | `True` | `clickhouse-connect` 的 autocommit 模式 |
| `connect_timeout` | ClickHouse 专属 | `10` | 连接超时（秒）|
| `send_receive_timeout` | ClickHouse 专属 | `30` | 收发超时（秒）|
| `compress` | ClickHouse 专属 | `False` | 是否启用 HTTP 压缩 |
| `settings` | ClickHouse 专属 | `None` | 传给 ClickHouse 的会话级 `settings` 字典（如 `{"mutations_sync": "1"}`）|

此外继承的 mixin 字段（`SSLMixin`/`TimezoneMixin`/`LoggingMixin`/`VersionMixin` 等）按核心库通用语义使用。`CharsetMixin` 字段存在但 ClickHouse 不使用 MySQL 风格的 charset（utf-8 是 HTTP 传输默认）。

## 把配置绑定到模型

```python
from rhosocial.activerecord.model import ActiveRecord

class User(ActiveRecord):
    __table_name__ = "users"
    __primary_key__ = "id"
    ...

User.configure(config, ClickHouseBackend)
```

之后所有 `User` 的查询都会走该后端。

## SSL/TLS

ClickHouse 原生支持 HTTPS（默认 8443）。本后端通过 `ssl_mode` 启用 TLS：

| `ssl_mode` | 行为 | 适用 |
|------------|------|------|
| `disabled` / `auto` / 未设 | 明文 HTTP（默认 8123）| 本地开发、内网 |
| `require` | HTTPS 加密，**不**校验证书 | 加密传输、自签证书 |
| `verify-ca` | HTTPS + 校验服务器证书链 | 生产（见下方限制）|
| `verify-full` | HTTPS + 校验证书链 + 主机名 | 生产推荐 |

配置示例：

```python
config = ClickHouseConnectionConfig(
    host="clickhouse.example.com",
    port=8443,                 # 远程 HTTPS 端口
    database="test_db",
    username="root",
    password="password",
    ssl_mode="verify-full",     # 启用 HTTPS + 校验证书 + 校验主机名
    # ssl_ca="/path/to/ca.pem", # 可选：自定义 CA（系统 CA store 已含 Let's Encrypt 等公共 CA 时可省）
)
```

### 实测可用

以下均对 ClickHouse 26.7 实测通过：

```bash
# HTTPS 加密不校验
python -m rhosocial.activerecord.backend.impl.clickhouse query "SELECT version()" \
    --host clickhouse.example.com --port 8443 --database test_db \
    --user root --password password --ssl require

# HTTPS 校验证书 + 主机名
python -m rhosocial.activerecord.backend.impl.clickhouse query "SELECT 1" \
    --host clickhouse.example.com --port 8443 --database test_db \
    --user root --password password --ssl verify-full

# HTTPS 校验证书（用证书 CN 域名访问）
python -m rhosocial.activerecord.backend.impl.clickhouse query "SELECT 1" \
    --host clickhouse.example.com --port 8443 --database test_db \
    --user root --password password --ssl verify-ca
```

### verify-ca 的限制

底层驱动 `clickhouse-connect` 的证书校验是布尔开关（`verify=True` 同时校验 CA **与主机名**），**不原生支持**"校验 CA 但不校验主机名"的标准 `verify-ca` 语义。因此本后端的 `verify-ca` 实际与 `verify-full` 行为一致：

- 用**证书 CN 对应的域名**访问（如 `clickhouse.example.com`）→ 主机名匹配，校验通过；
- 用 `localhost` / IP 访问证书 CN 为其他域名的服务 → 主机名不匹配，校验失败。

如需"加密但完全不校验"，用 `--ssl require`；如需校验，请用证书域名访问。

## 多后端隔离（开发用 SQLite，生产用 ClickHouse）

核心库支持按模型类绑定不同后端。开发环境可用 SQLite（零 IO 测试），生产切 ClickHouse：

```python
# 开发
User.configure(sqlite_config, SQLiteBackend)
# 生产
User.configure(clickhouse_config, ClickHouseBackend)
```

切换前用 `dialect.supports_*()` 探测能力差异，避免在 ClickHouse 上调用不支持的功能。

## 通过环境变量配置（测试场景）

测试时常用环境变量覆盖默认值（见 [测试配置](../testing/README.md)）：

```bash
export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=8123
export CLICKHOUSE_DATABASE=test_db
export CLICKHOUSE_USER=root
export CLICKHOUSE_PASSWORD=password
```

## 下一步

- [快速开始](../getting_started/quick_start.md)
- [能力边界](../introduction/capability_boundaries.md)
