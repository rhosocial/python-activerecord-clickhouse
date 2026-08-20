# docs/examples/worker_isolation_experiment/models.py
"""
Model definitions for Worker isolation experiment.

These models are designed to be compatible with the ClickHouse schema files
used in the testsuite.
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar, Optional

from pydantic import Field, EmailStr

from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base.field_proxy import FieldProxy
from rhosocial.activerecord.field import IntegerPKMixin, TimestampMixin
from rhosocial.activerecord.relation import HasMany, BelongsTo


class User(IntegerPKMixin, TimestampMixin, ActiveRecord):
    """User model for isolation experiment."""
    c: ClassVar[FieldProxy] = FieldProxy()
    __table_name__ = "users"

    id: Optional[int] = None
    username: str
    email: EmailStr
    age: Optional[int] = Field(None, ge=0, le=100)
    balance: float = 0.0
    is_active: bool = True

    orders: ClassVar[HasMany['Order']] = HasMany(foreign_key='user_id', inverse_of='user')
    posts: ClassVar[HasMany['Post']] = HasMany(foreign_key='user_id', inverse_of='user')


class Order(IntegerPKMixin, TimestampMixin, ActiveRecord):
    """Order model for isolation experiment."""
    c: ClassVar[FieldProxy] = FieldProxy()
    __table_name__ = "orders"

    id: Optional[int] = None
    user_id: int
    order_number: str
    total_amount: Decimal = Field(default=Decimal('0'))
    status: str = 'pending'

    user: ClassVar[BelongsTo['User']] = BelongsTo(foreign_key='user_id', inverse_of='orders')


class Post(IntegerPKMixin, TimestampMixin, ActiveRecord):
    """Post model for isolation experiment."""
    c: ClassVar[FieldProxy] = FieldProxy()
    __table_name__ = "posts"

    id: Optional[int] = None
    user_id: int
    title: str
    content: str = ''
    status: str = 'published'

    user: ClassVar[BelongsTo['User']] = BelongsTo(foreign_key='user_id', inverse_of='posts')


class Comment(IntegerPKMixin, TimestampMixin, ActiveRecord):
    """Comment model for isolation experiment."""
    c: ClassVar[FieldProxy] = FieldProxy()
    __table_name__ = "comments"

    id: Optional[int] = None
    user_id: int
    post_id: int
    content: str
    is_hidden: bool = False

    user: ClassVar[BelongsTo['User']] = BelongsTo(foreign_key='user_id', inverse_of='comments')
    post: ClassVar[BelongsTo['Post']] = BelongsTo(foreign_key='post_id', inverse_of='comments')


# Model list for easy iteration
ALL_MODELS = [User, Order, Post, Comment]
