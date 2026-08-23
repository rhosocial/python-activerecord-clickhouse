-- ClickHouse schema for basic/posts table
-- post_ref/author reference user ids but ClickHouse has no FOREIGN KEY
CREATE TABLE IF NOT EXISTS posts (
    id Int64,
    author Int64,
    title String,
    content String,
    published_at DateTime64(3),
    published Bool DEFAULT false,
    created_at DateTime64(3),
    updated_at DateTime64(3),
    INDEX idx_author author TYPE minmax GRANULARITY 1
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
