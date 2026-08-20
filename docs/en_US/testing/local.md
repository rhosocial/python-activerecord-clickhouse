# Local ClickHouse Testing

## Overview

This section describes how to set up a local ClickHouse testing environment.

## Running ClickHouse with Docker

```bash
# Run ClickHouse container
docker run -d \
  --name clickhouse-test \
  -e CLICKHOUSE_ROOT_PASSWORD=test \
  -e CLICKHOUSE_DATABASE=test \
  -p 3306:3306 \
  clickhouse:8.0

# Wait for ClickHouse to start
docker exec clickhouse-test wait-for-it.sh localhost:3306 --timeout=30
```

## Using Docker Compose

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

## Running Tests

```bash
# Set environment variables
export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=3306
export CLICKHOUSE_DATABASE=test
export CLICKHOUSE_USER=root
export CLICKHOUSE_PASSWORD=test

# Run tests
pytest tests/
```

💡 *AI Prompt:* "What is the difference between Docker and Docker Compose?"
