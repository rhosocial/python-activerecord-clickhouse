# Testing

This section covers testing for the ClickHouse backend.

## Contents

- [Test Configuration](configuration.md): test environment setup
- [Local ClickHouse Testing](local.md): local database testing

## Provider Responsibilities

As a backend implementation, the ClickHouse backend must implement the Provider interface to handle test environment setup and cleanup. This is critical for test isolation and correctness.

### Key Principles

1. **Environment Preparation**: The provider must:
   - Create database schemas (tables, indexes)
   - Establish database connections
   - Configure test models with ClickHouse-specific implementations

2. **Environment Cleanup**: The provider must:
   - Drop all test tables after each test
   - Close all cursors properly
   - Disconnect from the database

### Critical: Cleanup Order

The cleanup must follow this order to avoid issues:

```
Correct Order:
1. DROP TABLE statements (cleanup data)
2. Close cursors
3. Disconnect

Incorrect Order:
1. Disconnect first ❌
2. Then cleanup ❌ (connection already closed!)
```

### Common Issues

- **ClickHouse Async**: Failing to close cursors before disconnecting can cause `RuntimeError: Set changed size during iteration`
- **Table Conflicts**: Not dropping tables can cause "table already exists" errors
- **Data Contamination**: Not cleaning up can cause context-dependent tests to fail
- **Connection Issues**: Improper cleanup can lead to resource exhaustion

### Implementation Reference

See the test suite documentation for detailed implementation guidelines:
- `python-activerecord-testsuite/docs/en_US/README.md`
