## [v1.0.0.dev18] - 2026-06-15

### Added

- Added MySQL 9.7 new feature support: JSON Duality Views (CREATE/DROP DDL, DML operations with auto-increment), Hypergraph Optimizer per-statement hints (SET_VAR syntax), and DDL/function regression tests confirming correct behavior on MySQL 9.7. ([#41](https://github.com/rhosocial/python-activerecord-mysql/issues/41))
- Added MySQL expression-level `COLLATE` support with version-aware collation validation. ([#42](https://github.com/rhosocial/python-activerecord-mysql/issues/42))
- Added MySQL dialect support for datetime interval expressions (`EXTRACT`, `DATE_ADD`, `DATE_SUB`, `TIMESTAMPDIFF`) with EXPLAIN-backed index usage verification tests. ([#43](https://github.com/rhosocial/python-activerecord-mysql/issues/43))
- Added production-style MySQL time partition operation tests covering microsecond `DATETIME(6)` boundaries, future partition pre-creation, continuous partition pruning, index usage, and cold archival via `EXCHANGE PARTITION`. ([#44](https://github.com/rhosocial/python-activerecord-mysql/issues/44))



### Fixed

- Fixed RANGE COLUMNS partition routing assertion in async test and MySQLPartitionByKey crash when keys=[] produces empty KEY() partition ([#44](https://github.com/rhosocial/python-activerecord-mysql/issues/44))


## [v1.0.0.dev17] - 2026-05-30

### Changed

- Changed MySQLDialect to default to version=None instead of fixed version, requiring introspect_and_adapt() or explicit version before version-dependent features can be used. ([#39](https://github.com/rhosocial/python-activerecord-mysql/issues/39))


## [v1.0.0.dev16] - 2026-05-15

### Security

- **SECURITY**: Resolved SQL injection risks in MySQL backend ([#37](https://github.com/rhosocial/python-activerecord-mysql/issues/37))


## [v1.0.0.dev15] - 2026-05-01

### Added

- Added named query and named procedure CLI subcommands for MySQL backend. Added ConcurrencyAware protocol implementation for MySQL. Added named connection support with MySQL CLI integration. ([#35](https://github.com/rhosocial/python-activerecord-mysql/issues/35))



### Changed

- Aligned expression system with three architectural principles. Extracted CLI subcommands into modular cli/ subpackage. Moved threadsafety to MySQLBackendMixin. Removed ? → %s fallback from MySQL backend (now uses proper dialect placeholder conversion). Changed CI to install rhosocial-activerecord from git branch release/v1.0.0.dev25. ([#35](https://github.com/rhosocial/python-activerecord-mysql/issues/35))



### Fixed

- Fixed missing placeholder conversion in sync execute_many. Fixed ForUpdateClause handling without strength attribute. Fixed MySQL-specific protocols to properly extend generic protocols. Fixed _fetch_concurrency_hint call after connect. ([#35](https://github.com/rhosocial/python-activerecord-mysql/issues/35))


## [v1.0.0.dev14] - 2026-04-17

### Added

- Added backend examples for MySQL expression system ([#33](https://github.com/rhosocial/python-activerecord-mysql/issues/33))


## [v1.0.0.dev13] - 2026-04-13

### Added

- Added MySQL-specific features: INSERT IGNORE, REPLACE INTO, LOAD DATA INFILE, and JSON_TABLE expression support. Also includes introspection fixes for MySQL 8.4+ compatibility and binary log handling. ([#27](https://github.com/rhosocial/python-activerecord-mysql/issues/27))
- Added MySQL math enhanced functions including round_, pow, power, sqrt, mod, ceil, floor, trunc, max_, min_, and avg with proper Python-safe naming. ([#29](https://github.com/rhosocial/python-activerecord-mysql/issues/29))
- Added MySQL bitwise functions with native operator implementation (bit_count, bit_and, bit_or, bit_xor, bit_get_bit, bit_shift_left, bit_shift_right) ([#30](https://github.com/rhosocial/python-activerecord-mysql/issues/30))
- Add support for MySQL constraint expressions including foreign key ON DELETE/UPDATE clauses, CHECK constraints, and constraint detection protocol methods. ([#31](https://github.com/rhosocial/python-activerecord-mysql/issues/31))



### Fixed

- Internal code refactoring to improve maintainability by restructuring MySQL backend functions into category-based submodules. ([#28](https://github.com/rhosocial/python-activerecord-mysql/issues/28))


## [v1.0.0.dev12] - 2026-04-08

### Added

- Added connection pool context awareness support for session-based ActiveRecord usage. ([#23](https://github.com/rhosocial/python-activerecord-mysql/issues/23))
- Added transaction control support for MySQL dialect with TransactionControlSupport protocol implementation, including isolation level and access mode (READ ONLY/READ WRITE) control via SET TRANSACTION and START TRANSACTION statements. ([#24](https://github.com/rhosocial/python-activerecord-mysql/issues/24))
- Added MySQL server status introspector with configuration, performance metrics, connection info, storage details, and CLI status subcommand support. ([#25](https://github.com/rhosocial/python-activerecord-mysql/issues/25))


## [v1.0.0.dev11] - 2026-04-06

### Added

- Added EXPLAIN clause support with typed MySQLExplainResult and automatic connection recovery with dual-layer protection (pre-query check + error retry) for MySQL backend, including async concurrency documentation. ([#20](https://github.com/rhosocial/python-activerecord-mysql/issues/20))
- Improved MySQL backend CLI info command with connection status display and added introspect subcommand usage examples. ([#21](https://github.com/rhosocial/python-activerecord-mysql/issues/21))


## [v1.0.0.dev10] - 2026-03-28

### Added

- Added comprehensive introspection support for MySQL backend, including database schema discovery, metadata retrieval via SHOW commands, CLI introspection subcommand, and batch SQL execution via executescript method. ([#18](https://github.com/rhosocial/python-activerecord-mysql/issues/18))


## [v1.0.0.dev9] - 2026-03-22

### Added

- Added MySQL SET and VECTOR type support, and refactored backend code to extract common functionality into mixin classes for better code reuse between sync and async implementations. ([#16](https://github.com/rhosocial/python-activerecord-mysql/issues/16))


## [v1.0.0.dev8] - 2026-03-20

### Added

- Added MySQL CLI protocol support display with database introspection for version detection, enabling users to view detailed feature availability based on actual server version. ([#12](https://github.com/rhosocial/python-activerecord-mysql/issues/12))
- Added Python version-aware fixture selection for MySQL backend testing, enabling Python 3.10+ UnionType syntax support. ([#13](https://github.com/rhosocial/python-activerecord-mysql/issues/13))



### Fixed

- Reduced cognitive complexity in CLI display_info functions to comply with SonarCloud quality standards. ([#14](https://github.com/rhosocial/python-activerecord-mysql/issues/14))


## [v1.0.0.dev7] - 2026-03-13

### Added

- Added MySQL-specific DDL support including trigger DDL, enhanced CREATE TABLE with LIKE syntax, FULLTEXT/SPATIAL indexes, ENUM/SET type adapters, and spatial type functions. ([#10](https://github.com/rhosocial/python-activerecord-mysql/issues/10))


## [v1.0.0.dev6] - 2026-02-27

### Added

- Adapted MySQL backend to new expression-dialect architecture, rewritten backend tests, and added GROUP BY non-standard SQL behavior tests. ([#8](https://github.com/rhosocial/python-activerecord-mysql/issues/8))


## [1.0.0.dev5] - 2025-12-11

### Added

- Added full support for mapped column models and implemented support for annotated adapter query tests and type adapter tests in the MySQL backend. Enhanced test coverage for field and column mapping. ([#6](https://github.com/rhosocial/python-activerecord-mysql/issues/6))



### Fixed

- Resolved schema errors and test cleanup issues in the MySQL backend tests. ([#6](https://github.com/rhosocial/python-activerecord-mysql/issues/6))


## [1.0.0.dev4] - 2025-11-29

### Added

- Refactor type conversion system in MySQL backend with adapters (See [rhosocial/python-activerecord#20](https://github.com/rhosocial/python-activerecord/issues/20)) ([#3](https://github.com/rhosocial/python-activerecord-mysql/issues/3))
- Add backend CLI tool functionality for database operations ([#4](https://github.com/rhosocial/python-activerecord-mysql/issues/4))


## [1.0.0.dev3] - 2025-11-07

### Added

- Added new MySQL backend test infrastructure, including schema definitions, comprehensive query feature tests, extensive CTE support tests, detailed relation management tests, asynchronous backend adaptation, and backend-specific tests. ([#2](https://github.com/rhosocial/python-activerecord-mysql/issues/2))