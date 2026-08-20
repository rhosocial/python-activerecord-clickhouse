# SSL/TLS 配置

## 概述

当 ClickHouse 服务器端启用了可信机构签发的有效证书时，客户端连接时可以省略 SSL 相关参数，默认即可建立 SSL 连接。

## 基础用法（无需额外配置）

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

# 服务器证书由可信机构签发且在有效期内时，无需额外配置
backend = ClickHouseBackend(
    host='clickhouse.example.com',
    port=3306,
    database='myapp',
    username='user',
    password='password',
)
# 默认即启用 SSL 连接
backend.connect()
```

## SSL 配置参数

如需自定义 SSL 行为，可使用以下参数：

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| ssl_ca | str | - | CA 证书路径 |
| ssl_cert | str | - | 客户端证书路径 |
| ssl_key | str | - | 客户端私钥路径 |
| ssl_verify_cert | bool | True | 是否验证服务器证书 |
| ssl_verify_identity | bool | False | 是否验证服务器身份 |

## 自签名证书

对于自签名证书，需要额外配置：

```python
config = {
    'host': 'clickhouse.example.com',
    'ssl_ca': '/path/to/self-signed-ca.pem',
    'ssl_verify_cert': False,  # 禁用证书验证
}

backend = ClickHouseBackend(**config)
```

## 验证 SSL 连接

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

backend = ClickHouseBackend(
    host='clickhouse.example.com',
    port=3306,
    database='myapp',
    username='user',
    password='password',
)
backend.connect()

# 检查连接是否使用 SSL
connection = backend.get_connection()
print(f"SSL 状态: {connection.is_ssl}")
print(f"加密算法: {connection.get_character_set_info()}")

backend.disconnect()
```

💡 *AI 提示词：* "SSL、TLS 和 SSH 有什么区别？数据库连接中为什么需要 SSL？"
