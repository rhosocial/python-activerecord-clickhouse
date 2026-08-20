# RhoSocial ActiveRecord ClickHouse Backend Knowledge Base

Welcome to the knowledge base for the RhoSocial ActiveRecord ClickHouse backend (`rhosocial-activerecord-clickhouse`). This directory contains essential information to help developers and AI assistants understand and work with the ClickHouse backend implementation.

## Purpose

This knowledge base serves to:

1. Document the architecture and design of the ClickHouse backend
2. Provide guidance for developers working with the codebase
3. Help AI assistants understand the repository structure and patterns
4. Document testing strategies and configurations
5. Explain ClickHouse-specific features and optimizations

## Files Overview

- `testing.md` - Comprehensive guide to testing the ClickHouse backend, including shared test suite integration and ClickHouse-specific test patterns
- `clickhouse_backend.md` - General knowledge base covering architecture, features, configuration, and development guidelines
- `architecture.md` - Detailed architectural overview of the ClickHouse backend implementation (coming soon)

## Getting Started

For AI assistants or developers new to this repository:

1. Start with `clickhouse_backend.md` for an overview of the backend implementation
2. Review `testing.md` to understand the testing approach and requirements
3. Examine the codebase structure following the patterns documented
4. Set up the ClickHouse server and run the test suite to verify the setup

## Key Concepts

- The ClickHouse backend is a separate package that extends the core `rhosocial-activerecord`
- It reuses test suites from `rhosocial-activerecord-testsuite` while providing ClickHouse-specific implementations
- The backend supports ClickHouse-specific features like JSON, full-text search, and window functions
- PYTHONPATH configuration is required for test execution due to the multi-package architecture