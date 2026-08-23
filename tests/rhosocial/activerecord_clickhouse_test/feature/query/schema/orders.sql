-- ClickHouse schema for query/orders table
CREATE TABLE IF NOT EXISTS orders (
    id Int64,
    user_id Int64 NOT NULL,
    order_number String NOT NULL,
    total_amount Decimal(10, 2) NOT NULL DEFAULT 0.0,
    status String NOT NULL DEFAULT 'pending',
    created_at DateTime64(6),
    updated_at DateTime64(6),
    INDEX idx_user_id (user_id) TYPE minmax
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
