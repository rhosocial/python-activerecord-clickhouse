# 存储引擎

## 概述

ClickHouse 支持多种存储引擎，本节介绍常用的存储引擎及选择建议。

## 常用存储引擎对比

| 特性 | InnoDB | MyISAM | Memory |
|-----|--------|--------|--------|
| 事务支持 | ✅ | ❌ | ❌ |
| 外键约束 | ✅ | ❌ | ❌ |
| 全文索引 | ✅ (5.6+) | ✅ | ❌ |
| 锁级别 | 行级 | 表级 | 表级 |
| 崩溃恢复 | ✅ | ❌ | ❌ |

## InnoDB (推荐)

InnoDB 是 ClickHouse 默认的存储引擎，推荐用于大多数场景：

```sql
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(255)
) ENGINE=InnoDB;
```

特点：
- 支持事务
- 支持外键
- 行级锁
- 崩溃自动恢复

## MyISAM

适用于只读或读多写少的场景：

```sql
CREATE TABLE logs (
    id INT PRIMARY KEY,
    message TEXT
) ENGINE=MyISAM;
```

特点：
- 全文索引
- 紧凑型存储
- 不支持事务

## 选择建议

1. **默认使用 InnoDB** - 除非有特殊需求
2. **只读表** - 可以考虑 MyISAM
3. **临时表** - 可以考虑 Memory

💡 *AI 提示词：* "InnoDB 和 MyISAM 有什么区别？"
