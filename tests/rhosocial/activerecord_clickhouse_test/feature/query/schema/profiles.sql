-- ClickHouse schema for query/profiles table
CREATE TABLE IF NOT EXISTS profiles (
    id Int64,
    user_id Int64 NOT NULL,
    bio String,
    avatar_url String,
    created_at DateTime64(6),
    updated_at DateTime64(6)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
