# 常见连接错误

## 概述

本节介绍 ClickHouse 连接常见错误及解决方案。

## 连接被拒绝 (Connection Refused)

### 错误信息
```
ERROR 2003 (HY000): Can't connect to ClickHouse server
```

### 原因
- ClickHouse 服务未运行
- 端口错误
- 防火墙阻止

### 解决方案
```bash
# 检查 ClickHouse 是否运行
sudo systemctl status clickhouse

# 检查端口
telnet localhost 3306
```

## 认证失败 (Authentication Failed)

### 错误信息
```
ERROR 1045 (28000): Access denied for user 'root'@'localhost'
```

### 原因
- 用户名或密码错误
- 用户没有远程访问权限

### 解决方案
```sql
-- 在 ClickHouse 服务器上执行
CREATE USER 'user'@'%' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON database.* TO 'user'@'%';
FLUSH PRIVILEGES;
```

## 连接超时 (Connection Timeout)

### 错误信息
```
ERROR 2003: Can't connect to ClickHouse server (110)
```

### 原因
- 网络问题
- connect_timeout 设置过短

### 解决方案
```python
config = ClickHouseConnectionConfig(
    host='remote.host.com',
    connect_timeout=30,  # 增加超时时间
)
```

## SSL 连接错误

### 错误信息
```
ERROR 2026 (HY000): SSL connection error
```

### 原因
- SSL 证书问题
- SSL 配置错误

### 解决方案
```python
config = ClickHouseConnectionConfig(
    host='remote.host.com',
    ssl_verify_cert=False,  # 禁用证书验证（仅测试环境）
)
```

## 连接断开与自动恢复

### 概述

在长时间运行的应用程序中，数据库连接可能会因为各种原因断开。ClickHouse 后端实现了双层保护机制，确保连接断开后能够自动恢复。

### 连接断开的常见场景

| 场景 | 原因 | 错误码 |
|------|------|--------|
| `wait_timeout` 超时 | 连接空闲时间超过 ClickHouse 的 `wait_timeout` 设置 | 2006, 2013 |
| 连接被杀 | DBA 执行 `KILL CONNECTION` 或连接池管理 | 2013 |
| 网络抖动 | 网络不稳定导致 TCP 连接断开 | 2003, 2055 |
| 服务器重启 | ClickHouse 服务器重启或崩溃 | 2006, 2013 |
| 防火墙超时 | 防火墙关闭长时间空闲的 TCP 连接 | 2013 |

### 自动恢复机制

ClickHouse 后端实现了两层自动恢复机制：

#### 方案 A：查询前连接检查

在每次执行查询前，后端会自动检查连接状态：

```python
def _get_cursor(self):
    """获取游标，自动检查连接有效性"""
    if not self._connection:
        # 无连接，建立新连接
        self.connect()
    elif not self._connection.is_connected():
        # 连接已断开，重连
        self.disconnect()
        self.connect()
    return self._connection.cursor()
```

**特点**：
- 主动检查，在查询执行前发现问题
- 使用 `is_connected()` 方法检测连接状态
- 对应用层完全透明

#### 方案 B：错误重试机制

当查询执行时发生连接错误，后端会自动重试：

```python
# ClickHouse 连接错误码
CONNECTION_ERROR_CODES = {
    2003,  # CR_CONN_HOST_ERROR - 无法连接到 ClickHouse 服务器
    2006,  # CR_SERVER_GONE_ERROR - ClickHouse 服务器已断开
    2013,  # CR_SERVER_LOST - 查询期间丢失连接
    2048,  # CR_CONN_UNKNOW_PROTOCOL - 无效的连接协议
    2055,  # CR_SERVER_LOST_EXTENDED - 扩展的连接丢失
}

def execute(self, sql, params=None, *, options=None, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            return super().execute(sql, params, options=options)
        except ClickHouseOperationalError as e:
            if self._is_connection_error(e) and attempt < max_retries:
                self._reconnect()
                continue
            raise
```

**特点**：
- 被动恢复，在查询失败时触发
- 最多重试 2 次
- 仅对连接错误重试，其他错误直接抛出

### 手动保活机制

对于需要主动维护连接的场景，可以使用 `ping()` 方法：

```python
# 检查连接状态，不自动重连
is_alive = backend.ping(reconnect=False)

# 检查连接状态，断开时自动重连
is_alive = backend.ping(reconnect=True)
```

#### 保活最佳实践

在多进程 Worker 场景中，建议实现定期保活：

```python
import threading
import time

def keepalive_worker(backend, interval=60):
    """后台保活线程"""
    while True:
        time.sleep(interval)
        if backend.ping(reconnect=True):
            logger.debug("Connection keepalive successful")
        else:
            logger.warning("Connection keepalive failed")

# 启动保活线程
keepalive_thread = threading.Thread(
    target=keepalive_worker,
    args=(backend, 60),
    daemon=True
)
keepalive_thread.start()
```

### 异步后端支持

异步后端 (`AsyncClickHouseBackend`) 提供相同的连接恢复机制：

```python
# 异步 ping
is_alive = await async_backend.ping(reconnect=True)

# 异步查询也会自动重连
result = await async_backend.execute("SELECT 1")
```

### 最佳实践建议

#### 1. 合理设置 ClickHouse 超时参数

```sql
-- 查看当前设置
SHOW VARIABLES LIKE 'wait_timeout';
SHOW VARIABLES LIKE 'interactive_timeout';

-- 建议设置（根据业务需求调整）
SET GLOBAL wait_timeout = 28800;        -- 8 小时
SET GLOBAL interactive_timeout = 28800; -- 8 小时
```

#### 2. 使用连接池（同步后端）

对于高并发场景，建议启用连接池：

```python
config = ClickHouseConnectionConfig(
    host='localhost',
    database='mydb',
    pool_name='mypool',
    pool_size=5,
)
```

> **注意**：异步后端（使用 aioclickhouse）不支持连接池。

#### 3. 多进程 Worker 场景

每个 Worker 进程应独立配置后端实例：

```python
def worker_process(worker_id, config):
    """Worker 进程入口"""
    # 在进程内创建独立的后端实例
    backend = ClickHouseBackend(connection_config=config)
    backend.connect()

    try:
        # 执行任务
        do_work(backend)
    finally:
        backend.disconnect()
```

#### 4. 监控连接状态

```python
import logging

# 启用后端日志
logging.getLogger('rhosocial.activerecord.backend').setLevel(logging.DEBUG)

# 后端会自动记录连接恢复事件
# DEBUG: Connection lost, reconnecting...
# DEBUG: Reconnected successfully
```

### 相关错误码参考

| 错误码 | 名称 | 说明 |
|--------|------|------|
| 2003 | CR_CONN_HOST_ERROR | 无法连接到 ClickHouse 服务器 |
| 2006 | CR_SERVER_GONE_ERROR | ClickHouse 服务器已断开 |
| 2013 | CR_SERVER_LOST | 查询期间丢失连接 |
| 2048 | CR_CONN_UNKNOW_PROTOCOL | 无效的连接协议 |
| 2055 | CR_SERVER_LOST_EXTENDED | 扩展的连接丢失 |

💡 *AI 提示词：* "ClickHouse 连接错误如何排查？后端如何自动恢复连接？"
