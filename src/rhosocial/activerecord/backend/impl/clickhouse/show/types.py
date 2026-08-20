# src/rhosocial/activerecord/backend/impl/clickhouse/show_types.py
"""
ClickHouse SHOW command result types.

This module defines result dataclasses for ClickHouse SHOW commands.
These types provide structured access to SHOW command output.

.. warning::
    This module was copied from the MySQL backend template and contains
    MySQL-style SQL functions/show commands. ClickHouse uses different
    function names (e.g. ``JSONExtract*``) and a different SHOW command
    subset. May generate non-ClickHouse SQL; verify before use.
"""

from dataclasses import dataclass
from typing import Optional


# ==================== CREATE Statement Results ====================


@dataclass
class ShowCreateTableResult:
    """Result from SHOW CREATE TABLE command.

    Contains the complete CREATE TABLE statement for a table.

    Attributes:
        table_name: Name of the table.
        create_statement: Complete CREATE TABLE statement.
    """

    table_name: str
    create_statement: str


@dataclass
class ShowCreateViewResult:
    """Result from SHOW CREATE VIEW command.

    Contains the CREATE VIEW statement for a view.

    Attributes:
        view_name: Name of the view.
        create_statement: Complete CREATE VIEW statement.
        character_set_client: Client character set.
        collation_connection: Connection collation.
    """

    view_name: str
    create_statement: str
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None


@dataclass
class ShowCreateTriggerResult:
    """Result from SHOW CREATE TRIGGER command.

    Contains the CREATE TRIGGER statement for a trigger.

    Attributes:
        trigger_name: Name of the trigger.
        create_statement: Complete CREATE TRIGGER statement.
        character_set_client: Client character set.
        collation_connection: Connection collation.
        database_collation: Database collation.
    """

    trigger_name: str
    create_statement: str
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None
    database_collation: Optional[str] = None


@dataclass
class ShowCreateProcedureResult:
    """Result from SHOW CREATE PROCEDURE command.

    Contains the CREATE PROCEDURE statement.

    Attributes:
        procedure_name: Name of the procedure.
        create_statement: Complete CREATE PROCEDURE statement.
        character_set_client: Client character set.
        collation_connection: Connection collation.
        database_collation: Database collation.
    """

    procedure_name: str
    create_statement: str
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None
    database_collation: Optional[str] = None


@dataclass
class ShowCreateFunctionResult:
    """Result from SHOW CREATE FUNCTION command.

    Contains the CREATE FUNCTION statement.

    Attributes:
        function_name: Name of the function.
        create_statement: Complete CREATE FUNCTION statement.
        character_set_client: Client character set.
        collation_connection: Connection collation.
        database_collation: Database collation.
    """

    function_name: str
    create_statement: str
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None
    database_collation: Optional[str] = None


# ==================== Column Information Results ====================


@dataclass
class ShowColumnResult:
    """Result from SHOW [FULL] COLUMNS command.

    Contains column information for a table.

    Attributes:
        field: Column name.
        type: Column data type.
        null: Whether the column allows NULL ('YES' or 'NO').
        key: Key type ('PRI', 'UNI', 'MUL', or empty).
        default: Default value for the column.
        extra: Additional information (auto_increment, etc.).
        privileges: Column privileges (FULL mode only).
        comment: Column comment (FULL mode only).
    """

    field: str
    type: str
    null: str
    key: str
    default: Optional[str] = None
    extra: Optional[str] = None
    privileges: Optional[str] = None
    comment: Optional[str] = None


# ==================== Table Status Results ====================


@dataclass
class ShowTableStatusResult:
    """Result from SHOW TABLE STATUS command.

    Contains extensive table metadata.

    Attributes:
        name: Table name.
        engine: Storage engine.
        version: Table version number.
        row_format: Row format (Compact, Dynamic, etc.).
        rows: Estimated number of rows.
        avg_row_length: Average row length in bytes.
        data_length: Data file length in bytes.
        max_data_length: Maximum data file length.
        index_length: Index file length in bytes.
        data_free: Allocated but unused bytes.
        auto_increment: Next AUTO_INCREMENT value.
        create_time: Table creation time.
        update_time: Last update time.
        check_time: Last check time.
        collation: Table collation.
        checksum: Table checksum.
        create_options: Additional table options.
        comment: Table comment.
    """

    name: str
    engine: Optional[str] = None
    version: Optional[int] = None
    row_format: Optional[str] = None
    rows: Optional[int] = None
    avg_row_length: Optional[int] = None
    data_length: Optional[int] = None
    max_data_length: Optional[int] = None
    index_length: Optional[int] = None
    data_free: Optional[int] = None
    auto_increment: Optional[int] = None
    create_time: Optional[str] = None
    update_time: Optional[str] = None
    check_time: Optional[str] = None
    collation: Optional[str] = None
    checksum: Optional[str] = None
    create_options: Optional[str] = None
    comment: Optional[str] = None


# ==================== Index Information Results ====================


@dataclass
class ShowIndexResult:
    """Result from SHOW INDEX command.

    Contains index information for a table.
    Each row represents one column in an index.

    Attributes:
        table: Table name.
        non_unique: 1 if index allows duplicates, 0 if unique.
        key_name: Index name.
        seq_in_index: Column sequence number in index.
        column_name: Column name.
        collation: Column sort order ('A' for ascending, NULL for unsorted).
        cardinality: Estimated number of unique values.
        sub_part: Index prefix length (NULL if full column indexed).
        packed: How the key is packed (NULL if not packed).
        null: Whether the column allows NULL.
        index_type: Index type (BTREE, FULLTEXT, HASH, RTREE).
        comment: Index comment.
        index_comment: Index comment (ClickHouse 5.5+).
        visible: Whether index is visible to optimizer (ClickHouse 8.0+).
        expression: Expression for functional index (ClickHouse 8.0+).
    """

    table: str
    non_unique: int
    key_name: str
    seq_in_index: int
    column_name: Optional[str] = None
    collation: Optional[str] = None
    cardinality: Optional[int] = None
    sub_part: Optional[int] = None
    packed: Optional[str] = None
    null: Optional[str] = None
    index_type: str = "BTREE"
    comment: Optional[str] = None
    index_comment: Optional[str] = None
    visible: Optional[str] = None
    expression: Optional[str] = None


# ==================== Database and Table List Results ====================


@dataclass
class ShowTableResult:
    """Result from SHOW TABLES command.

    Attributes:
        name: Table name.
        table_type: Table type (BASE TABLE or VIEW), available in FULL mode.
    """

    name: str
    table_type: Optional[str] = None


@dataclass
class ShowDatabaseResult:
    """Result from SHOW DATABASES command.

    Attributes:
        name: Database name.
    """

    name: str


# ==================== Trigger Results ====================


@dataclass
class ShowTriggerResult:
    """Result from SHOW TRIGGERS command.

    Contains trigger information.

    Attributes:
        trigger: Trigger name.
        event: Trigger event (INSERT, UPDATE, DELETE).
        table: Table name.
        statement: Trigger body.
        timing: Trigger timing (BEFORE, AFTER).
        created: Creation time.
        sql_mode: SQL mode during creation.
        definer: Definer of the trigger.
        character_set_client: Client character set.
        collation_connection: Connection collation.
        database_collation: Database collation.
    """

    trigger: str
    event: str
    table: str
    statement: str
    timing: str
    created: Optional[str] = None
    sql_mode: Optional[str] = None
    definer: Optional[str] = None
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None
    database_collation: Optional[str] = None


# ==================== Procedure and Function Results ====================


@dataclass
class ShowProcedureResult:
    """Result from SHOW PROCEDURE STATUS command.

    Attributes:
        db: Database name.
        name: Procedure name.
        type: Always 'PROCEDURE'.
        definer: Definer of the procedure.
        modified: Last modification time.
        created: Creation time.
        security_type: Security type (DEFINER or INVOKER).
        comment: Procedure comment.
        character_set_client: Client character set.
        collation_connection: Connection collation.
        database_collation: Database collation.
    """

    db: str
    name: str
    type: str = "PROCEDURE"
    definer: Optional[str] = None
    modified: Optional[str] = None
    created: Optional[str] = None
    security_type: Optional[str] = None
    comment: Optional[str] = None
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None
    database_collation: Optional[str] = None


@dataclass
class ShowFunctionResult:
    """Result from SHOW FUNCTION STATUS command.

    Attributes:
        db: Database name.
        name: Function name.
        type: Always 'FUNCTION'.
        definer: Definer of the function.
        modified: Last modification time.
        created: Creation time.
        security_type: Security type (DEFINER or INVOKER).
        comment: Function comment.
        character_set_client: Client character set.
        collation_connection: Connection collation.
        database_collation: Database collation.
    """

    db: str
    name: str
    type: str = "FUNCTION"
    definer: Optional[str] = None
    modified: Optional[str] = None
    created: Optional[str] = None
    security_type: Optional[str] = None
    comment: Optional[str] = None
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None
    database_collation: Optional[str] = None


# ==================== Variables and Status Results ====================


@dataclass
class ShowVariableResult:
    """Result from SHOW VARIABLES command.

    Attributes:
        variable_name: Variable name.
        value: Variable value.
    """

    variable_name: str
    value: str


@dataclass
class ShowStatusResult:
    """Result from SHOW STATUS command.

    Attributes:
        variable_name: Status variable name.
        value: Status value.
    """

    variable_name: str
    value: str


# ==================== Warning and Error Results ====================


@dataclass
class ShowWarningResult:
    """Result from SHOW WARNINGS command.

    Attributes:
        level: Warning level (Note, Warning, Error).
        code: Warning code.
        message: Warning message.
    """

    level: str
    code: int
    message: str


@dataclass
class ShowCountResult:
    """Result from SHOW COUNT(*) WARNINGS/ERRORS command.

    Attributes:
        count: Number of warnings or errors.
    """

    count: int


# ==================== Grants Results ====================


@dataclass
class ShowGrantResult:
    """Result from SHOW GRANTS command.

    Attributes:
        grants: List of GRANT statements for the user.
    """

    grants: str


# ==================== Process List Results ====================


@dataclass
class ShowProcessListResult:
    """Result from SHOW PROCESSLIST command.

    Attributes:
        id: Connection identifier.
        user: ClickHouse user.
        host: Client host and port.
        command: Command type (Query, Sleep, etc.).
        time: Time in current state (seconds).
        db: Selected database.
        state: Thread state.
        info: Query text (NULL if not executing query, or in basic mode).
    """

    id: int
    user: str
    host: str
    command: str
    time: int
    db: Optional[str] = None
    state: Optional[str] = None
    info: Optional[str] = None


# ==================== Open Tables Results ====================


@dataclass
class ShowOpenTableResult:
    """Result from SHOW OPEN TABLES command.

    Attributes:
        database: Database name.
        table: Table name.
        in_use: Number of table locks in use.
        name_locked: Whether table name is locked.
    """

    database: str
    table: str
    in_use: int
    name_locked: int


# ==================== Engine Results ====================


@dataclass
class ShowEngineResult:
    """Result from SHOW ENGINES command.

    Attributes:
        engine: Storage engine name.
        support: Support level (YES, NO, DEFAULT).
        transactions: Whether engine supports transactions.
        xa: Whether engine supports XA transactions.
        savepoints: Whether engine supports savepoints.
    """

    engine: str
    support: str
    transactions: Optional[str] = None
    xa: Optional[str] = None
    savepoints: Optional[str] = None


# ==================== Charset and Collation Results ====================


@dataclass
class ShowCharsetResult:
    """Result from SHOW CHARACTER SET command.

    Attributes:
        charset: Character set name.
        description: Character set description.
        default_collation: Default collation name.
        maxlen: Maximum length of a character in bytes.
    """

    charset: str
    description: str
    default_collation: str
    maxlen: int


@dataclass
class ShowCollationResult:
    """Result from SHOW COLLATION command.

    Attributes:
        collation: Collation name.
        charset: Character set name.
        id: Collation ID.
        default: Whether this is the default collation for the charset.
        compiled: Whether the collation is compiled.
        sortlen: Sort length.
    """

    collation: str
    charset: str
    id: int
    default: str
    compiled: str
    sortlen: int


# ==================== Plugin Results ====================


@dataclass
class ShowPluginResult:
    """Result from SHOW PLUGINS command.

    Attributes:
        name: Plugin name.
        status: Plugin status (ACTIVE, INACTIVE, DISABLED, etc.).
        type: Plugin type (STORAGE ENGINE, INFORMATION_SCHEMA, etc.).
        library: Plugin library file name.
        license: Plugin license.
    """

    name: str
    status: str
    type: str
    library: Optional[str] = None
    license: Optional[str] = None


# ==================== Profile Results (Deprecated) ====================


@dataclass
class ShowProfileResult:
    """Result from SHOW PROFILE command.

    Note: Deprecated in ClickHouse 5.7+, use Performance Schema instead.

    Attributes:
        status: Profile status.
        duration: Duration in seconds.
        cpu_user: CPU user time (if CPU profile).
        cpu_system: CPU system time (if CPU profile).
        context_voluntary: Voluntary context switches (if BLOCK IO profile).
        context_involuntary: Involuntary context switches (if BLOCK IO profile).
        block_ops_in: Block operations in (if BLOCK IO profile).
        block_ops_out: Block operations out (if BLOCK IO profile).
        messages_sent: Messages sent (if IPC profile).
        messages_received: Messages received (if IPC profile).
        page_faults_major: Major page faults (if PAGE FAULTS profile).
        page_faults_minor: Minor page faults (if PAGE FAULTS profile).
        swaps: Number of swaps (if PAGE FAULTS profile).
        source_function: Source function name (if SOURCE profile).
        source_file: Source file name (if SOURCE profile).
        source_line: Source line number (if SOURCE profile).
    """

    status: str
    duration: float
    cpu_user: Optional[float] = None
    cpu_system: Optional[float] = None
    context_voluntary: Optional[int] = None
    context_involuntary: Optional[int] = None
    block_ops_in: Optional[int] = None
    block_ops_out: Optional[int] = None
    messages_sent: Optional[int] = None
    messages_received: Optional[int] = None
    page_faults_major: Optional[int] = None
    page_faults_minor: Optional[int] = None
    swaps: Optional[int] = None
    source_function: Optional[str] = None
    source_file: Optional[str] = None
    source_line: Optional[int] = None


@dataclass
class ShowProfilesResult:
    """Result from SHOW PROFILES command.

    Note: Deprecated in ClickHouse 5.7+, use Performance Schema instead.

    Attributes:
        query_id: Query identifier.
        duration: Query duration in seconds.
        query: Query text.
    """

    query_id: int
    duration: float
    query: str
