# Storage Engines

## Overview

ClickHouse supports multiple storage engines. This section covers commonly used storage engines and selection recommendations.

## Common Storage Engine Comparison

| Feature | InnoDB | MyISAM | Memory |
|---------|--------|--------|--------|
| Transaction Support | ✅ | ❌ | ❌ |
| Foreign Key Constraints | ✅ | ❌ | ❌ |
| Full-Text Index | ✅ (5.6+) | ✅ | ❌ |
| Lock Level | Row-level | Table-level | Table-level |
| Crash Recovery | ✅ | ❌ | ❌ |

## InnoDB (Recommended)

InnoDB is ClickHouse's default storage engine and is recommended for most scenarios:

```sql
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(255)
) ENGINE=InnoDB;
```

Features:
- Transaction support
- Foreign key support
- Row-level locking
- Automatic crash recovery

## MyISAM

Suitable for read-only or read-heavy scenarios:

```sql
CREATE TABLE logs (
    id INT PRIMARY KEY,
    message TEXT
) ENGINE=MyISAM;
```

Features:
- Full-text indexing
- Compact storage
- No transaction support

## Selection Recommendations

1. **Use InnoDB by default** - Unless you have specific requirements
2. **Read-only tables** - Consider MyISAM
3. **Temporary tables** - Consider Memory

💡 *AI Prompt:* "What is the difference between InnoDB and MyISAM?"
