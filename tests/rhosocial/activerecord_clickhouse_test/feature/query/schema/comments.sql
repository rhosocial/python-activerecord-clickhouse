-- ClickHouse schema for query/comments table
CREATE TABLE IF NOT EXISTS comments (
    id Int64,
    user_id Int64 NOT NULL,
    post_id Int64 NOT NULL,
    content String,
    is_hidden Bool DEFAULT 0,
    created_at DateTime,
    updated_at DateTime,
    INDEX idx_user_id (user_id) TYPE minmax,
    INDEX idx_post_id (post_id) TYPE minmax
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
