-- ClickHouse schema for basic/users table
CREATE TABLE IF NOT EXISTS users (
    id Int64,
    username String,
    email String,
    age Int64,
    balance Float64 DEFAULT 0.0,
    is_active Bool DEFAULT true,
    created_at DateTime64(3),
    updated_at DateTime64(3)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
