"""Configuration Management Module, implementing multi-level priority configuration mechanism"""

import os
import yaml
from typing import Dict, Any
from pathlib import Path

# Try to import tomllib (Python 3.11+) or tomli for older versions
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


def load_yaml_config(file_path: Path) -> Dict[str, Any]:
    """
    Load YAML configuration file

    Args:
        file_path: YAML file path

    Returns:
        Configuration dictionary
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
            print(f"[INFO] Loaded configuration from {file_path}")
            return config
    except Exception as e:
        print(f"[ERROR] Failed to load configuration file {file_path}: {e}")
        raise


def load_toml_config(file_path: Path) -> Dict[str, Any]:
    """
    Load TOML configuration file

    Args:
        file_path: TOML file path

    Returns:
        Configuration dictionary
    """
    if tomllib is None:
        raise ImportError("tomllib or tomli is required to load TOML configuration files")

    try:
        with open(file_path, "rb") as f:
            config = tomllib.load(f) or {}
            print(f"[INFO] Loaded configuration from {file_path}")
            return config
    except Exception as e:
        print(f"[ERROR] Failed to load configuration file {file_path}: {e}")
        raise


def load_config_from_file(config_path: Path) -> Dict[str, Any]:
    """
    Load configuration from file based on its extension

    Args:
        config_path: Configuration file path

    Returns:
        Configuration dictionary
    """
    # Remove any potential trailing spaces from the suffix
    suffix = config_path.suffix.lower().strip()
    if suffix in [".yaml", ".yml"]:
        return load_yaml_config(config_path)
    elif suffix == ".toml":
        return load_toml_config(config_path)
    else:
        raise ValueError(f"Unsupported configuration file format: {config_path.suffix}")


def load_config() -> Dict[str, Any]:
    """
    Load configuration using multi-level priority mechanism:
    1. Environment variable specified config file (CLICKHOUSE_ACTIVERECCORD_CONFIG_PATH)
    2. Default config file (config.toml then config.yaml/config.yml in project root)
    3. Environment variables for ClickHouse connection parameters
    4. Hard-coded default values
    """
    # 1. Check environment variable for config file path
    config_file_path_env = os.getenv("CLICKHOUSE_ACTIVERECCORD_CONFIG_PATH")
    if config_file_path_env:
        config_path = Path(config_file_path_env)
        if config_path.exists():
            print(f"[INFO] Using configuration file from environment variable: {config_path}")
            try:
                return load_config_from_file(config_path)
            except Exception as e:
                print(f"[ERROR] Configuration file from environment variable exists but failed to read: {e}")
                print("[ERROR] Terminating due to configuration read error.")
                raise
        else:
            print(f"[WARNING] Configuration file specified in environment variable does not exist: {config_path}")
            raise FileNotFoundError(
                f"Configuration file {config_path} specified in CLICKHOUSE_ACTIVERECCORD_CONFIG_PATH does not exist"
            )

    # 2. Check default config files in tests directory, prioritizing TOML then YAML
    default_config_paths = [
        Path(__file__).parent.parent / "config.toml",  # Looking for TOML in project root first
        Path(__file__).parent.parent / "config.yaml",  # Fallback to YAML in project root
        Path(__file__).parent.parent / "config.yml",  # Alternative YAML extension
    ]

    for default_config_path in default_config_paths:
        if default_config_path.exists():
            print(f"[INFO] Using default configuration file: {default_config_path}")
            try:
                return load_config_from_file(default_config_path)
            except Exception as e:
                print(f"[ERROR] Default configuration file exists but failed to read: {e}")
                print("[ERROR] Terminating due to configuration read error.")
                raise

    # 3. Try to get connection parameters from environment variables
    clickhouse_host = os.getenv("CLICKHOUSE_HOST")
    clickhouse_port = os.getenv("CLICKHOUSE_PORT")
    clickhouse_user = os.getenv("CLICKHOUSE_USER")
    clickhouse_password = os.getenv("CLICKHOUSE_PASSWORD")
    clickhouse_database = os.getenv("CLICKHOUSE_DATABASE")

    if all([clickhouse_host, clickhouse_port, clickhouse_user, clickhouse_password, clickhouse_database]):
        print("[INFO] Using ClickHouse connection parameters from environment variables")
        return {
            "databases": {
                "clickhouse": {
                    "versions": [
                        {
                            "label": "environment",
                            "version": [8, 0, 0],  # Default version assumption
                            "host": clickhouse_host,
                            "port": int(clickhouse_port),
                            "database": clickhouse_database,
                            "username": clickhouse_user,
                            "password": clickhouse_password,
                        }
                    ]
                }
            }
        }

    # 4. Use default hard-coded configuration
    print("[INFO] Using default hard-coded configuration")
    return {
        "databases": {
            "clickhouse": {
                "versions": [
                    {
                        "label": "default",
                        "version": [8, 0, 21],  # Default version assumption
                        "host": "localhost",
                        "port": 3306,
                        "database": "test_db",
                        "username": "root",
                        "password": "password",
                        "charset": "utf8mb4",
                        "autocommit": True,
                        "connect_timeout": 10,
                        # Temporarily disable read_timeout and write_timeout, as they are not supported by the
                        # version of clickhouse-connector-python used in the current test environment.
                        # 'read_timeout': 30,
                        # 'write_timeout': 30,
                        "ssl_disabled": True,  # SSL is disabled by default
                    }
                ]
            }
        },
        "connection_pool": {"pool_name": "test_pool", "pool_size": 5, "pool_reset_session": True},
    }


def get_clickhouse_configurations() -> Dict[str, Any]:
    """
    Get ClickHouse configurations using the multi-level priority mechanism

    Returns:
        ClickHouse configurations dictionary
    """
    return load_config()


# For backward compatibility with existing scenarios code
def get_clickhouse_connection_params() -> Dict[str, Any]:
    """
    Get basic ClickHouse connection parameters for backward compatibility

    Returns:
        Connection parameters dictionary
    """
    config = load_config()

    # Extract default ClickHouse connection parameters from config
    clickhouse_configs = config.get("databases", {}).get("clickhouse", {}).get("versions", [])
    if clickhouse_configs:
        # Return the first configuration as default
        first_config = clickhouse_configs[0]
        return first_config

    # Fallback to basic environment variables or defaults
    return {
        "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "port": int(os.getenv("CLICKHOUSE_PORT", "3306")),
        "user": os.getenv("CLICKHOUSE_USER", "root"),
        "password": os.getenv("CLICKHOUSE_PASSWORD", "password"),
        "database": os.getenv("CLICKHOUSE_DATABASE", "test_db"),
    }
