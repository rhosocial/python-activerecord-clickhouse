-- ClickHouse schema for basic/comments table
-- post_ref/author reference other tables but ClickHouse has no FOREIGN KEY
CREATE TABLE IF NOT EXISTS comments (
    id Int64,
    post_ref Int64,
    author Int64,
    text String,
    created_at DateTime64(3),
    updated_at DateTime64(3),
    approved Bool DEFAULT false,
    INDEX idx_post_ref post_ref TYPE minmax GRANULARITY 1,
    INDEX idx_author author TYPE minmax GRANULARITY 1
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
