# src/rhosocial/activerecord/backend/impl/clickhouse/config.py
"""ClickHouse-specific connection configuration

This module provides ClickHouse-specific connection configuration classes that extend
the base ConnectionConfig with ClickHouse-specific parameters and functionality.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from rhosocial.activerecord.backend.config import (
    ConnectionConfig,
    ConnectionPoolMixin,
    SSLMixin,
    CharsetMixin,
    TimezoneMixin,
    VersionMixin,
    LoggingMixin,
)


@dataclass
class ClickHouseConnectionConfig(
    ConnectionConfig, ConnectionPoolMixin, SSLMixin, CharsetMixin, TimezoneMixin, VersionMixin, LoggingMixin
):
    """ClickHouse connection configuration with ClickHouse-specific parameters.

    This class extends the base ConnectionConfig with ClickHouse-specific
    parameters and functionality including connection pooling, SSL,
    character sets, timezone handling, and logging options.
    """

    # ClickHouse-specific connection options
    autocommit: bool = True
    connect_timeout: int = 10
    send_receive_timeout: int = 30

    # ClickHouse driver settings
    compress: bool = False
    settings: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary, including ClickHouse-specific parameters."""
        config_dict = super().to_dict()

        clickhouse_params = {
            "autocommit": self.autocommit,
            "connect_timeout": self.connect_timeout,
            "send_receive_timeout": self.send_receive_timeout,
            "compress": self.compress,
        }

        if self.settings:
            clickhouse_params["settings"] = self.settings

        for key, value in clickhouse_params.items():
            if value is not None:
                config_dict[key] = value

        return config_dict
