-- ClickHouse schema for events/event_tracking_models table
CREATE TABLE IF NOT EXISTS event_tracking_models (
    id Int64,
    title String NOT NULL,
    content String NOT NULL,
    view_count Int32 NOT NULL DEFAULT 0,
    last_viewed_at Nullable(DateTime)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
