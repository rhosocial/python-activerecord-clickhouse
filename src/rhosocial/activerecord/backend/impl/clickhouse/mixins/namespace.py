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

from typing import Any, List, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.objects import MaterializedView, View

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.objects import RelationObject, SchemaObject


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

    def engine_kind_condition(
        self,
        *,
        include_views: bool,
        offset: int,
    ) -> Tuple[str, List[Any]]:
        """Render the ``system.tables`` engine filter that selects views or tables.

        Args:
            include_views: ``True`` selects the view engines, ``False`` selects
                everything that is not one of them.
            offset: Index of the first bind placeholder in the statement, so the
                returned values land in the right parameter positions.

        Returns:
            ``(sql_fragment, params)`` where the fragment reads
            ``engine IN (...)`` or ``engine NOT IN (...)``.
        """
        p = self.get_parameter_placeholder
        holes = ", ".join(p(offset + i) for i in range(len(self.VIEW_ENGINES)))
        operator = "IN" if include_views else "NOT IN"
        return f"engine {operator} ({holes})", list(self.VIEW_ENGINES)