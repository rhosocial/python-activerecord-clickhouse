# 本地 ClickHouse 测试

## 概述

介绍如何在本地搭建 ClickHouse 测试环境。

## 使用 Docker 运行 ClickHouse

```bash
# 运行 ClickHouse 容器
docker run -d \
  --name clickhouse-test \
  -e CLICKHOUSE_ROOT_PASSWORD=test \
  -e CLICKHOUSE_DATABASE=test \
  -p 3306:3306 \
  clickhouse:8.0

# 等待 ClickHouse 启动
docker exec clickhouse-test wait-for-it.sh localhost:3306 --timeout=30
```

## 使用 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  clickhouse:
    image: clickhouse:8.0
    environment:
      CLICKHOUSE_ROOT_PASSWORD: test
      CLICKHOUSE_DATABASE: test
    ports:
      - "3306:3306"
    volumes:
      - clickhouse_data:/var/lib/clickhouse

volumes:
  clickhouse_data:
```

```bash
docker-compose up -d
```

## 运行测试

```bash
# 设置环境变量
export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=3306
export CLICKHOUSE_DATABASE=test
export CLICKHOUSE_USER=root
export CLICKHOUSE_PASSWORD=test

# 运行测试
pytest tests/
```

💡 *AI 提示词：* "Docker 和 Docker Compose 有什么区别？"
