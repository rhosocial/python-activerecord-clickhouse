-- ClickHouse schema for query/users table
CREATE TABLE IF NOT EXISTS users (
    id Int64,
    username String NOT NULL,
    email String NOT NULL,
    age Nullable(Int32),
    balance Float64 NOT NULL DEFAULT 0.0,
    is_active Bool NOT NULL DEFAULT 1,
    created_at DateTime64(6),
    updated_at DateTime64(6)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
