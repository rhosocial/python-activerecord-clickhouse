# models.py - Async Model Definitions
# docs/examples/chapter_10_fastapi/models.py

from __future__ import annotations

import os
import sys

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from rhosocial.activerecord.field import IntegerPKMixin, TimestampMixin
from rhosocial.activerecord.model import AsyncActiveRecord
from rhosocial.activerecord.relation import BelongsTo, HasMany
from rhosocial.activerecord.relation.async_descriptors import (
    AsyncHasManyDescriptor,
    AsyncBelongsToDescriptor,
)


class AsyncUser(IntegerPKMixin, TimestampMixin, AsyncActiveRecord):
    """Async User model."""
    __table_name__ = "users"

    username: str
    email: str
    is_active: bool = True

    # Relationships
    posts: AsyncHasManyDescriptor = HasMany(
        "AsyncPost", foreign_key="user_id", back_populates="author"
    )
    comments: AsyncHasManyDescriptor = HasMany(
        "AsyncComment", foreign_key="user_id", back_populates="author"
    )


class AsyncPost(IntegerPKMixin, TimestampMixin, AsyncActiveRecord):
    """Async Post model."""
    __table_name__ = "posts"

    user_id: int
    title: str
    body: str = ""
    status: str = "draft"
    view_count: int = 0

    # Relationships
    author: AsyncBelongsToDescriptor = BelongsTo(
        "AsyncUser", foreign_key="user_id", back_populates="posts"
    )
    comments: AsyncHasManyDescriptor = HasMany(
        "AsyncComment", foreign_key="post_id", back_populates="post"
    )


class AsyncComment(IntegerPKMixin, TimestampMixin, AsyncActiveRecord):
    """Async Comment model."""
    __table_name__ = "comments"

    post_id: int
    user_id: int
    body: str
    is_approved: bool = False

    # Relationships
    post: AsyncBelongsToDescriptor = BelongsTo(
        "AsyncPost", foreign_key="post_id", back_populates="comments"
    )
    author: AsyncBelongsToDescriptor = BelongsTo(
        "AsyncUser", foreign_key="user_id", back_populates="comments"
    )
