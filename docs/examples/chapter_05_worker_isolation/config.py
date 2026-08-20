# docs/examples/worker_isolation_experiment/config.py
"""
Configuration loader for Worker isolation experiment.

Loads ClickHouse connection configuration from the test scenarios config.
"""

import os
import yaml
from typing import Dict, Any, Optional

from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig


def load_scenario_config(scenario_name: str = None) -> ClickHouseConnectionConfig:
    """
    Load ClickHouse connection config from the test scenarios YAML file.

    Args:
        scenario_name: Name of the scenario to load. If None, uses environment
                      variable CLICKHOUSE_SCENARIO or the first available scenario.

    Returns:
        ClickHouseConnectionConfig instance
    """
    # Find config file
    env_config_path = os.getenv("CLICKHOUSE_SCENARIOS_CONFIG_PATH")
    if env_config_path and os.path.exists(env_config_path):
        config_path = env_config_path
    else:
        # Default path relative to this file
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "tests", "config", "clickhouse_scenarios.yaml"
        )

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"ClickHouse scenarios config not found at {config_path}. "
            "Set CLICKHOUSE_SCENARIOS_CONFIG_PATH environment variable."
        )

    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)

    scenarios = config_data.get('scenarios', {})
    if not scenarios:
        raise ValueError("No scenarios found in config file")

    # Select scenario
    if scenario_name is None:
        scenario_name = os.getenv("CLICKHOUSE_SCENARIO", next(iter(scenarios.keys())))

    if scenario_name not in scenarios:
        raise ValueError(f"Scenario '{scenario_name}' not found. Available: {list(scenarios.keys())}")

    return ClickHouseConnectionConfig(**scenarios[scenario_name])


def get_backend_class():
    """Return the ClickHouse backend class."""
    return ClickHouseBackend


# Table schema definitions (embedded for self-contained experiment)
SCHEMA_SQL = {
    "users": """
        CREATE TABLE IF NOT EXISTS `users` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `username` VARCHAR(191) NOT NULL UNIQUE,
            `email` VARCHAR(191) NOT NULL UNIQUE,
            `age` INT,
            `balance` DOUBLE NOT NULL DEFAULT 0.0,
            `is_active` TINYINT(1) NOT NULL DEFAULT 1,
            `created_at` DATETIME(6),
            `updated_at` DATETIME(6)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "orders": """
        CREATE TABLE IF NOT EXISTS `orders` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `user_id` INT NOT NULL,
            `order_number` VARCHAR(255) NOT NULL,
            `total_amount` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            `status` VARCHAR(50) NOT NULL DEFAULT 'pending',
            `created_at` DATETIME(6),
            `updated_at` DATETIME(6),
            INDEX `idx_user_id` (`user_id`),
            FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "posts": """
        CREATE TABLE IF NOT EXISTS `posts` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `user_id` INT NOT NULL,
            `title` VARCHAR(255) NOT NULL,
            `content` TEXT,
            `status` VARCHAR(50) NOT NULL DEFAULT 'published',
            `created_at` DATETIME(6),
            `updated_at` DATETIME(6),
            INDEX `idx_user_id` (`user_id`),
            INDEX `idx_status` (`status`),
            FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "comments": """
        CREATE TABLE IF NOT EXISTS `comments` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `user_id` INT NOT NULL,
            `post_id` INT NOT NULL,
            `content` TEXT NOT NULL,
            `is_hidden` TINYINT(1) NOT NULL DEFAULT 0,
            `created_at` DATETIME(6),
            `updated_at` DATETIME(6),
            INDEX `idx_user_id` (`user_id`),
            INDEX `idx_post_id` (`post_id`),
            FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
            FOREIGN KEY (`post_id`) REFERENCES `posts`(`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
}


def setup_database(backend: ClickHouseBackend, drop_existing: bool = True) -> None:
    """
    Set up database tables.

    Args:
        backend: ClickHouse backend instance
        drop_existing: Whether to drop existing tables first
    """
    # Disable foreign key checks for table operations
    backend.execute("SET FOREIGN_KEY_CHECKS = 0")

    try:
        if drop_existing:
            # Drop tables in reverse order of foreign key dependencies
            for table in reversed(list(SCHEMA_SQL.keys())):
                backend.execute(f"DROP TABLE IF EXISTS `{table}`")

        # Create tables in order of dependencies
        for table, sql in SCHEMA_SQL.items():
            backend.execute(sql)
    finally:
        backend.execute("SET FOREIGN_KEY_CHECKS = 1")
