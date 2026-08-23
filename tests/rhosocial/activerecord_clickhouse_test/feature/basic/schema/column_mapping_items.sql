-- ClickHouse schema for basic/column_mapping_items table
CREATE TABLE IF NOT EXISTS column_mapping_items (
    id Int64,
    name String,
    item_total Int64,
    remarks Int64
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
