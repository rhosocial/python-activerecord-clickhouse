-- ClickHouse schema for basic/bulk_users table
CREATE TABLE IF NOT EXISTS bulk_users (
    id Int64,
    name String,
    age Int64 DEFAULT 0,
    email String DEFAULT ''
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
