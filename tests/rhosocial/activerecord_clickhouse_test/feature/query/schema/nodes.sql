-- ClickHouse schema for query/nodes table
CREATE TABLE IF NOT EXISTS nodes (
    id Int64,
    name String NOT NULL,
    parent_id Nullable(Int64),
    value Decimal(10, 2) NOT NULL DEFAULT 0.0,
    created_at DateTime64(6),
    updated_at DateTime64(6)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
