-- ClickHouse schema for basic/pydantic_validated_models table
CREATE TABLE IF NOT EXISTS pydantic_validated_models (
    id Int64,
    code String,
    quantity Int64,
    step_count Int64,
    price Decimal(10, 2),
    start_at DateTime64(6),
    end_at DateTime64(6),
    status String,
    normalized_name String,
    created_token String
) ENGINE = MergeTree
ORDER BY id
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
