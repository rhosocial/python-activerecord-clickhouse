-- ClickHouse schema for basic/type_adapter_tests table
CREATE TABLE IF NOT EXISTS type_adapter_tests (
    id Int64,
    name String,
    optional_name Nullable(String),
    optional_age Nullable(Int64),
    last_login Nullable(String),
    is_premium Nullable(Bool),
    unsupported_union String,
    custom_bool String,
    optional_custom_bool Nullable(String)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;