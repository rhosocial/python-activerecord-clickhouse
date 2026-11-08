# 数据库自省

ClickHouse 后端回答三层问题：数据库**声明**了什么（读 `system.tables`、`system.columns` 及其邻表），服务端**留着**哪些关于自己的事实（六个 operational 家族被提供、被拒绝），以及一列的**行里实际放着什么**（三个读取行的家族）。三层都从 `backend.introspector` 进入，本页每个答案都是 ClickHouse 自己的答案：这个引擎怎么说，而不是一个跨方言消费者可以期待的形态。这些答案所依附的契约——探针承诺什么、数据画像携带什么、operational 家族是什么意思——由核心库陈述，本页不重复。

## ClickHouse 回答什么

自省契约里的每个问题在 dialect 上都有一个探针，而探针问的是**你面前这台服务器**，不是产品本身。提问之前先跑 `backend.introspect_and_adapt()`：它读取服务端版本并（据此）适配 dialect，而探针正是在适配后的 dialect 上求值的，因此低于版本下限的能力会按当前连接如实回答。

CLI 的类型表也由同一份映射派生，所以它提供的十六个类型与背后的开关不会彼此漂移。本 dialect 有十个回答 `True`——七个 catalogue 家族加三个读取行的家族。另外六个被提供但被拒绝，因为 ClickHouse 没有统计收集器、没有依赖图，也没有本后端会读取的原生 DDL 获取途径。请先读 `False` 那几行：`False` 说的是"这台服务器无法回答这个问题"，绝不是"答案为空或为零"。

| 类型 | 探针 | 答案 | 读取 | `NAME` |
|------|------|------|------|--------|
| `tables` | `supports_table_introspection()` | `True` | `system.tables` | 拒绝 |
| `views` | `supports_view_introspection()` | `True` | `system.tables`（视图引擎） | 视图，可选 |
| `columns` | `supports_column_introspection()` | `True` | `system.columns` | 表，必填 |
| `indexes` | `supports_index_introspection()` | `True` | `system.data_skipping_indices` | 表，必填 |
| `partitions` | `supports_partition_introspection()` | `True` | `system.parts`，仅 active part | 表，必填 |
| `table-engine` | `supports_table_engine_introspection()` | `True` | `system.tables` | 表，必填 |
| `database` | `supports_database_info()` | `True` | `system.databases` | 拒绝 |
| `unused-indexes` | `supports_unused_indexes_detection()` | `False` | — | 拒绝 |
| `table-stats` | `supports_table_stats()` | `False` | — | 拒绝 |
| `runtime` | `supports_runtime_stats()` | `False` | — | 拒绝 |
| `index-stats` | `supports_index_stats()` | `False` | — | 拒绝 |
| `dependencies` | `supports_object_dependencies()` | `False` | — | 对象，可选 |
| `ddl` | `supports_ddl_extraction()` | `False` | — | 表，必填 |
| `column-profiles` | `supports_column_data_profile()` | `True` | 行本身 | 表，必填 |
| `value-samples` | `supports_column_value_sample()` | `True` | 行本身 | 表，必填 |
| `join-coverage` | `supports_join_coverage()` | `True` | 行本身，两张表 | 左表，必填 |

`partitions` 与 `table-engine` 是本后端自己的家族，不是核心的：它们各自挂在本后端 mixin 里声明的开关上，也各有自己的结果类型。核心的 `supports_partition_info()` 按继承保持 `False`，因为这里没有可供 `True` 承诺的核心分区方法；CLI 读的是本后端自己的开关，不是核心的。

没有对应 CLI 类型的探针也在说话。`supports_foreign_key_introspection()` 与 `supports_trigger_introspection()` 回答 `False`，因为本引擎既不声明也不强制外键，且根本没有触发器——它们的类型**不在** CLI 词汇表里，而不是"提供后再拒绝"：回答 `False` 的开关说的是"这台服务器无法回答"，词汇表里缺席的词说的是"本后端从不问"。同一条区分也让 `show.*` 不进入 `introspect`：`SHOW` 与 `system.*` 并不等价，而这里每个类型都读 `system.*`。`supports_table_storage_introspection()` 回答 `True`，这正是表行携带 `size_bytes` 的原因，它读自 `system.tables.total_bytes`；`data_size_bytes` 与 `index_size_bytes` 保持 `None`，因为 ClickHouse 的数据以磁盘上的 part 形式存放，跳数索引是引擎自己维护的稀疏结构、不是数据的第二份副本——这个拆分是本引擎不保留的事实，不是缺口。`supports_extensions()` 保持 `False`：本后端没有声明任何附加组件目录。

### 回答 False 的六个

`unused-indexes` 没有东西可读。ClickHouse 不保留按索引计数的访问计数器：它仅有的索引行是主键与跳数索引，两者都没有"是否被用过"的埋点，因此没有哪种视图的行可以被称作未使用。回答 `True` 就会要求一个这里并不存在的查询格式化器。

`table-stats` 要的是按表的读写计数器，ClickHouse 一个也不留。`system.parts` 描述数据如何存放——part 大小、行数、分区边界——而不是表被读了多少次，也没有 `performance_schema` 之类的东西来补上这一差额。

`runtime` 是六个里唯一"缺失属于接线选择而非缺少度量"的家族：本后端通过自己的 `status` 自省器读取 `system.metrics` 与 `system.events`，暴露引擎的实时 gauge 与计数，而这里没有任何东西渲染核心的 runtime 家族。因此 CLI 的 `runtime` 类型是被拒绝的，而不是换一种形态回答。

`index-stats` 是 `unused-indexes` 的另一半，失败原因相同、只多走一步：连"用了多少"这个问题都没有计数器可读，所以这个家族既没有数据源也没有查询。

`dependencies` 需要一个记录"谁依赖谁"的目录。ClickHouse 不声明外键，本后端也不从它读取依赖图，因此没有边可返回，一个名字也无法收窄一张不存在的图。

`ddl` 需要引擎保留的文本。本后端没有读取 `SHOW CREATE` 语句的实现，因此 `get_ddl_statement()` 没有东西可交回，CLI 的分支若真被走到就会以退出 1 结束。开关保持 `False`，正常运行时这个分支根本到不了；`supports_ddl_extraction_native()` 也随之保持 `False`。

## 数据家族是聚合

`system.*` 里没有任何按列的分布可以读。`system.columns` 描述一列的**声明**——类型、默认值、codec、注释——而 `system.parts` 描述数据如何落在磁盘上；两者都不回答"这一列有多少行是 NULL"或"它有多少个不同取值"。因此画像里的每个数字都是从行算出来的、精确的，并以时间为代价：每列一条 arm，每条 arm 都是对表的一次扫描。

语句是这些 arm 的一条 `UNION ALL`，所以十列的表付十次扫描，但只付一次往返。聚合用精确的 `COUNT(DISTINCT ...)`，而不用 `uniq` 或 `uniqCombined`：后两者是本引擎的近似去重计数，而画像没有词能描述它们产生的东西——`aggregate` 会声称精确计数，`sample` 会声称只读了行的子集，而近似读完每一行却把答案取整。精确形式还让 `distinct_count == row_count` 继续可用作唯一性信号，任何估算都承载不了这一点。

每一行都被打上 `source='aggregate'`，它是投影进行里的，不是事后贴上的，因此把这份画像与别的引擎的估算放在一起比较的消费者，无需知道是谁回答的就能区分二者。没有 `collected_at`：聚合按构造就是当前的，一个时间戳会让它看起来像过期的估算。

有两种形态是这条 union 的代价。ClickHouse 拒绝各 arm 在某一列上类型不一致的 `UNION ALL`——它会寻找超类型，找不到就报错——因此 `min_value` 与 `max_value` 在每个 arm 里都被转成 `Nullable(String)`，而不是留作列自身的类型。数字是精确的；端点以文本到达，数值端点需经 `Decimal` 读回。空的列清单回答零行，从 `system.one` 读而不是裸 `SELECT`，因为 ClickHouse 只允许 `WHERE` 作用在一个来源上；真实表总至少有一列，所以这个分支是为一条必须能渲染的语句而存在。

某一列的类型若被这些聚合拒绝，整条语句失败，而不是丢掉那一列的 arm：`Array`、`Map`、`Tuple` 在 ClickHouse 里既没有 `MIN`/`MAX` 也没有 `COUNT(DISTINCT)`。静默缺失的一列，会变成一份声称表比实际列数更少的画像。

画像的空值计数是 `SUM` 套一个 `CASE`，不是 `countIf`，并且与 `COUNT(*)` 共用一次扫描，因为二者是同一个分数的两半。`SUM` 是共享渲染器能正确拼出的写法；`SUM` 还让空表回答 `0`，解析器因行数为零把它读成"没有分数"——而不是"这一列没有 NULL"。另外两个数据家族各有自己的代价。`value-samples` 是对该列的一次 `GROUP BY` 加一次分组排序：`ORDER BY COUNT(*) DESC` 让答案成为"最频繁的取值"而不是"最前面的取值"，并列时按取值排序使同一查询两次运行结果一致，limit 是绑定参数。ClickHouse 把 NULL 归成一个真实的行，所以含 NULL 的列在清单里有一行 NULL——通常还是最频繁的那一行——它是值域的一个成员，不是格式化器要过滤掉的值；`frequency` 保持 `None`，因为引擎报告的是计数，而分母是画像携带的行数。`join-coverage` 在两侧都数去重后的非 NULL 值，分母用 `NULLIF` 守护，使没有可匹配值的列回答 `None` 而不是 `0.0`："什么都没匹配上"与"根本没有东西可匹配"得以区分。这里没有 `* 1.0`，因为 ClickHouse 对两个整数做 `/` 已经给出浮点份额。类型不做归一：值按自身类型比较，因此不相关的类型永不相等，分数对那次连接是一个真实的零，而不是对引擎并未执行的转换的度量。

### 运行时类型

本后端返回的画像是 `ClickHouseColumnDataProfile`，即核心画像加一个具名字段：`runtime_types`。它存在的原因是 ClickHouse 存放值的方式。在别处，列的类型是**列**的属性；ClickHouse 的类型可以复合——`Nullable`、`LowCardinality`、`Enum8`、`DateTime64(3, 'UTC')`、`Array(Tuple(...))`——而引擎命名的是它求值那个表达式的类型，而不是它存储的声明。把这个名字在该列上分组，因此是一个关于**数据**的查询：普通列持有引擎为每一行解析出的那一个类型，而取值并非都以同一方式解析的列则持有其中每一个，这恰恰是读声明的人看不见的东西。

核心有意不保留这个槽——它是真实的方言差异——因此这个事实住在后端自己的子类上：问过 ClickHouse 的调用者找得到它，问别家引擎的调用者从不需要忽略它。投影是与同一扫描共用的一个聚合，所以这个事实不额外付一次扫描：

```
groupUniqArray(toTypeName(`note`)) AS `runtime_types`
```

清单在解析器里排序，不在 SQL 里，因为聚合自身的顺序未定义，而同一份画像的两次运行必须可比较相等。驱动把数组交回成 list 或 tuple 都能处理；裸字符串按它本来就是的单元素集合处理。`None` 变成空清单而不是缺失槽：语句返回的每一行都有这个数组，所以 `None` 只可能意味着该列没有产生任何值——空表——因而没有类型可命名。解析器在核心解析器看到之前就把 `runtime_types` 从行里取出，因此它是具名字段，而不是调用者要读源码才能发现的字典键。

```python
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host="localhost", port=8123, database="analytics",
    username="root", password="password",
)
backend = ClickHouseBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()

for profile in backend.introspector.list_column_data_profiles("events"):
    print(profile.column_name, profile.null_fraction, profile.runtime_types)
```

`Int32` 列报告唯一的名字 `Int32`。声明为 `Nullable(String)` 的列报告 string 家族里的一个名字，而引擎选了哪种拼写——`String` 还是 `Nullable(String)`——是服务器的答案，不是可以对着声明钉死的东西。

## 函数名大小写陷阱

这是读者能从本后端带走的最有用的一条事实，也是画像之所以写成现在这样的原因。共享的函数渲染器会把它渲染的每个函数名都转成大写。在 ClickHouse 上，这只对恰好是 SQL 标准拼写的名字正确，对其余每个 camelCase 名字都错。

ClickHouse 通过 `FunctionFactory` 与 `AggregateFunctionFactory` 解析函数名：先做精确匹配，再对一张**只**装着以 `Case::Insensitive` 注册的名字的表做**小写**匹配。这张表很小：`sum`、`count`、`min`、`max`、`nullIf` 以及少数 SQL 标准拼写在里面，所以 `SUM` 与 `COUNT` 大写无妨。`groupUniqArray`、`toTypeName`、`currentUser` 都以 `Case::Sensitive`（默认值）注册，而每个组合器后缀（`OrNull`、`If`、`State`）都是按**写出来的**名字尾部匹配的。因此一个大写化的 camelCase 名字在两张表里都落空。

代价不是理论上的。`minOrNull` 被渲染成 `MINORNULL`，服务器回答 ``Function with name `MINORNULL` does not exist``——同一个提交上的两次 CI 运行、每次五个任务全部失败。渲染器无法知道一个名字落在哪张表里，所以本后端通过 `_engine_function()` 逐个请求注册过的拼写，原样送出：

```python
sql = self._engine_function("groupUniqArray", self._engine_function("toTypeName", column))
```

`_engine_function()` 把可选的操作符文本作为 `RawSQL` 节点交给 SQL，而不是 `FunctionCall`，正是为了让任何配套代码路径都不能再对它套一次大小写规则。操作数仍是它们自己的节点：列由 dialect 的标识符渲染器加引号并限定 catalog，字面量在 `Literal` 说的位置绑定。只有名字是原样的，绝不是整个调用。同一个 helper 也承载 `currentUser` 与 `version`——这两个状态读取的大小写不归共享渲染器决定，而后者正是后端版本检测所依赖的读取。

一个陷阱藏在另一个后面：引擎只回答查询里第一个无法解析的名字，所以修好 `MINORNULL` 之后才暴露出下一个。画像最初的形式请求 `groupUniqArray(typeof(col))`，而 `typeof` **根本不是 ClickHouse 函数**——它从未发布。对照 ClickHouse 发布的函数目录（常规函数、全部 195 个聚合函数、表函数与窗口函数）逐页核对，字符串 `typeof` 一次都没出现，大小写不敏感地算也没有；存在的是 `toTypeName`，一台真实服务器验证了这一点。现在渲染出的 arm 是

```
groupUniqArray(toTypeName(`id`)) AS `runtime_types`
CAST(MIN(`id`) AS Nullable(String)) AS `min_value`
```

离线的大小写守卫会拒绝渲染语句里的 `MINORNULL`、`MAXORNULL`、`GROUPUNIQARRAY`、`TOTYPENAME` 与 `CURRENTUSER`，因此将来某次改动若把其中一个交回共享渲染器，会在这里失败，而不是在五个 CI 任务上失败。

### 全 NULL 的端点

端点是 `MIN`/`MAX`，不是 `minOrNull`/`maxOrNull`，因为后两个名字无法活着穿过共享渲染器——那是同一个大小写陷阱，而 `MIN`/`MAX` 是这条 arm 里能穿过的两个名字。差异是某一类列的一个数字，而且是真实的限制，不是舍入细节。

没有累计到任何非 NULL 值时，朴素聚合回答的是**结果类型的默认值**，而 `OrNull` 组合器会强制给出 NULL。因此**每一行**都是 NULL 的列把那个默认值当作两个端点报出——字符串列就是空字符串——而 `minOrNull` 本会产生 NULL、解析器本会读成 `None`。画像另外两个数字仍然说明了发生过什么：`null_count` 等于 `row_count`，`null_fraction` 为 `1.0`，所以"每个值都是 NULL"这一事实保留了下来。失去的只是端点自己"没有测到任何值"的那声声明。

## 命令行

`python -m rhosocial.activerecord.backend.impl.clickhouse introspect` 问的是同一个自省器，因此 CLI 打印的就是库看到的东西，而不是第二份实现。十六个类型及其开关、`NAME` 规则见上表。`NAME` 对 `columns`、`indexes`、`partitions`、`table-engine`、`ddl`、`column-profiles`、`value-samples` 与 `join-coverage` 是表名，对 `views` 是视图本身；`dependencies` 收一个可选的对象名以收窄图；`tables`、`database` 与四个全库范围的 operational 家族**拒绝**名字，而不是解析后丢掉。必填名字缺失属于调用不完整（退出 1）；类型用不上的名字是命令拒绝的请求（退出 2）；开关回答 `False` 是以退出 2 拒绝并输出 `Error: <type> introspection is not supported by this server`；连接失败或视图不存在是退出 1。

`--column` 为 `value-samples` 指定列，也为 `join-coverage` 指定左列；`--right-table` 与 `--right-column` 只被 `join-coverage` 读取。类型不读的旗标会被拒绝（退出 2），理由与"没人读的名字"相同：被静默丢掉的参数会产生一次成功的运行，却读起来像回答了一个更窄的问题。`--limit` 只在给出时才转发，数字归属于自省器自己的默认值。`column-profiles` 向 stderr 打一行提示——画像由行聚合而来，`source='aggregate'`，并按每列一次全扫描计价——从而让机器可读格式保持可解析。

```bash
python -m rhosocial.activerecord.backend.impl.clickhouse introspect column-profiles events \
    --host localhost --database analytics --user root --password password

python -m rhosocial.activerecord.backend.impl.clickhouse introspect value-samples events \
    --column status --limit 20 --database analytics --user root --password password
```

`runtime_types` 随行穿过序列化，而不被提升为共享列。序列化器遍历 dataclass，因此该字段作为自己的数组出现在五个核心数字旁，交给 JSON 调用者；表格格式则把它显示在自己的单元格里。它从不被折进 `extra`，也从不被提升进公共画像形态，因为只有本引擎能回答的事实，不该放进每个引擎都必须填的槽。

## 版本与可用性下限

这些家族没有确立版本下限。十六个类型挂在按当前连接适配后的 dialect 求值的能力开关上，而不是这里写死的版本号；三个数据家族只需要普通的聚合与 `system.*` 关系，本后端声明的每个版本——25.8、26.3 与 26.7——都提供它们。回答 `False` 的探针仍是完整的答案：它说的是这里无法提问，这与"数据库没有任何东西可报告"是不同的陈述。

其余子命令见 [CLI 用法](../cli/README.md)；本后端选择拒绝而非模拟的边界见 [不支持的功能](../capabilities/unsupported.md)。
