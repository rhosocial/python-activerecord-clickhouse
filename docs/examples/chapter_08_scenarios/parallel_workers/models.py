# models.py - Shared Model Definitions for Parallel Worker Experiments (ClickHouse Version)
# docs/examples/chapter_12_scenarios/parallel_workers/models.py
"""
Model hierarchy:
    User  --(has_many)--> Post  --(has_many)--> Comment
    User  <--(belongs_to)-- Post
    Post  <--(belongs_to)-- Comment
    User  <--(belongs_to)-- Comment (comment author)

Each model provides both synchronous (inheriting ActiveRecord) and asynchronous
(inheriting AsyncActiveRecord) versions with identical method names.
Async version only requires adding await.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar, Optional

from rhosocial.activerecord.base.field_proxy import FieldProxy
from rhosocial.activerecord.field import IntegerPKMixin, TimestampMixin
from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord
from rhosocial.activerecord.relation import BelongsTo, HasMany
from rhosocial.activerecord.relation.async_descriptors import (
    AsyncBelongsTo,
    AsyncHasMany,
)


# ─────────────────────────────────────────
# Synchronous Models
# ─────────────────────────────────────────


class User(IntegerPKMixin, TimestampMixin, ActiveRecord):
    """Blog user (synchronous)"""

    __table_name__ = "users"

    id: Optional[int] = None
    username: str
    email: str
    is_active: bool = True

    c: ClassVar[FieldProxy] = FieldProxy()

    posts: ClassVar[HasMany[Post]] = HasMany(foreign_key="user_id", inverse_of="author")
    comments: ClassVar[HasMany[Comment]] = HasMany(foreign_key="user_id", inverse_of="author")


class Post(IntegerPKMixin, TimestampMixin, ActiveRecord):
    """Blog post (synchronous)"""

    __table_name__ = "posts"

    id: Optional[int] = None
    user_id: int
    title: str
    body: str
    status: str = "draft"  # draft / processing / published
    view_count: int = 0

    c: ClassVar[FieldProxy] = FieldProxy()

    author: ClassVar[BelongsTo[User]] = BelongsTo(foreign_key="user_id", inverse_of="posts")
    comments: ClassVar[HasMany[Comment]] = HasMany(foreign_key="post_id", inverse_of="post")


class Comment(IntegerPKMixin, TimestampMixin, ActiveRecord):
    """Comment (synchronous)"""

    __table_name__ = "comments"

    id: Optional[int] = None
    post_id: int
    user_id: int
    body: str
    is_approved: bool = False

    c: ClassVar[FieldProxy] = FieldProxy()

    post: ClassVar[BelongsTo[Post]] = BelongsTo(foreign_key="post_id", inverse_of="comments")
    author: ClassVar[BelongsTo[User]] = BelongsTo(foreign_key="user_id", inverse_of="comments")


# ─────────────────────────────────────────
# Asynchronous Models (identical method names to sync version, add await)
# ─────────────────────────────────────────


class AsyncUser(IntegerPKMixin, TimestampMixin, AsyncActiveRecord):
    """Blog user (asynchronous)"""

    __table_name__ = "users"

    id: Optional[int] = None
    username: str
    email: str
    is_active: bool = True

    c: ClassVar[FieldProxy] = FieldProxy()

    posts: ClassVar[AsyncHasMany[AsyncPost]] = AsyncHasMany(foreign_key="user_id", inverse_of="author")
    comments: ClassVar[AsyncHasMany[AsyncComment]] = AsyncHasMany(foreign_key="user_id", inverse_of="author")


class AsyncPost(IntegerPKMixin, TimestampMixin, AsyncActiveRecord):
    """Blog post (asynchronous)"""

    __table_name__ = "posts"

    id: Optional[int] = None
    user_id: int
    title: str
    body: str
    status: str = "draft"
    view_count: int = 0

    c: ClassVar[FieldProxy] = FieldProxy()

    author: ClassVar[AsyncBelongsTo[AsyncUser]] = AsyncBelongsTo(foreign_key="user_id", inverse_of="posts")
    comments: ClassVar[AsyncHasMany[AsyncComment]] = AsyncHasMany(foreign_key="post_id", inverse_of="post")


class AsyncComment(IntegerPKMixin, TimestampMixin, AsyncActiveRecord):
    """Comment (asynchronous)"""

    __table_name__ = "comments"

    id: Optional[int] = None
    post_id: int
    user_id: int
    body: str
    is_approved: bool = False

    c: ClassVar[FieldProxy] = FieldProxy()

    post: ClassVar[AsyncBelongsTo[AsyncPost]] = AsyncBelongsTo(foreign_key="post_id", inverse_of="comments")
    author: ClassVar[AsyncBelongsTo[AsyncUser]] = AsyncBelongsTo(foreign_key="user_id", inverse_of="comments")


# ─────────────────────────────────────────
# Table Creation DDL (ClickHouse)
# ─────────────────────────────────────────

SCHEMA_SQL = """\
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id         INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username   VARCHAR(64)  NOT NULL,
    email      VARCHAR(255) NOT NULL,
    is_active  TINYINT(1)   NOT NULL DEFAULT 1,
    created_at DATETIME(6)  NULL,
    updated_at DATETIME(6)  NULL,
    UNIQUE KEY uq_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE posts (
    id         INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id    INT          NOT NULL,
    title      VARCHAR(255) NOT NULL,
    body       TEXT         NOT NULL DEFAULT (''),
    status     VARCHAR(20)  NOT NULL DEFAULT 'draft',
    view_count INT          NOT NULL DEFAULT 0,
    created_at DATETIME(6)  NULL,
    updated_at DATETIME(6)  NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_status  (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE comments (
    id          INT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    post_id     INT         NOT NULL,
    user_id     INT         NOT NULL,
    body        TEXT        NOT NULL,
    is_approved TINYINT(1)  NOT NULL DEFAULT 0,
    created_at  DATETIME(6) NULL,
    updated_at  DATETIME(6) NULL,
    INDEX idx_post_id (post_id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def now_utc() -> datetime:
    """Return current UTC time (naive datetime, ClickHouse friendly)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
