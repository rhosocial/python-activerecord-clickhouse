# 连接配置

## 基础配置项

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| host | str | localhost | ClickHouse 服务器地址 |
| port | int | 3306 | ClickHouse 端口 |
| database | str | - | 数据库名称 |
| username | str | root | 用户名 |
| password | str | - | 密码 |
| charset | str | utf8mb4 | 字符集 |
| collation | str | utf8mb4_unicode_ci | 排序规则 |
| autocommit | bool | True | 自动提交 |

## 高级配置项

```python
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    # 基础配置
    host='localhost',
    port=3306,
    database='myapp',
    username='myuser',
    password='mypassword',
    
    # 字符集配置
    charset='utf8mb4',
    collation='utf8mb4_unicode_ci',
    
    # 连接选项
    autocommit=True,
    connect_timeout=10,
    read_timeout=30,
    write_timeout=30,
    
    # SSL 配置
    ssl_ca='/path/to/ca.pem',
    ssl_cert='/path/to/client-cert.pem',
    ssl_key='/path/to/client-key.pem',
    ssl_verify_cert=False,
)
```

## 使用 YAML 配置

```yaml
# clickhouse_scenarios.yaml
scenarios:
  production:
    host: db.example.com
    port: 3306
    database: myapp_prod
    username: app_user
    password: ${CLICKHOUSE_PASSWORD}
    charset: utf8mb4
    autocommit: true
    ssl_verify_cert: true
    
  development:
    host: localhost
    port: 3306
    database: myapp_dev
    username: dev_user
    password: dev_password
    charset: utf8mb4
    autocommit: true
```

💡 *AI 提示词：* "什么是字符集和排序规则？utf8mb4 与 utf8 有什么区别？"
