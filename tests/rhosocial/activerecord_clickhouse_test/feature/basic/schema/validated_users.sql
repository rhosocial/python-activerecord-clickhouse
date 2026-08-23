-- ClickHouse schema for basic/validated_users table
CREATE TABLE IF NOT EXISTS validated_users (
    id Int64,
    username String,
    email String,
    age Nullable(Int64)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;