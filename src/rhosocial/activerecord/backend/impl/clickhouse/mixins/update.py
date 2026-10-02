# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/update.py
"""ClickHouse UPDATE statement support.

A ClickHouse UPDATE is a mutation: the server rewrites it into
``_CAST(if(<filter>, <new value>, <old value>), <type>)`` and recomputes row by
row. That rewritten expression evaluates the filter against the part's columns,
and until 26.7 it did not resolve a table qualifier -- ``WHERE t.id = 1`` was
read as a column literally named ``t.id`` and reported ``Missing columns``.

The qualifier is not optional information for a mutation. It is the only way to
name a column, and ClickHouse documents mutation filters against bare column
names. So below 26.7 this mixin renders an UPDATE's filter without the table
qualifier its Columns carry, because that is the form the server accepts. From
26.7 the server handles the qualifier itself and the columns are rendered as
they are, so the same statement runs unmodified on every maintained line.
"""

from typing import Any, List, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases, operators, predicates
from rhosocial.activerecord.backend.expression.core import Column, FunctionCall
from rhosocial.activerecord.backend.expression.query_parts import WhereClause

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseUpdateMixin:
    """UPDATE formatting for ClickHouse mutations."""

    #: First release whose mutation path resolves a qualified column name.
    #:
    #: The release notes for 26.7 record it under bug fixes: "Fix the usage of
    #: qualified column names (database.table.column) in the WHERE clause of
    #: mutations, such as DELETE FROM and ALTER TABLE ... UPDATE/DELETE, over
    #: MergeTree-family tables; previously such queries failed with a
    #: missing-columns error." (PR #109491, closing
    #: ClickHouse/ClickHouse#71760.) The maintained lines below it -- 25.8 LTS
    #: and 26.3 LTS -- do not carry the fix, so this is the boundary rather
    #: than a guess: both were verified to reject a qualified filter, and 26.7
    #: was verified to apply it.
    QUALIFIED_MUTATION_COLUMN_VERSION = (26, 7, 0)

    def supports_update_column_qualification(self) -> bool:
        """Whether an UPDATE filter may qualify a column with its table.

        False below 26.7, where the mutation engine reads ``t.col`` as one
        identifier and refuses the statement with Missing columns. True from
        26.7, which resolves the qualifier.
        """
        return self.version >= self.QUALIFIED_MUTATION_COLUMN_VERSION

    def _unqualify_columns(self, expr: Any) -> Any:
        """Rebuild ``expr`` with every Column stripped of its table qualifier.

        Why rebuild rather than render differently: a Column renders through
        the dialect's ``format_column``, which has no way to know it is being
        asked to render inside a mutation filter. The tree is walked and the
        Column nodes are replaced with equivalents that carry no table; the
        filter then renders bare, which is the form every ClickHouse release
        accepts.

        Why not mutate in place: the caller may hold the same Column in another
        predicate, and a mutation here would silently strip its qualifier
        there too.

        Returns the original object when nothing carries a table, so a filter
        built without qualifiers costs a walk and no allocation. Only the
        Column nodes are replaced; operators, functions and literals are
        shared as-is because they render identically either way.
        """
        if isinstance(expr, WhereClause):
            condition = self._unqualify_columns(expr.condition)
            if condition is expr.condition:
                return expr
            return WhereClause(self, condition=condition)

        if isinstance(expr, Column):
            if not expr.table:
                # Nothing to strip; the filter is already in the form the
                # mutation engine accepts.
                return expr
            # Same column, same alias and quoting, minus the table. schema_name
            # is deliberately not carried over: on ClickHouse it names a
            # database rather than a schema, and a mutation filter is not where
            # a database qualifier belongs.
            return Column(
                self,
                expr.name,
                alias=expr.alias,
                name_need_quote=expr.name_need_quote,
                alias_need_quote=expr.alias_need_quote,
            )

        # Recurse through the containers a filter expression can be built from.
        if isinstance(expr, predicates.ComparisonPredicate):
            left = self._unqualify_columns(expr.left)
            right = self._unqualify_columns(expr.right)
            if left is expr.left and right is expr.right:
                return expr
            return predicates.ComparisonPredicate(self, expr.op, left, right)

        if isinstance(expr, predicates.LogicalPredicate):
            operands = [self._unqualify_columns(p) for p in expr.predicates]
            if all(a is b for a, b in zip(operands, expr.predicates)):
                return expr
            return predicates.LogicalPredicate(self, expr.op, *operands)

        if isinstance(expr, predicates.LikePredicate):
            target = self._unqualify_columns(expr.expr)
            pattern = self._unqualify_columns(expr.pattern)
            if target is expr.expr and pattern is expr.pattern:
                return expr
            return predicates.LikePredicate(self, expr.op, target, pattern)

        if isinstance(expr, predicates.ILIKEExpression):
            column = self._unqualify_columns(expr.column)
            if column is expr.column:
                return expr
            return predicates.ILIKEExpression(
                self, column, expr.pattern, negate=expr.negate
            )

        if isinstance(expr, predicates.InPredicate):
            target = self._unqualify_columns(expr.expr)
            if target is expr.expr:
                return expr
            return predicates.InPredicate(self, target, expr.values)

        if isinstance(expr, predicates.BetweenPredicate):
            target = self._unqualify_columns(expr.expr)
            low = self._unqualify_columns(expr.low)
            high = self._unqualify_columns(expr.high)
            if target is expr.expr and low is expr.low and high is expr.high:
                return expr
            return predicates.BetweenPredicate(self, target, low, high)

        if isinstance(expr, FunctionCall):
            if not expr.args:
                return expr
            args = [self._unqualify_columns(a) for a in expr.args]
            if all(a is b for a, b in zip(args, expr.args)):
                return expr
            return FunctionCall(
                self,
                expr.func_name,
                *args,
                is_distinct=expr.is_distinct,
                alias=expr.alias,
                niladic=expr.niladic,
            )

        if isinstance(expr, operators.UnaryExpression):
            operand = self._unqualify_columns(expr.operand)
            if operand is expr.operand:
                return expr
            return operators.UnaryExpression(self, expr.op, operand)

        if isinstance(expr, operators.BinaryExpression):
            left = self._unqualify_columns(expr.left)
            right = self._unqualify_columns(expr.right)
            if left is expr.left and right is expr.right:
                return expr
            return operators.BinaryExpression(self, expr.op, left, right)

        if isinstance(expr, bases.BaseExpression):
            # Anything else (literals, subqueries, casts) either carries no
            # Column or is not something a mutation filter is built from.
            return expr

        return expr

    def format_update_statement(self, expr) -> Tuple[str, tuple]:
        """Format an UPDATE, dropping the filter's table qualifier if required.

        Why the qualifier is dropped, and only from the filter:

        A ClickHouse UPDATE is a mutation, so the server rewrites it into
        ``_CAST(if(<filter>, <new value>, <old value>), <type>)`` and recomputes
        row by row. That rewritten expression is evaluated against the part's
        columns by a resolver that, before 26.7, had no notion of a table
        qualifier. It read ``tasks.id`` as one identifier named ``tasks.id``,
        found no such column, and refused the statement::

            Missing columns: 'tasks.id' while processing:
            '_CAST(if(tasks.id = 381195967974322176, ...), 'Nullable(String)')

        This is a ClickHouse defect, not a design choice -- ClickHouse
        documents mutation filters written against bare column names, and
        qualifying one is accepted in SELECT on every version. It was fixed in
        26.7 by PR #109491, closing ClickHouse/ClickHouse#71760; the older
        maintained lines (25.8 LTS, 26.3 LTS) still reject it, which is why
        ``supports_update_column_qualification`` gates on the version at all.

        So on those lines the filter is rendered bare. The target table keeps
        its own qualification, because that is what names the table being
        mutated and the server resolves it normally. Nothing else about the
        statement changes, and from 26.7 the columns are rendered as they are,
        so one statement works unmodified across every maintained line.

        Everything else is left to the generic implementation rather than
        copied here, so this mixin cannot drift from it.
        """
        if self.supports_update_column_qualification() or not expr.where:
            # 26.7+ resolves the qualifier itself, so render the Columns as the
            # caller built them and let the server handle them.
            return super().format_update_statement(expr)

        from ....expression.statements.dml import UpdateExpression

        # Rebuild only the filter. The assignments, the table and any FROM are
        # passed through untouched so their rendering and parameters are
        # identical to what the generic implementation would have produced.
        stripped = UpdateExpression(
            self,
            table=expr.table,
            assignments=expr.assignments,
            from_=expr.from_,
            where=self._unqualify_columns(expr.where),
            returning=expr.returning,
        )
        return super().format_update_statement(stripped)