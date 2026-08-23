-- ClickHouse schema for query/extended_orders table
CREATE TABLE IF NOT EXISTS extended_orders (
    id Int64,
    user_id Int64 NOT NULL,
    order_number String NOT NULL,
    total_amount Decimal(10, 2) NOT NULL DEFAULT 0.0,
    status String NOT NULL DEFAULT 'pending',
    priority String NOT NULL DEFAULT 'medium',
    region String NOT NULL DEFAULT 'default',
    category String,
    product String,
    department String,
    year String,
    quarter String,
    created_at DateTime,
    updated_at DateTime,
    INDEX idx_user_id (user_id) TYPE minmax,
    INDEX idx_status (status) TYPE minmax,
    INDEX idx_priority (priority) TYPE minmax,
    INDEX idx_region (region) TYPE minmax
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
