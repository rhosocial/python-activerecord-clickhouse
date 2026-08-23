-- ClickHouse schema for basic/validated_field_users table
-- status is an Enum8 with explicit values
CREATE TABLE IF NOT EXISTS validated_field_users (
    id Int64,
    username String,
    email String,
    age Int64,
    balance Decimal(10, 2),
    credit_score Int64,
    status Enum8('active' = 1, 'inactive' = 2, 'banned' = 3, 'pending' = 4, 'suspended' = 5) DEFAULT 'active',
    is_active Bool DEFAULT true
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
