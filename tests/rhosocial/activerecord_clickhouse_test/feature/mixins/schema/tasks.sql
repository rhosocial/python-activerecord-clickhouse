-- ClickHouse schema for mixins/tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id Int64,
    title String NOT NULL,
    is_completed Bool NOT NULL DEFAULT 0,
    deleted_at Nullable(String)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
