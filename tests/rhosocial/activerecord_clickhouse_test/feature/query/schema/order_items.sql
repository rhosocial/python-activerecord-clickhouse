-- ClickHouse schema for query/order_items table
CREATE TABLE IF NOT EXISTS order_items (
    id Int64,
    order_id Int64 NOT NULL,
    product_name String NOT NULL,
    quantity Int32 NOT NULL DEFAULT 1,
    unit_price Decimal(10, 2) NOT NULL,
    subtotal Decimal(10, 2) NOT NULL DEFAULT 0.0,
    created_at DateTime,
    updated_at DateTime,
    INDEX idx_order_id (order_id) TYPE minmax
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
