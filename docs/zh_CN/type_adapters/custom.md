# 自定义类型适配器

## 概述

虽然 ClickHouse 后端提供了开箱即用的类型映射，但在某些场景下，你可能需要自定义类型转换逻辑。

## Pydantic 自定义类型

推荐使用 Pydantic 的自定义验证器来实现自定义类型转换：

```python
from typing import Any
from pydantic import field_validator
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import UUIDMixin, TimestampMixin
from typing import ClassVar
import json


class Address:
    def __init__(self, street: str, city: str, country: str):
        self.street = street
        self.city = city
        self.country = country
    
    def __str__(self) -> str:
        return f"{self.street}, {self.city}, {self.country}"
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Address':
        return cls(
            street=data.get('street', ''),
            city=data.get('city', ''),
            country=data.get('country', '')
        )


class User(UUIDMixin, TimestampMixin, ActiveRecord):
    name: str
    address: str  # 存储为 JSON 字符串
    
    c: ClassVar[FieldProxy] = FieldProxy()
    
    @field_validator('address', mode='before')
    @classmethod
    def parse_address(cls, v: Any) -> str:
        if isinstance(v, dict):
            return json.dumps(v)
        if isinstance(v, Address):
            return json.dumps({
                'street': v.street,
                'city': v.city,
                'country': v.country
            })
        return v
    
    def get_address(self) -> Address:
        if isinstance(self.address, str):
            return Address.from_dict(json.loads(self.address))
        return Address.from_dict(self.address)
    
    @classmethod
    def table_name(cls) -> str:
        return 'users'
```

## 使用自定义类型

```python
# 创建用户
user = User(
    name='Tom',
    address=Address(street='123 Main St', city='Beijing', country='China')
)
user.save()

# 读取用户
user = User.query().first()
address = user.get_address()
print(address.city)  # Beijing
```

💡 *AI 提示词：* "Pydantic 的 field_validator 和 model_validator 有什么区别？"
