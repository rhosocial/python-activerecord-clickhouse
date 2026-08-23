-- ClickHouse schema for basic/mixed_annotation_items table
CREATE TABLE IF NOT EXISTS mixed_annotation_items (
    id Int64,
    name String,
    tags String,
    meta String,
    description String,
    status String
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
