# rhosocial-activerecord-clickhouse

ClickHouse backend implementation for [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord).

## Documentation / 文档

Please select your language / 请选择语言:

- [English Documentation](en_US/README.md)
- [中文文档 (Chinese)](zh_CN/README.md)

## Overview

The ClickHouse backend brings the ActiveRecord pattern to ClickHouse's columnar,
OLAP-oriented world. It is **honest about ClickHouse's semantics**: features that
ClickHouse does not support (ACID transactions, FOREIGN KEY / UNIQUE constraints,
triggers, UPSERT, FOR UPDATE, FULLTEXT, JSON_TABLE, spatial/vector types, stored
routines, MySQL admin commands, ...) raise `UnsupportedFeatureError` instead of
being silently emulated.

For the main ActiveRecord framework documentation, please visit the
[python-activerecord docs](https://github.com/rhosocial/python-activerecord/tree/docs/docs).
