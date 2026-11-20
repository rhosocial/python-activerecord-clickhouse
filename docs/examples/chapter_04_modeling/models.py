# docs/examples/chapter_04_modeling/models.py
"""Chapter 4: declarative models on the ClickHouse backend.

The example shows four declaration surfaces working together:

1. ``UseSqlType`` + ClickHouse-native ``DataType`` instances in ``Annotated``
   fields — the column's SQL type is stated explicitly rather than inferred
   from the bare Python annotation;
2. reusable **mixins** (a plain :class:`IdentifiedMixin` for shared behaviour
   and a local :class:`ContentMixin` for fields and behaviour);
3. a ``table_name()`` class method — the model's declared table;
4. a ``FieldProxy`` on ``c`` for type-checked query conditions.

IDs are generated client-side by the backend on ``save()`` (ClickHouse has no
AUTO_INCREMENT), so the ``id`` field is an optional ``Int64`` on the model.
"""

import os
import sys
from typing import Annotated, ClassVar, Optional

from rhosocial.activerecord.base import FieldProxy, UseSqlType
from rhosocial.activerecord.backend.impl.clickhouse.backend import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseArrayType,
    ClickHouseFloat64Type,
    ClickHouseInt32Type,
    ClickHouseInt64Type,
    ClickHouseStringType,
)
from rhosocial.activerecord.model import ActiveRecord


class IdentifiedMixin:
    """A plain Python mixin: shared behaviour, no persisted fields."""

    @property
    def identity(self) -> str:
        return f"{type(self).__name__}:{self.id}"


class ContentMixin(ActiveRecord):
    """Reusable content fields; a mixin may be an ActiveRecord subclass."""

    title: Annotated[str, UseSqlType(ClickHouseStringType())]
    body: Annotated[str, UseSqlType(ClickHouseStringType())]

    @property
    def summary(self) -> str:
        """A derived, non-persisted property."""
        return self.body[:80] + "..." if len(self.body) > 80 else self.body


class User(IdentifiedMixin, ActiveRecord):
    """A user with explicitly declared ClickHouse column types."""

    c: ClassVar[FieldProxy] = FieldProxy()

    id: Annotated[Optional[int], UseSqlType(ClickHouseInt64Type())] = None
    username: Annotated[str, UseSqlType(ClickHouseStringType())]
    email: Annotated[str, UseSqlType(ClickHouseStringType())]
    score: Annotated[float, UseSqlType(ClickHouseFloat64Type())] = 0.0

    @classmethod
    def table_name(cls) -> str:
        return "example_users"


class Post(IdentifiedMixin, ContentMixin, ActiveRecord):
    """A post that reuses content fields and adds ClickHouse array storage."""

    c: ClassVar[FieldProxy] = FieldProxy()

    id: Annotated[Optional[int], UseSqlType(ClickHouseInt64Type())] = None
    user_id: Annotated[int, UseSqlType(ClickHouseInt64Type())]
    tags: Annotated[
        list[str],
        UseSqlType(ClickHouseArrayType(element_type=ClickHouseStringType())),
    ] = []
    views: Annotated[int, UseSqlType(ClickHouseInt32Type())] = 0

    @classmethod
    def table_name(cls) -> str:
        return "example_posts"


def build_config() -> ClickHouseConnectionConfig:
    return ClickHouseConnectionConfig(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        database=os.getenv("CLICKHOUSE_DATABASE", "test_db"),
        username=os.getenv("CLICKHOUSE_USER", "root"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "password"),
    )


def create_tables(backend: ClickHouseBackend) -> None:
    """Create the two demo tables with column types matching the models."""
    backend.execute(
        """
        CREATE TABLE IF NOT EXISTS example_users (
            id       Int64,
            username String,
            email    String,
            score    Float64
        ) ENGINE = MergeTree
        ORDER BY id
        SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1
        """
    )
    backend.execute(
        """
        CREATE TABLE IF NOT EXISTS example_posts (
            id      Int64,
            title   String,
            body    String,
            user_id Int64,
            tags    Array(String),
            views   Int32
        ) ENGINE = MergeTree
        ORDER BY id
        SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1
        """
    )


def main() -> None:
    config = build_config()
    try:
        # configure() binds the backend and negotiates the server version,
        # which opens the connection.
        User.configure(config, ClickHouseBackend)
    except Exception as error:  # noqa: BLE001 - any connection failure is the same answer here
        print(f"Could not connect to ClickHouse at {config.host}:{config.port}: {error}", file=sys.stderr)
        sys.exit(1)

    # Both models share one backend instance.
    Post.__backend__ = User.backend()
    backend = User.backend()

    try:
        create_tables(backend)

        alice = User(username="alice", email="alice@example.com", score=9.5)
        alice.save()

        post = Post(
            title="Columnar storage",
            body="ClickHouse stores columns, not rows." * 5,
            user_id=alice.id,
            tags=["clickhouse", "activerecord"],
        )
        post.save()

        # FieldProxy builds a typed condition bound to User.table_name().
        found = User.find_one(User.c.username == "alice")
        print("Found user:", found.username, "id:", found.id)
        print("Post id:", post.id, "summary:", post.summary)

        younger = User.query().where(User.c.score < 10).all()
        print("Users with score < 10:", [user.username for user in younger])
    finally:
        backend.execute("DROP TABLE IF EXISTS example_posts")
        backend.execute("DROP TABLE IF EXISTS example_users")
        backend.disconnect()


if __name__ == "__main__":
    main()
