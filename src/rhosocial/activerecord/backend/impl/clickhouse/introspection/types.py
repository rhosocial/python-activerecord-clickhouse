# src/rhosocial/activerecord/backend/impl/clickhouse/introspection/types.py
"""ClickHouse-specific introspection results.

The core introspection types describe what every backend can be asked about —
tables, columns, indexes. ClickHouse exposes further facts that those shapes
cannot carry: how a MergeTree table's data is divided into partitions on disk,
the storage definition a table was created with, and six server-wide catalogues
(functions, dictionaries, clusters, quotas, users and roles). All are read here
as frozen dataclasses, one row per answer.

Naming, stated once and not translated anywhere below:

    ClickHouse has **no schema layer**. Its top-level namespace is called a
    *database* (``system.databases``, ``system.tables.database``), and an object
    is qualified by that database alone. The core introspection API calls that
    slot ``schema`` because most backends have both; when the core hands this
    backend a ``schema``, the value is a ClickHouse database name. The methods
    in :mod:`.introspector` therefore name the parameter ``database`` — that is
    what it is — and do not turn it into anything else.

So ``ClickHousePartitionInfo.database`` and ``ClickHouseTableEngineInfo.database``
hold a ClickHouse database name, the same string the server reports in
``system.parts.database`` / ``system.tables.database``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from rhosocial.activerecord.backend.introspection.types import ColumnDataProfile

__all__ = [
    "ClickHousePartitionInfo",
    "ClickHouseTableEngineInfo",
    "ClickHouseColumnDataProfile",
    "ClickHouseFunctionInfo",
    "ClickHouseDictionaryInfo",
    "ClickHouseClusterInfo",
    "ClickHouseQuotaInfo",
    "ClickHouseUserInfo",
    "ClickHouseRoleInfo",
]


@dataclass(frozen=True)
class ClickHousePartitionInfo:
    """One partition of a table, aggregated from its active parts.

    Built from ``system.parts`` grouped by ``partition_id``. Only *active* parts
    are read, because inactive parts are those a merge has already replaced and
    are waiting for removal: counting them would report the same rows twice.

    Args:
        partition_id: ``system.parts.partition_id`` — the identity ClickHouse
            itself uses (``DROP PARTITION ID '...'``), and the grouping key.
            A table declared without ``PARTITION BY`` has the single id
            ``'all'``.
        table_name: The table the partition belongs to.
        database: The ClickHouse database the table lives in.
        engine: The table engine, as ``system.parts.engine`` reports it.
        partition: ``system.parts.partition`` — the readable partition value
            the key produced (e.g. ``'202601'`` for ``toYYYYMM(date)``,
            ``'tuple()'`` for a table with no partition key). Kept beside the
            id because the id is a hash-like token for many key expressions.
        row_count: Sum of ``rows`` over the partition's active parts.
        bytes_on_disk: Sum of ``bytes_on_disk`` over the active parts.
        active_part_count: Number of active parts the partition consists of.
            A partition with more than one active part is normal: parts merge
            in the background.
        min_modification_time: Earliest ``modification_time`` among the active
            parts, or ``None`` when the server reports none.
        max_modification_time: Latest ``modification_time`` among them.
    """

    partition_id: str
    table_name: str
    database: str
    engine: str
    partition: Optional[str] = None
    row_count: int = 0
    bytes_on_disk: int = 0
    active_part_count: int = 0
    min_modification_time: Optional[datetime] = None
    max_modification_time: Optional[datetime] = None


@dataclass(frozen=True)
class ClickHouseTableEngineInfo:
    """The storage definition of one table, from ``system.tables``.

    Every field is the column of the same name on ``system.tables``. The key
    expressions are the ones the table was declared with; ClickHouse reports
    ``''`` (not ``None``) for a key the table does not have, so the empty string
    is passed through unchanged rather than being turned into a missing value
    the server never said.

    Args:
        table_name: ``system.tables.name``.
        database: The ClickHouse database the table lives in.
        engine: ``engine`` — the short engine name (``MergeTree``,
            ``ReplicatedMergeTree``, ``View``, ...).
        sorting_key: ``sorting_key`` — the ``ORDER BY`` expression.
        primary_key: ``primary_key`` — the primary key expression.
        partition_key: ``partition_key`` — the ``PARTITION BY`` expression.
        sampling_key: ``sampling_key`` — the ``SAMPLE BY`` expression.
        total_rows: ``total_rows`` as the server reports it; ``None`` when the
            server has no estimate (the column is ``Nullable(UInt64)`` and is
            empty for engines that do not track rows).
        total_bytes: ``total_bytes``, same treatment.
        comment: ``comment`` — ``''`` when the table has none.
    """

    table_name: str
    database: str
    engine: str
    sorting_key: Optional[str] = None
    primary_key: Optional[str] = None
    partition_key: Optional[str] = None
    sampling_key: Optional[str] = None
    total_rows: Optional[int] = None
    total_bytes: Optional[int] = None
    comment: Optional[str] = None


@dataclass
class ClickHouseColumnDataProfile(ColumnDataProfile):
    """A column profile carrying the runtime types ClickHouse reports.

    Named fields rather than ``extra`` entries, for the reason the PostgreSQL
    subclass states: these are this engine's own facts, and a consumer that
    knows it asked ClickHouse should read them off the object instead of
    guessing at dictionary keys.

    ``runtime_types`` is the fact no other engine in this family has, and it
    belongs here because of how ClickHouse stores a value. Elsewhere a column's
    type is a property of the *column*: PostgreSQL will not let a row hold
    something the declaration does not name, and SQLite's dynamic typing has no
    name to report at all. ClickHouse types compose -- ``Nullable``,
    ``LowCardinality``, ``Enum8``, ``DateTime64(3, 'UTC')``, ``Array(Tuple(...))``
    -- and the engine will name the type of the expression it evaluated rather
    than describe the declaration it stored. Grouping that name over the column
    is therefore a query about the *data*: on an ordinary column the set holds
    the one type the engine resolved for every row, and on a column whose values
    do not all resolve the same way it holds each of them, which is exactly what
    a reader of the declaration cannot see.

    The core profile keeps this slot out on purpose -- it is a real dialect
    difference, and the comment on
    :class:`~rhosocial.activerecord.backend.introspection.types.ColumnDataProfile`
    says so -- so the fact lives on the backend's own subclass, where a caller
    who asked ClickHouse can find it and a caller who asked PostgreSQL never
    has to ignore it.

    The list is sorted by the parser, because the aggregate's own order is not
    defined and two runs of the same profile must compare equal.
    """

    #: The type names the engine reported for the column's values, sorted.
    runtime_types: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClickHouseFunctionInfo:
    """One row of ``system.functions``.

    ClickHouse exposes its built-in functions and the functions a user or the
    server configuration added through the same catalogue. ``origin`` is the
    column that tells them apart — ``System`` for a built-in and a
    ``*UserDefined`` value for every other flavour — and it is passed through
    unchanged rather than normalised into a boolean, because the engine names
    four kinds.

    The optional text fields are ``''`` on the server when a function has no
    description, syntax, arguments or category, and are reported here as
    ``None`` so "the catalogue did not answer" is distinguishable from a
    function whose syntax really is empty. ``is_aggregate`` and
    ``case_insensitive`` are ``UInt8`` flags on the server and booleans here.
    """

    name: str
    is_aggregate: bool = False
    case_insensitive: bool = False
    alias_to: Optional[str] = None
    origin: Optional[str] = None
    description: Optional[str] = None
    syntax: Optional[str] = None
    arguments: Optional[str] = None
    categories: Optional[str] = None

    @property
    def is_user_defined(self) -> bool:
        """Whether ``origin`` names one of the user-defined flavours.

        The four origins ClickHouse documents are ``System``,
        ``SQLUserDefined``, ``ExecutableUserDefined`` and
        ``WasmUserDefined``. A ``System`` row is a built-in; the other three
        are functions the deployment added. ``None`` is not called
        user-defined: the server did not answer, and guessing would be worse
        than leaving the raw origin to speak for itself.
        """
        origin = getattr(self.origin, "value", self.origin)
        return origin in (
            "SQLUserDefined",
            "ExecutableUserDefined",
            "WasmUserDefined",
        )


@dataclass(frozen=True)
class ClickHouseDictionaryInfo:
    """One row of ``system.dictionaries``.

    ``database`` is ``''`` for a dictionary configured outside DDL (a
    configuration-file dictionary has no database); the empty string is the
    server's own answer and is kept rather than turned into ``None``. The four
    list fields are the key and attribute names/types the dictionary declares,
    read from the dotted catalogue columns ``key.names``, ``key.types``,
    ``attribute.names`` and ``attribute.types``.

    ``hit_rate`` and ``found_rate`` are ``Float64`` on the server; ``None``
    means the server did not report a rate (the dictionary has not served a
    query), not a rate of zero.
    """

    name: str
    database: str = ""
    uuid: Optional[str] = None
    status: Optional[str] = None
    is_lazy: bool = False
    origin: Optional[str] = None
    type: Optional[str] = None
    key_names: List[str] = field(default_factory=list)
    key_types: List[str] = field(default_factory=list)
    attribute_names: List[str] = field(default_factory=list)
    attribute_types: List[str] = field(default_factory=list)
    bytes_allocated: int = 0
    element_count: int = 0
    query_count: int = 0
    hit_rate: Optional[float] = None
    found_rate: Optional[float] = None
    lifetime_min: Optional[int] = None
    lifetime_max: Optional[int] = None
    loading_start_time: Optional[datetime] = None
    last_successful_update_time: Optional[datetime] = None
    error_count: int = 0
    last_exception: Optional[str] = None
    comment: Optional[str] = None


@dataclass(frozen=True)
class ClickHouseClusterInfo:
    """One server in one cluster, from ``system.clusters``.

    ``system.clusters`` is a row per shard/replica member, not a row per
    cluster, so the family is a listing of members and the cluster name is a
    field on each. ``shard_num`` and ``replica_num`` are one-based, as the
    engine reports them. The two flags are ``UInt8`` on the server and
    booleans here.
    """

    cluster: str
    shard_num: int
    replica_num: int
    shard_name: Optional[str] = None
    shard_weight: Optional[int] = None
    internal_replication: bool = False
    host_name: Optional[str] = None
    host_address: Optional[str] = None
    port: Optional[int] = None
    is_local: bool = False
    user: Optional[str] = None
    default_database: Optional[str] = None
    errors_count: int = 0
    slowdowns_count: int = 0
    estimated_recovery_time: Optional[int] = None


@dataclass(frozen=True)
class ClickHouseQuotaInfo:
    """One quota, from ``system.quotas``.

    ``keys`` and ``durations`` are arrays on the server. ``apply_to_all`` is
    the flag that says whether ``apply_to_list`` or ``apply_to_except`` is
    the meaningful side; both lists are kept exactly as the server answered.
    The prefix-bit fields are ``Nullable`` and stay ``None`` when the engine
    has nothing to report.
    """

    name: str
    id: Optional[str] = None
    storage: Optional[str] = None
    keys: List[str] = field(default_factory=list)
    durations: List[int] = field(default_factory=list)
    apply_to_all: bool = False
    apply_to_list: List[str] = field(default_factory=list)
    apply_to_except: List[str] = field(default_factory=list)
    ipv4_prefix_bits: Optional[int] = None
    ipv6_prefix_bits: Optional[int] = None


@dataclass(frozen=True)
class ClickHouseUserInfo:
    """One account, from ``system.users``.

    The catalogue reports authentication *types* but not credentials, and
    that is the line this type follows: ``auth_type`` is the list of methods
    the account accepts, while the parameters that would describe a
    credential are deliberately not projected. The role and grant lists are
    the account's default roles and its grantee limits, not an expansion of
    every effective privilege.
    """

    name: str
    id: Optional[str] = None
    storage: Optional[str] = None
    auth_type: List[str] = field(default_factory=list)
    default_roles_all: bool = False
    default_roles_list: List[str] = field(default_factory=list)
    default_roles_except: List[str] = field(default_factory=list)
    grantees_any: bool = False
    grantees_list: List[str] = field(default_factory=list)
    grantees_except: List[str] = field(default_factory=list)
    default_database: Optional[str] = None
    host_ip: List[str] = field(default_factory=list)
    host_names: List[str] = field(default_factory=list)
    host_names_regexp: List[str] = field(default_factory=list)
    host_names_like: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClickHouseRoleInfo:
    """One role, from ``system.roles``.

    ``system.roles`` answers the role's name, id and storage path and nothing
    else; what the role grants lives in ``system.grants`` and is deliberately
    a different family. ``storage`` is the access-control storage path the
    server reports, not a location this backend assembled.
    """

    name: str
    id: Optional[str] = None
    storage: Optional[str] = None
