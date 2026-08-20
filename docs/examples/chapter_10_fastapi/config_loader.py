# config_loader.py - ClickHouse Connection Configuration for FastAPI
# docs/examples/chapter_10_fastapi/config_loader.py

from __future__ import annotations

import os
import sys

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseConnectionConfig


def load_config() -> ClickHouseConnectionConfig:
    """Load ClickHouse connection configuration from environment or defaults."""
    return ClickHouseConnectionConfig(
        host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "3306")),
        database=os.environ.get("CLICKHOUSE_DATABASE", "test_db"),
        username=os.environ.get("CLICKHOUSE_USER", "root"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=True,
    )
