-- ClickHouse schema for mixins/timestamped_posts table
CREATE TABLE IF NOT EXISTS timestamped_posts (
    id Int64,
    title String NOT NULL,
    content String NOT NULL,
    created_at DateTime64(6),
    updated_at DateTime64(6)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
