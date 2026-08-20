# Scenarios

This chapter provides complete application examples of the ClickHouse backend in real-world business scenarios, helping developers understand how to correctly use rhosocial-activerecord in actual projects.

## Scenario List

### [Parallel Worker Processing](parallel_workers.md)

Demonstrates correct usage of ClickHouse backend in multi-process/async concurrent scenarios:

- **Multi-process Correct Usage**: `configure()` must be called within child processes
- **ClickHouse Async Advantage**: Native network I/O async, completely different from SQLite's thread pool simulation
- **Deadlock Handling**: InnoDB automatically detects deadlocks, recommended retry mechanism for production
- **Multi-threading Pitfalls**: ClickHouse has no `check_same_thread` protection, requires special attention

> 📖 **Companion Code**: Complete runnable experiment code is located in the `docs/examples/chapter_08_scenarios/parallel_workers/` directory.

## Relationship with Core Library Scenarios

This chapter is a ClickHouse-specific supplement to the [Core Library Scenarios Documentation](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/scenarios), focusing on:

- ClickHouse-specific concurrent behavior (row-level locking, deadlock detection)
- True advantages of async I/O (network latency scenarios)
- Key differences compared to SQLite

The general ActiveRecord usage patterns introduced in the core library scenarios (such as relationships, query building) also apply to the ClickHouse backend.
