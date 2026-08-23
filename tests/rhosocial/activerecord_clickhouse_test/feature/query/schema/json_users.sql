-- ClickHouse schema for query/json_users table
CREATE TABLE IF NOT EXISTS json_users (
    id Int64,
    username String NOT NULL,
    email String NOT NULL,
    age Nullable(Int32),
    created_at DateTime64(6),
    updated_at DateTime64(6),
    settings String,
    tags String,
    profile String,
    roles String,
    scores String,
    subscription String,
    preferences String
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
