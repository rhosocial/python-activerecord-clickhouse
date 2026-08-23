-- ClickHouse schema for mixins/versioned_products table
CREATE TABLE IF NOT EXISTS versioned_products (
    id Int64,
    name String NOT NULL,
    price Decimal(10, 2) NOT NULL DEFAULT 0.0,
    version Int32 NOT NULL DEFAULT 1
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
