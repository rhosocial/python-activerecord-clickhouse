# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/namespace.py
"""ClickHouse name spaces and object kinds.

ClickHouse qualifies an object with exactly one namespace: the **database**.
There is no inner schema layer, so this mixin answers the two catalog switches
True and leaves ``supports_schema_qualification`` at its default ``False``. A
schema object that carries a ``schema_name`` therefore raises rather than being
rendered as a second namespace ClickHouse does not have.

Which level the database occupies used to be an accident. ``SchemaObject`` has
three slots -- catalog, schema, name -- and core's renderer walked them in a
fixed order with catalog first, so ClickHouse's one level lined up with the
outer slot and worked. Nothing in that method said ClickHouse had one level;
it said ClickHouse happened to fit the shape core assumed. Oracle is the
arrangement that does not fit: no catalog, an inner schema, and the outer slot
always empty. So the shape is now stated here rather than inherited:
:attr:`separator` and :meth:`format_qualified_name` are ClickHouse's, and they
name one level -- the database, which the object carries in ``catalog_name``.

The second thing this mixin owns is *how a kind of object is spelled in SQL*.
Two places used to decide that by guessing at the text of a statement keyword
or of a storage-engine name:

* dropping a materialized view emitted ``DROP VIEW``, because that is the only
  keyword the server accepts -- decided here, from the object's kind, so the
  reason is recorded rather than implied by the formatter's name;
* ``system.tables`` was filtered with ``engine LIKE '%View'``, a substring
  guess. ``VIEW_ENGINES`` names the closed set of engines that store a view,
  and both the table list and the view list read it.

Rendering of the name itself is not here: that is the core's per-kind
``format_<kind>_object``, reached through the object's own ``to_sql()``.

Where this mixin sits in ``ClickHouseDialect``'s base list is load-bearing.
``supports_catalog`` and ``supports_catalog_qualification`` have to win over the
defaults core's ``NamespaceMixin`` gives them, and ``format_qualified_name`` has
to win over the two-slot shape core spells. C3 linearisation gives the *first*
name in the list priority, so this mixin must stay ahead of ``NamespaceMixin``;
moved after it, ``CREATE TABLE analytics.users`` renders as ``users`` and no
test on earth catches it, because the statement is still well-formed.
"""

from typing import List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.objects import MaterializedView, View

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.objects import RelationObject, SchemaObject
    from rhosocial.activerecord.backend.introspection.types import TableType


class ClickHouseNamespaceMixin:
    """Catalog qualification and object-kind decisions for ClickHouse."""

    #: What goes between a name's levels. Core defaults to ``"."`` and
    #: ClickHouse spells a qualified name exactly that way -- ``db.table`` --
    #: so this states the fact rather than leaning on the default, which is
    #: what made the one-level shape invisible before.
    separator: str = "."

    #: The ``system.tables`` engines that store a view rather than a table.
    #: Anything not in this set is reported as a base table. ``LiveView`` and
    #: ``WindowView`` are here because they are views; they were previously
    #: swept in by ``LIKE '%View'`` without anyone having said so.
    VIEW_ENGINES: Tuple[str, ...] = ("View", "MaterializedView", "LiveView", "WindowView")

    #: Which introspection kind each view engine stores. The groups are
    #: disjoint and their union is :attr:`VIEW_ENGINES`; ``MaterializedView``
    #: is the one that reports as its own kind rather than as a plain view.
    VIEW_ENGINE_KINDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
        ("VIEW", ("View", "LiveView", "WindowView")),
        ("MATERIALIZED_VIEW", ("MaterializedView",)),
    )

    #: The DDL keyword ClickHouse uses to remove each kind of relation.
    #: ClickHouse has no ``DROP MATERIALIZED VIEW``: a materialized view is
    #: removed with ``DROP VIEW``, same as a plain view. Keying the mapping by
    #: kind makes that a stated fact about the engine rather than an accident
    #: of which formatter happens to run.
    DROP_KEYWORD_BY_KIND: Tuple[Tuple[type, str], ...] = (
        (View, "VIEW"),
        (MaterializedView, "VIEW"),
    )

    def supports_catalog(self) -> bool:
        """ClickHouse has a namespace above the object: the database."""
        return True

    def supports_catalog_qualification(self) -> bool:
        """The database is rendered when a name carries one (``db.table``)."""
        return True

    def format_qualified_name(self, expr: "SchemaObject") -> Tuple[str, tuple]:
        """Build *expr*'s qualified name: the database, then the name.

        ClickHouse has one namespace level and it is the database, which the
        object carries in ``catalog_name``. There is no second level to render,
        and ``schema_name`` cannot reach here: :meth:`validate_namespace` -- the
        call every ``format_<kind>_object`` makes first -- refuses a name
        carrying an inner schema, because rendering one would produce a name the
        server cannot resolve.

        This overrides core's two-slot spelling, which walks catalog, then
        schema, then name. For ClickHouse the two agree on every name that
        survives validation, so the rendered SQL is unchanged; what changes is
        that the shape is stated here instead of inherited. The override is what
        makes this mixin's position in ``ClickHouseDialect``'s base list matter
        for a second reason beyond the catalog switches.

        Args:
            expr: The object being named.

        Returns:
            A ``(sql, params)`` tuple. ``params`` is empty: an identifier is
            never a bind parameter.
        """
        parts: List[str] = []
        if expr.catalog_name:
            parts.append(
                self.format_identifier(expr.catalog_name, expr.catalog_need_quote)
            )
        parts.append(self.format_identifier(expr.name, expr.name_need_quote))
        return self.separator.join(parts), ()

    def drop_object_keyword(self, obj: "RelationObject") -> str:
        """Return the DDL keyword ClickHouse uses to drop *obj*.

        Args:
            obj: The relation being dropped.

        Returns:
            ``"VIEW"`` for a view or materialized view -- ClickHouse has no
            ``MATERIALIZED VIEW`` form of ``DROP``.

        Raises:
            UnsupportedFeatureError: The kind has no ClickHouse ``DROP`` form.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        for kind, keyword in self.DROP_KEYWORD_BY_KIND:
            if isinstance(obj, kind):
                return keyword
        raise UnsupportedFeatureError(
            self.name,
            f"DROP {type(obj).__name__}",
            suggestion=f"{self.name} can only drop views and materialized views.",
        )

    def engine_kind(self, engine: str) -> "TableType":
        """The relation kind an engine stores, in the introspection vocabulary.

        The Python counterpart of :meth:`engine_kind_predicate`: the result
        parser reads an engine string and needs the same closed set the SQL
        filter uses, so the split lives here rather than in a second table
        inside the introspector. An engine this backend does not know is an
        ordinary table; the engine string itself stays available to the caller.

        Args:
            engine: A ``system.tables.engine`` value.

        Returns:
            ``TableType.VIEW`` for the view engines that are plain views,
            ``TableType.MATERIALIZED_VIEW`` for ``MaterializedView``, and
            ``TableType.BASE_TABLE`` otherwise.
        """
        from rhosocial.activerecord.backend.introspection.types import TableType

        for kind_name, engines in self.VIEW_ENGINE_KINDS:
            if engine in engines:
                return TableType[kind_name]
        return TableType.BASE_TABLE

    def resolve_table_type(self, table_type) -> Optional["TableType"]:
        """Read a ``table_type`` filter in the introspection vocabulary.

        The accepted spellings are a :class:`TableType` member, its name
        (``"VIEW"``, ``"BASE_TABLE"``…), and the standard ``"TABLE"`` for a base
        table. An engine name is **not** a kind and resolves to ``None``; the
        filter keeps it as the engine comparison it used to be.

        Args:
            table_type: The filter value, or ``None`` for no filter.

        Returns:
            The matching member, or ``None`` when the value is an engine name
            (or no filter was given).
        """
        from rhosocial.activerecord.backend.introspection.types import TableType

        if table_type is None:
            return None
        if isinstance(table_type, TableType):
            return table_type
        spelled = str(table_type).strip().upper().replace(" ", "_")
        if spelled == "TABLE":
            spelled = TableType.BASE_TABLE.name
        return TableType.__members__.get(spelled)

    def is_system_table_type(self, table_type) -> bool:
        """Whether a ``table_type`` filter asks for system tables."""
        from rhosocial.activerecord.backend.introspection.types import TableType

        return self.resolve_table_type(table_type) is TableType.SYSTEM_TABLE

    def table_type_predicate(self, table_type):
        """The ``system.tables`` test that selects one relation kind.

        ``table_type`` is read in the introspection vocabulary
        (``TableType``), not as an engine name. ``VIEW`` has to select the
        engines that *store* a view; comparing ``engine = 'VIEW'`` matched
        nothing, because no ClickHouse engine is called ``VIEW``. A value that
        is not a kind is kept as an engine name, so an engine filter such as
        ``MergeTree`` still selects what it selected before.

        Kinds this catalogue reports no rows for answer with an always-false
        predicate. The answer is "none"; widening to every engine would claim
        rows the parser never reports as that kind.

        Args:
            table_type: A :class:`TableType` member, its name (``"VIEW"``,
                ``"BASE_TABLE"``…), the standard ``"TABLE"`` spelling, or an
                engine name.

        Returns:
            A predicate ready to join into a conjunction.
        """
        from rhosocial.activerecord.backend.expression import (
            Column,
            ComparisonPredicate,
            InPredicate,
            Literal,
            LogicalPredicate,
        )
        from rhosocial.activerecord.backend.introspection.types import TableType

        kind = self.resolve_table_type(table_type)
        if kind is None:
            return ComparisonPredicate(
                self, "eq", Column(self, "engine"), Literal(self, table_type)
            )
        if kind is TableType.SYSTEM_TABLE:
            # System tables are identified by their database, not by an
            # engine: the system database mixes several storage engines.
            return ComparisonPredicate(
                self,
                "eq",
                Column(self, "database"),
                Literal(self, "system", inline=True),
            )
        if kind is TableType.BASE_TABLE:
            return LogicalPredicate(
                self,
                "NOT",
                InPredicate(self, Column(self, "engine"), Literal(self, self.VIEW_ENGINES)),
            )
        for kind_name, engines in self.VIEW_ENGINE_KINDS:
            if TableType[kind_name] is kind:
                return InPredicate(self, Column(self, "engine"), Literal(self, engines))

        return ComparisonPredicate(
            self, "eq", Literal(self, 1, inline=True), Literal(self, 0, inline=True)
        )

    def engine_kind_predicate(self, *, include_views: bool):
        """The ``system.tables`` engine test that selects views or tables.

        The closed set travels as a bound list, exactly as it did when the
        fragment was text: the engines are values, and this backend's
        ``<engine> IN (%s, %s, ...)`` and ``NOT IN`` are what ``InPredicate``
        and its negation render. Nothing here counts placeholders -- the
        predicate's parameters are the ones it holds, and the enclosing
        statement concatenates them in projection order.

        Args:
            include_views: ``True`` selects the view engines, ``False`` selects
                everything that is not one of them.

        Returns:
            An ``InPredicate`` (``engine IN (...)``) or its negation
            (``engine NOT IN (...)``), ready to join into a conjunction.
        """
        from rhosocial.activerecord.backend.expression import (
            Column,
            InPredicate,
            Literal,
            LogicalPredicate,
        )

        membership = InPredicate(
            self,
            Column(self, "engine"),
            Literal(self, self.VIEW_ENGINES),
        )
        if include_views:
            return membership
        return LogicalPredicate(self, "NOT", membership)