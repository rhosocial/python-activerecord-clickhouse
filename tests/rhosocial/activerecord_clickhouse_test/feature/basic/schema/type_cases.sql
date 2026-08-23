-- ClickHouse schema for basic/type_cases table
-- id is a UUID string; text fields stored as String
CREATE TABLE IF NOT EXISTS type_cases (
    id String,
    username String,
    email String,
    tiny_int String,
    small_int String,
    big_int String,
    float_val String,
    double_val String,
    decimal_val String,
    char_val String,
    varchar_val String,
    text_val String,
    date_val String,
    time_val String,
    timestamp_val String,
    blob_val String,
    json_val String,
    array_val String,
    is_active String
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
