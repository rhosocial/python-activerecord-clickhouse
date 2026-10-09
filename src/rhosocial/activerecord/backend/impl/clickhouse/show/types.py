# src/rhosocial/activerecord/backend/impl/clickhouse/show/types.py
"""
ClickHouse SHOW command result types.

This module defines result dataclasses for ClickHouse SHOW commands.
These types provide structured access to SHOW command output.

Which of them can actually be filled
------------------------------------
Every statement modelled here is one this backend emits and parses against
26.7.3.19, and each result dataclass reads the column names the server actually
sent:

=================================  =========================================
statement                           ClickHouse output columns
=================================  =========================================
``SHOW CREATE TABLE`` / ``VIEW``    ``statement``
``SHOW [FULL] COLUMNS``             ``field``, ``type``, ``null``, ``key``,
                                    ``default``, ``extra`` (+ ``collation``,
                                    ``comment``, ``privileges`` under FULL)
``SHOW INDEX``                      ``table``, ``non_unique``, ``key_name``,
                                    ``seq_in_index``, ``pk_col``, ``collation``,
                                    ``cardinality``, ``sub_part``, ``packed``,
                                    ``null``, ``index_type``, ``comment``,
                                    ``index_comment``, ``visible``,
                                    ``expression``
``SHOW [FULL] TABLES``              ``name`` (+ ``engine`` under FULL)
``SHOW DATABASES``                  ``name``
``SHOW PROCESSLIST``                ``system.processes``'s 43 columns
``SHOW ENGINES``                    ``name``, eight ``supports_*`` flags,
                                    ``description``, ``syntax``, ``examples``,
                                    ``introduced_in``, ``related``
``SHOW GRANTS``                     one column, named after the statement text
                                    plus the requested output format
=================================  =========================================

Where the two databases disagree it is not cosmetic: reading MySQL's names
against ClickHouse's rows does not raise, it silently yields ``None``. Two of
those disagreements are structural rather than cosmetic and are documented on
the dataclasses — ``SHOW INDEX`` calls the indexed column ``pk_col``, and
``SHOW COLUMNS`` packs ``ALIAS`` / ``DEFAULT`` / ``MATERIALIZED`` expressions
all into ``default``.

The remaining dataclasses mirror MySQL's ``SHOW`` result shapes for statements
ClickHouse genuinely does not have. Their dialect formatters raise
``UnsupportedFeatureError`` naming a ClickHouse replacement, which is the
negotiation point a caller needs when switching backends.

There is deliberately no dataclass for a statement this package has no path to
at all — no expression class, no dialect formatter, no parser and no export:
those were removed rather than left as types nothing can construct.
"""

from dataclasses import dataclass
from typing import Any, Optional


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
        character_set_client: Always ``None`` on this backend. ClickHouse
            answers ``SHOW CREATE VIEW`` with a single ``statement`` column;
            the MySQL ``character_set_client`` / ``collation_connection``
            columns are not produced.
        collation_connection: Always ``None`` on this backend — see above.
    """

    view_name: str
    create_statement: str
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None


@dataclass
class ShowCreateTriggerResult:
    """Result from SHOW CREATE TRIGGER command.

    NOTE: MySQL-only command, not supported by ClickHouse. ``SHOW CREATE TRIGGER``
    is a ``SYNTAX_ERROR`` on 26.7.3.19 and the server has no triggers at all;
    ``format_show_create_trigger`` refuses with "ClickHouse does not support
    triggers". A SQL UDF (``CREATE FUNCTION ... AS``) invoked from the
    application is the ClickHouse equivalent.

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


# ==================== Column Information Results ====================


@dataclass
class ShowColumnResult:
    """Result from SHOW [FULL] COLUMNS command.

    ClickHouse has this statement. On 26.7.3.19 ``SHOW COLUMNS FROM db.t``
    answers with the lower-cased column names ``field``, ``type``, ``null``,
    ``key``, ``default``, ``extra``, and adds ``collation``, ``comment`` and
    ``privileges`` under ``FULL`` — the same list the ``SHOW`` reference page
    documents, so the mapping below is one-to-one.

    Attributes:
        field: Column name (ClickHouse's spelling; MySQL's is ``Field``).
        type: Column data type.
        null: ``'YES'`` if the type is ``Nullable``, ``'NO'`` otherwise.
        key: ``'PRI SOR'`` for a column in the sorting key, ``'PRI'`` for a
            primary-key-only column, ``''`` otherwise. Not MySQL's
            ``PRI``/``UNI``/``MUL`` — ClickHouse has no unique-constraint
            concept to report here.
        default: The expression of an ``ALIAS``, ``DEFAULT`` **or**
            ``MATERIALIZED`` column — the server reports all three through this
            one column — and ``None`` for a plain column.
        extra: Always ``''``: the server documents this column as unused.
        collation: Always ``None``: ClickHouse has no per-column collations.
            ``FULL`` only.
        comment: Column comment. ``FULL`` only.
        privileges: Column privilege string; the server documents this as
            "currently not available", and it is ``''``. ``FULL`` only.
    """

    field: str
    type: str
    null: str
    key: str
    default: Optional[str] = None
    extra: Optional[str] = None
    collation: Optional[str] = None
    comment: Optional[str] = None
    privileges: Optional[str] = None


# ==================== Table Status Results ====================


@dataclass
class ShowTableStatusResult:
    """Result from SHOW TABLE STATUS command.

    NOTE: MySQL-only command, not supported by ClickHouse: ``SHOW TABLE STATUS``
    is the one MySQL ``SHOW`` the server answers with ``UNKNOWN_TABLE``-style
    failure rather than a bare parse error on 26.7.3.19. ``format_show_table_status``
    refuses and points at ``system.tables``.

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

    ClickHouse has this statement — the ``SHOW`` reference page says it "mostly
    exists for compatibility with MySQL" — and answers with ClickHouse's own
    column names: ``table``, ``non_unique``, ``key_name``, ``seq_in_index``,
    ``pk_col``, ``collation``, ``cardinality``, ``sub_part``, ``packed``,
    ``null``, ``index_type``, ``comment``, ``index_comment``, ``visible``,
    ``expression``. Note ``pk_col``, which MySQL spells ``Column_name`` (the
    reference page still calls it ``column_name``; the 26.7.3.19 server sends
    ``pk_col``, and the server is what the parser reads).

    One statement, two kinds of row: the table's **primary key columns**
    (``key_name='PRIMARY'``, ``pk_col`` holding the column name,
    ``collation='A'``, ``seq_in_index`` counting from 1) and one row per **data
    skipping index** (``key_name`` = the index name, ``pk_col=''``,
    ``seq_in_index`` always 1, the indexed expression in ``expression``).

    Attributes:
        table_name: Table name (ClickHouse's column is ``table``).
        non_unique: Always ``1``: ClickHouse has no uniqueness constraints to
            report, so this is not a discriminator.
        key_name: Index name, or ``PRIMARY`` for the sorting-key rows.
        seq_in_index: Position within the primary key, or ``1`` for a skip index.
        column_name: Column name for a primary-key row — ClickHouse's ``pk_col``.
            Empty for a skip-index row, whose expression is in ``expression``.
        collation: ``'A'`` ascending, ``'D'`` descending, ``None`` unsorted.
        cardinality: Currently always ``0`` per the reference page.
        sub_part: Always ``None`` — ClickHouse has no index prefixes.
        packed: Always ``None`` — ClickHouse has no packed indexes.
        null: Unused by the server.
        index_type: ``PRIMARY``, ``MINMAX``, ``SET``, ``BLOOM_FILTER``,
            ``TEXT``, ... — ClickHouse's index kinds, not MySQL's ``BTREE``.
        comment: Currently always ``''``.
        index_comment: Always ``''`` — ClickHouse indexes cannot carry a comment.
        visible: Always ``'YES'``.
        expression: Index expression for a skip-index row, ``''`` for a
            primary-key row.
    """

    table_name: str
    non_unique: int
    key_name: str
    seq_in_index: int
    column_name: Optional[str] = None
    collation: Optional[str] = None
    cardinality: Optional[int] = None
    sub_part: Optional[str] = None
    packed: Optional[str] = None
    null: Optional[str] = None
    index_type: Optional[str] = None
    comment: Optional[str] = None
    index_comment: Optional[str] = None
    visible: Optional[str] = None
    expression: Optional[str] = None


# ==================== Database and Table List Results ====================


@dataclass
class ShowTableResult:
    """Result from SHOW TABLES command.

    Attributes:
        name: Table name. ClickHouse names this column ``name`` in both plain
            and ``FULL`` modes (MySQL names it after the database).
        table_type: Value of the second column ``SHOW FULL TABLES`` reports.
            On ClickHouse that is the **storage engine** (``MergeTree``,
            ``ReplicatedMergeTree``, ``View``, ...), not MySQL's ``BASE TABLE``
            / ``VIEW``; ``None`` in plain mode, which reports one column.
    """

    name: str
    table_type: Optional[str] = None


@dataclass
class ShowDatabaseResult:
    """Result from SHOW DATABASES command.

    Attributes:
        name: Database name. ClickHouse names this column ``name``; MySQL
            calls it ``Database``.
    """

    name: str


# ==================== Trigger Results ====================


@dataclass
class ShowTriggerResult:
    """Result from SHOW TRIGGERS command.

    ClickHouse has no triggers at all: ``SHOW TRIGGERS`` is a ``SYNTAX_ERROR``
    on 26.7.3.19 and the server's own grammar after ``SHOW`` offers no
    ``TRIGGERS``. The statement is not emitted — ``format_show_triggers``
    raises ``UnsupportedFeatureError`` with "ClickHouse does not support
    triggers" — so the refusal stays the negotiation point for a caller moving
    between backends. ``CREATE FUNCTION ... AS`` (an SQL UDF) plus a MATERIALIZED
    VIEW is the ClickHouse way to react to a row.

    Attributes:
        trigger_name: Trigger name.
        event: Trigger event (INSERT, UPDATE, DELETE).
        table_name: Table name.
        statement: Trigger body.
        timing: Trigger timing (BEFORE, AFTER).
        created: Creation time.
        sql_mode: SQL mode during creation.
        definer: Definer of the trigger.
        character_set_client: Client character set.
        collation_connection: Connection collation.
        database_collation: Database collation.
    """

    trigger_name: str
    event: str
    table_name: str
    statement: str
    timing: str
    created: Optional[str] = None
    sql_mode: Optional[str] = None
    definer: Optional[str] = None
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None
    database_collation: Optional[str] = None


# ==================== Variables and Status Results ====================


@dataclass
class ShowVariableResult:
    """Result from SHOW VARIABLES command.

    NOTE: MySQL-only command, not supported by ClickHouse. ``SHOW VARIABLES`` and
    ``SHOW GLOBAL VARIABLES`` are both ``SYNTAX_ERROR`` on 26.7.3.19 — the
    server's grammar after ``SHOW`` offers no ``VARIABLES``. The configuration
    lives in ``system.settings`` (what a query or session can change) and
    ``system.server_settings`` (the ``config.xml`` half), which is where
    ``ClickHouseStatusIntrospector.list_configuration()`` reads it from.

    Attributes:
        variable_name: Variable name.
        value: Variable value.
    """

    variable_name: str
    value: str


@dataclass
class ShowStatusResult:
    """Result from SHOW STATUS command.

    NOTE: MySQL-only command, not supported by ClickHouse. ``SHOW STATUS`` and
    ``SHOW GLOBAL STATUS`` are both ``SYNTAX_ERROR`` on 26.7.3.19. ClickHouse
    splits the same idea three ways: ``system.metrics`` (instantaneous gauges),
    ``system.events`` (monotonic counters) and ``system.asynchronous_metrics``
    (sampled OS / disk figures), which is exactly what
    ``ClickHouseStatusIntrospector.list_performance_metrics()`` reads.

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

    NOTE: MySQL-only command, not supported by ClickHouse. ``SHOW WARNINGS`` is
    a ``SYNTAX_ERROR`` on 26.7.3.19; the server reports a problem by raising it,
    and once configured records it in ``system.text_log`` / ``system.query_log``.

    Attributes:
        level: Warning level (Note, Warning, Error).
        code: Warning code.
        message: Warning message.
    """

    level: str
    code: int
    message: str


# ==================== Grants Results ====================


@dataclass
class ShowGrantResult:
    """Result from SHOW GRANTS command.

    ClickHouse has this statement — ``SHOW GRANTS [FOR user1 [, user2 ...]]
    [WITH IMPLICIT] [FINAL]`` — and returns one row per grant.

    The column it returns has no stable name: the server labels it after the
    statement text plus the output format the client asked for. Measured on
    26.7.3.19: ``SHOW GRANTS`` over HTTP with ``default_format=JSONEachRow``
    gives ``GRANTS``; ``SHOW GRANTS FORMAT JSONEachRow`` gives ``GRANTS FORMAT
    JSONEachRow``; over the native protocol, where clickhouse-connect appends
    ``FORMAT Native``, ``GRANTS FORMAT Native``; and ``SHOW GRANTS FOR root``
    gives ``GRANTS FOR root``. MySQL's ``Grants for`` never appears. The parser
    therefore reads the single value of each row rather than a named column.

    Attributes:
        grants: One GRANT statement.
    """

    grants: str


# ==================== Process List Results ====================


@dataclass
class ShowProcessListResult:
    """Result from SHOW PROCESSLIST command.

    ClickHouse has this statement and it is ``system.processes`` verbatim, so its
    columns are that table's 43 lower-cased names: ``is_initial_query``, ``user``,
    ``query_id``, ``address``, ``port``, ``initial_user``, ``initial_query_id``,
    ``initial_address``, ``initial_port``, ``interface``, ``os_user``,
    ``client_hostname``, ``client_name``, ``client_agent``, ``client_revision``,
    ``client_version_major``, ``client_version_minor``, ``client_version_patch``,
    ``http_method``, ``http_user_agent``, ``http_referer``, ``forwarded_for``,
    ``quota_key``, ``distributed_depth``, ``elapsed``, ``is_cancelled``,
    ``is_all_data_sent``, ``read_rows``, ``read_bytes``, ``total_rows_approx``,
    ``written_rows``, ``written_bytes``, ``memory_usage``,
    ``peak_memory_usage``, ``query``, ``normalized_query_hash``, ``query_kind``,
    ``thread_ids``, ``peak_threads_usage``, ``ProfileEvents``, ``Settings``,
    ``current_database``, ``is_internal`` (26.7.3.19).

    The MySQL-shaped field names below are kept so the result reads the same
    across backends, but two of them have no ClickHouse source and stay ``None``;
    see :attr:`command` and :attr:`state`. There is no ``FULL`` variant of the
    statement either, and none is needed — ``query`` already holds the full
    query text.

    Attributes:
        id: ``query_id`` — a UUID identifying the running query, **not** MySQL's
            integer connection id, which ClickHouse does not report here.
        user: The ClickHouse user the query runs as (``user``).
        host: ``address`` and ``port`` joined as ``host:port``, matching the
            shape of MySQL's ``Host`` column. The driver may hand back ``address``
            as an ``IPv6Address``; it is stringified here.
        command: Always ``None``. ``system.processes`` has no per-process command
            column, because every row *is* a running query.
        time: ``elapsed`` — seconds since the query started, as a float.
        db: ``current_database``.
        state: Always ``None``. There is no per-process state column; the closest
            server-side signal is ``is_cancelled``.
        info: ``query`` — the query text.
    """

    id: Optional[str]
    user: str
    host: Optional[str]
    command: Optional[str] = None
    time: Optional[float] = None
    db: Optional[str] = None
    state: Optional[str] = None
    info: Optional[str] = None


# ==================== Engine Results ====================


@dataclass
class ShowEngineResult:
    """Result from SHOW ENGINES command.

    ClickHouse has this statement and it is ``system.table_engines`` verbatim.
    Its columns are its own, and MySQL's ``Support`` / ``Transactions`` / ``XA`` /
    ``Savepoints`` are not among them — this result type therefore carries the
    eight ``supports_*`` capability flags ClickHouse actually reports, plus the
    engine's own documentation columns. On 26.7.3.19 the statement returns 83
    rows, one per engine.

    ``introduced_in`` is the only version-shaped column in the whole ``SHOW``
    set — it is where a table engine's introducing release would come from. It is
    **empty on this server**: ``SELECT count() FROM system.table_engines WHERE
    introduced_in != ''`` returns 0 across all 83 engines, so no version is
    claimed from it here.

    Attributes:
        engine: Engine name (ClickHouse's column is ``name``).
        supports_settings: Whether the engine accepts a ``SETTINGS`` clause.
        supports_skipping_indices: Whether it supports data skipping indices.
        supports_projections: Whether it supports projections.
        supports_sort_order: Whether it supports an explicit sorting key.
        supports_ttl: Whether it supports TTL.
        supports_replication: Whether it supports replication.
        supports_deduplication: Whether it supports block deduplication.
        supports_parallel_insert: Whether it supports parallel insert.
        description: Markdown description of the engine.
        syntax: Markdown syntax block.
        examples: Markdown examples block.
        introduced_in: Release the engine was introduced in — ``''`` on
            26.7.3.19, where the server populates none of them.
        related: Array of related engine names.
    """

    engine: str
    supports_settings: Optional[int] = None
    supports_skipping_indices: Optional[int] = None
    supports_projections: Optional[int] = None
    supports_sort_order: Optional[int] = None
    supports_ttl: Optional[int] = None
    supports_replication: Optional[int] = None
    supports_deduplication: Optional[int] = None
    supports_parallel_insert: Optional[int] = None
    description: Optional[str] = None
    syntax: Optional[str] = None
    examples: Optional[str] = None
    introduced_in: Optional[str] = None
    related: Optional[Any] = None


# ==================== Charset and Collation Results ====================


@dataclass
class ShowCharsetResult:
    """Result from SHOW CHARACTER SET command.

    NOTE: MySQL-only command, not supported by ClickHouse. ``SHOW CHARACTER SET``
    is a ``SYNTAX_ERROR`` on 26.7.3.19; the equivalents are the
    ``system.character_sets`` table and the ``output_format_*`` settings.

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

    NOTE: MySQL-only command, not supported by ClickHouse. ``SHOW COLLATION`` is a
    ``SYNTAX_ERROR`` on 26.7.3.19; the equivalents are the ``system.collations``
    table and, per query, ``ORDER BY`` on ``String`` (which is a byte-wise
    comparison, not a linguistic one).

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

    NOTE: MySQL-only command, not supported by ClickHouse, which has no plugin
    concept at all — ``SHOW PLUGINS`` is a ``SYNTAX_ERROR`` on 26.7.3.19 and the
    server's grammar after ``SHOW`` offers no ``PLUGINS``. The nearest things
    that exist are table engines, SQL UDFs, dictionaries and named collections.

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
