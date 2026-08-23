-- ClickHouse schema for mixins/combined_articles table
CREATE TABLE IF NOT EXISTS combined_articles (
    id Int64,
    title String NOT NULL,
    content String NOT NULL,
    status String NOT NULL DEFAULT 'draft',
    created_at DateTime,
    updated_at DateTime,
    version Int32 NOT NULL DEFAULT 1,
    deleted_at Nullable(DateTime64(6))
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
