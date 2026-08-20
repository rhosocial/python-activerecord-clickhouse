# Common Connection Errors

## Overview

This section covers common ClickHouse connection errors and their solutions.

## Connection Refused

### Error Message
```
ERROR 2003 (HY000): Can't connect to ClickHouse server
```

### Causes
- ClickHouse service is not running
- Incorrect port
- Firewall blocking

### Solutions
```bash
# Check if ClickHouse is running
sudo systemctl status clickhouse

# Check port
telnet localhost 3306
```

## Authentication Failed

### Error Message
```
ERROR 1045 (28000): Access denied for user 'root'@'localhost'
```

### Causes
- Incorrect username or password
- User does not have remote access permissions

### Solutions
```sql
-- Execute on ClickHouse server
CREATE USER 'user'@'%' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON database.* TO 'user'@'%';
FLUSH PRIVILEGES;
```

## Connection Timeout

### Error Message
```
ERROR 2003: Can't connect to ClickHouse server (110)
```

### Causes
- Network issues
- connect_timeout setting is too short

### Solutions
```python
config = ClickHouseConnectionConfig(
    host='remote.host.com',
    connect_timeout=30,  # Increase timeout
)
```

## SSL Connection Error

### Error Message
```
ERROR 2026 (HY000): SSL connection error
```

### Causes
- SSL certificate issues
- Incorrect SSL configuration

### Solutions
```python
config = ClickHouseConnectionConfig(
    host='remote.host.com',
    ssl_verify_cert=False,  # Disable certificate verification (testing only)
)
```

## Connection Loss and Automatic Recovery

### Overview

In long-running applications, database connections may be dropped for various reasons. The ClickHouse backend implements a dual-layer protection mechanism to ensure automatic recovery when connections are lost.

### Common Connection Loss Scenarios

| Scenario | Cause | Error Codes |
|----------|-------|-------------|
| `wait_timeout` expiry | Connection idle time exceeds ClickHouse's `wait_timeout` setting | 2006, 2013 |
| Connection killed | DBA executes `KILL CONNECTION` or connection pool management | 2013 |
| Network instability | Network issues cause TCP connection to drop | 2003, 2055 |
| Server restart | ClickHouse server restart or crash | 2006, 2013 |
| Firewall timeout | Firewall closes long-idle TCP connections | 2013 |

### Automatic Recovery Mechanism

The ClickHouse backend implements two layers of automatic recovery:

#### Plan A: Pre-Query Connection Check

Before each query execution, the backend automatically checks the connection status:

```python
def _get_cursor(self):
    """Get a database cursor, ensuring connection is active."""
    if not self._connection:
        # No connection, establish new one
        self.connect()
    elif not self._connection.is_connected():
        # Connection lost, reconnect
        self.disconnect()
        self.connect()
    return self._connection.cursor()
```

**Features**:
- Proactive checking, detects issues before query execution
- Uses `is_connected()` method to check connection status
- Completely transparent to the application layer

#### Plan B: Error Retry Mechanism

When a connection error occurs during query execution, the backend automatically retries:

```python
# ClickHouse connection error codes
CONNECTION_ERROR_CODES = {
    2003,  # CR_CONN_HOST_ERROR - Can't connect to ClickHouse server
    2006,  # CR_SERVER_GONE_ERROR - ClickHouse server has gone away
    2013,  # CR_SERVER_LOST - Lost connection during query
    2048,  # CR_CONN_UNKNOW_PROTOCOL - Invalid connection protocol
    2055,  # CR_SERVER_LOST_EXTENDED - Extended connection lost
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

**Features**:
- Reactive recovery, triggered on query failure
- Maximum 2 retries
- Only retries on connection errors, other errors are raised directly

### Manual Keep-Alive Mechanism

For scenarios requiring proactive connection maintenance, use the `ping()` method:

```python
# Check connection status without auto-reconnect
is_alive = backend.ping(reconnect=False)

# Check connection status with auto-reconnect if disconnected
is_alive = backend.ping(reconnect=True)
```

#### Keep-Alive Best Practices

In multi-process worker scenarios, implement periodic keep-alive:

```python
import threading
import time

def keepalive_worker(backend, interval=60):
    """Background keep-alive thread"""
    while True:
        time.sleep(interval)
        if backend.ping(reconnect=True):
            logger.debug("Connection keepalive successful")
        else:
            logger.warning("Connection keepalive failed")

# Start keep-alive thread
keepalive_thread = threading.Thread(
    target=keepalive_worker,
    args=(backend, 60),
    daemon=True
)
keepalive_thread.start()
```

### Async Backend Support

The async backend (`AsyncClickHouseBackend`) provides the same connection recovery mechanism:

```python
# Async ping
is_alive = await async_backend.ping(reconnect=True)

# Async queries also auto-reconnect
result = await async_backend.execute("SELECT 1")
```

### Best Practices

#### 1. Configure ClickHouse Timeout Parameters Appropriately

```sql
-- View current settings
SHOW VARIABLES LIKE 'wait_timeout';
SHOW VARIABLES LIKE 'interactive_timeout';

-- Recommended settings (adjust based on your requirements)
SET GLOBAL wait_timeout = 28800;        -- 8 hours
SET GLOBAL interactive_timeout = 28800; -- 8 hours
```

#### 2. Use Connection Pool (Sync Backend)

For high-concurrency scenarios, enable connection pooling:

```python
config = ClickHouseConnectionConfig(
    host='localhost',
    database='mydb',
    pool_name='mypool',
    pool_size=5,
)
```

> **Note**: The async backend (using aioclickhouse) does not support connection pooling.

#### 3. Multi-Process Worker Scenarios

Each worker process should have its own backend instance:

```python
def worker_process(worker_id, config):
    """Worker process entry point"""
    # Create independent backend instance within the process
    backend = ClickHouseBackend(connection_config=config)
    backend.connect()

    try:
        # Execute tasks
        do_work(backend)
    finally:
        backend.disconnect()
```

#### 4. Monitor Connection Status

```python
import logging

# Enable backend logging
logging.getLogger('rhosocial.activerecord.backend').setLevel(logging.DEBUG)

# Backend will automatically log connection recovery events
# DEBUG: Connection lost, reconnecting...
# DEBUG: Reconnected successfully
```

### Connection Error Codes Reference

| Error Code | Name | Description |
|------------|------|-------------|
| 2003 | CR_CONN_HOST_ERROR | Can't connect to ClickHouse server |
| 2006 | CR_SERVER_GONE_ERROR | ClickHouse server has gone away |
| 2013 | CR_SERVER_LOST | Lost connection during query |
| 2048 | CR_CONN_UNKNOW_PROTOCOL | Invalid connection protocol |
| 2055 | CR_SERVER_LOST_EXTENDED | Extended connection lost |

💡 *AI Prompt:* "How to troubleshoot ClickHouse connection errors? How does the backend automatically recover connections?"
