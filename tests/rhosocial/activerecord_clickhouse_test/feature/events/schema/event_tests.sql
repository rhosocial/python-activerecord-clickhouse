-- ClickHouse schema for events/event_tests table
CREATE TABLE IF NOT EXISTS event_tests (
    id Int64,
    name String NOT NULL,
    status String NOT NULL DEFAULT 'draft',
    revision Int32 NOT NULL DEFAULT 1,
    content String,
    created_at DateTime64(6),
    updated_at DateTime64(6)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
