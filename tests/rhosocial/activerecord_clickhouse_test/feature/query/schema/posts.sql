-- ClickHouse schema for query/posts table
CREATE TABLE IF NOT EXISTS posts (
    id Int64,
    user_id Int64 NOT NULL,
    title String NOT NULL,
    content String,
    status String NOT NULL DEFAULT 'published',
    created_at DateTime64(6),
    updated_at DateTime64(6),
    INDEX idx_user_id (user_id) TYPE minmax,
    INDEX idx_status (status) TYPE minmax
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
