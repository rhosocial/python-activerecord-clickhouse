-- ClickHouse schema for query/searchable_items table
CREATE TABLE IF NOT EXISTS searchable_items (
    id Int64,
    name String,
    tags String,
    created_at DateTime64(6),
    updated_at DateTime64(6)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
