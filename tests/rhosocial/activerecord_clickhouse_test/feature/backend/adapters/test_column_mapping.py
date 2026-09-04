# tests/rhosocial/activerecord_clickhouse_test/feature/backend/adapters/test_column_mapping.py
import pytest
from datetime import datetime
import uuid

# Note: The actual adapters are imported from the core library, as the clickhouse backend
# may rely on the standard ones if it doesn't provide its own overrides.
from rhosocial.activerecord.backend.type_adapter import UUIDAdapter, BooleanAdapter


@pytest.fixture
def setup_mapped_users_table(clickhouse_backend):
    """Fixture to create and drop a 'mapped_users' table for ClickHouse."""
    clickhouse_backend.execute("DROP TABLE IF EXISTS mapped_users")
    clickhouse_backend.execute("""
        CREATE TABLE mapped_users (
            user_id UInt32,
            name String NOT NULL,
            email String,
            created_at DateTime,
            user_uuid String,
            is_active UInt8
        ) ENGINE = MergeTree()
        ORDER BY user_id
        SETTINGS enable_block_number_column = 1
    """)
    yield
    clickhouse_backend.execute("DROP TABLE IF EXISTS mapped_users")


def test_insert_with_mapping(clickhouse_backend, setup_mapped_users_table):
    """
    Tests that execute() with an INSERT correctly handles mapped data.
    Note: ClickHouse < 8.0.1 does not support RETURNING, so we verify with a subsequent SELECT.
    """
    backend = clickhouse_backend
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Data for insertion must use database column names and compatible types
    sql = "INSERT INTO mapped_users (user_id, name, email, created_at, user_uuid, is_active) VALUES (%s, %s, %s, %s, %s, %s)"
    params = (99, "John Doe", "john.doe@example.com", now_str, str(uuid.uuid4()), 1)

    result = backend.execute(sql=sql, params=params)

    # ClickHouse does not report affected_rows / last_insert_id for INSERT
    # like MySQL; verify by reading the row back.
    fetched = backend.execute("SELECT name FROM mapped_users WHERE user_uuid = %s", (params[4],))
    assert fetched.data and fetched.data[0]["name"] == "John Doe"


def test_fetch_with_combined_mapping_and_adapters(clickhouse_backend, setup_mapped_users_table):
    """
    Tests that execute() correctly applies both column_mapping and column_adapters for ClickHouse.
    """
    backend = clickhouse_backend
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    test_uuid = uuid.uuid4()

    # Define mappings and adapters
    column_to_field_mapping = {"user_id": "pk", "name": "full_name", "user_uuid": "uuid", "is_active": "active"}

    # Adapters can be instantiated directly for testing purposes
    column_adapters = {"user_uuid": (UUIDAdapter(), uuid.UUID), "is_active": (BooleanAdapter(), bool)}

    # Insert data in DB-compatible format
    backend.execute(
        "INSERT INTO mapped_users (user_id, name, email, created_at, user_uuid, is_active) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (100, "Combined Test", "combined@example.com", now_str, str(test_uuid), 1),
    )

    # Execute SELECT with both mapping and adapters
    result = backend.execute(
        "SELECT * FROM mapped_users WHERE user_id = 100",
        column_mapping=column_to_field_mapping,
        column_adapters=column_adapters,
    )

    fetched_row = result.data[0] if result.data else None
    assert fetched_row is not None

    # 1. Assert keys are the MAPPED FIELD NAMES
    assert "full_name" in fetched_row
    assert "uuid" in fetched_row
    assert "active" in fetched_row
    assert "name" not in fetched_row
    assert "user_uuid" not in fetched_row

    # 2. Assert values are the ADAPTED PYTHON TYPES
    assert fetched_row["full_name"] == "Combined Test"
    assert isinstance(fetched_row["uuid"], uuid.UUID)
    assert fetched_row["uuid"] == test_uuid
    assert isinstance(fetched_row["active"], bool)
    assert fetched_row["active"] is True
