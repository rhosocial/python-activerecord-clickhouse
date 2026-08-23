-- ClickHouse schema for basic/type_tests table
-- id is a UUID string; json_field stored as String
CREATE TABLE IF NOT EXISTS type_tests (
    id String,
    string_field String DEFAULT 'test string',
    int_field Int64 DEFAULT 42,
    float_field Float32 DEFAULT 3.14,
    decimal_field Float64 DEFAULT 10.99,
    bool_field Bool DEFAULT true,
    datetime_field String,
    json_field String,
    nullable_field Nullable(String)
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;