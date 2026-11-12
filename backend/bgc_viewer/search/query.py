"""Translate structured filters into Tantivy queries.

A structured filter is the BGC Atlas ``FilterGroup``: a group joins its
conditions and nested groups with ``AND`` or ``OR``, and a condition compares
one field to a value with an operator. This module validates the JSON form of
that tree and builds a :class:`tantivy.Query` from it, ported from the Atlas
OpenSearch adapter (``lib/opensearch/query.ts``).

Two kinds of condition go beyond the field registry: ``contains`` on the
catch-all ``text`` field is the "any field contains" condition, and a
condition on :data:`RAW_QUERY_FIELD` runs a query-language string.

A condition that cannot become a clause is never skipped, since running the
rest would answer a broader question; every such condition is collected and
reported in one :class:`UnhonourableFilterError`. A condition whose value is
still blank (half-built in the UI) is dropped silently, as in Atlas.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Literal

from tantivy import FieldType, Index, Occur, Query

from .document import (
    OPERATORS_BY_KIND,
    PATH_TOKENIZER_PATTERN,
    SEARCH_FIELDS_BY_NAME,
    SearchField,
)
from .index import SearchError, parse_query

# Pseudo-field of a condition whose value is a query-language string.
RAW_QUERY_FIELD = "_query"
RAW_QUERY_OPERATORS: tuple[str, ...] = ("matches",)

# Operators that test for a value rather than compare one.
_VALUELESS_OPERATORS = frozenset({"exists", "not_exists"})

# Bounds on a filter tree, so a request cannot build an arbitrarily large query.
MAX_FILTER_DEPTH = 8
MAX_FILTER_CONDITIONS = 200
MAX_CONDITION_VALUES = 1000

Join = Literal["AND", "OR"]
Scalar = str | int | float


class InvalidFilterError(SearchError):
    """Raised when a filter is not a well-formed group of conditions."""

    code = "invalid_filter"


@dataclass(frozen=True)
class UnhonouredCondition:
    """A condition that could not become a clause, and why.

    ``reason`` is ``unknown_field``, ``unsupported_operator`` (with the
    operators the field does support), or ``unusable_value``.
    """

    field: str
    operator: str
    reason: str
    value: Any = None
    supported_operators: tuple[str, ...] = ()

    def describe(self) -> str:
        if self.reason == "unknown_field":
            return f'unknown field "{self.field}"'
        if self.reason == "unsupported_operator":
            supported = ", ".join(self.supported_operators)
            return (
                f'field "{self.field}" does not support operator '
                f'"{self.operator}" (supported: {supported})'
            )
        return (
            f'field "{self.field}" cannot use value {self.value!r} '
            f'with operator "{self.operator}"'
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "field": self.field,
            "operator": self.operator,
            "reason": self.reason,
            "value": self.value,
        }
        if self.supported_operators:
            result["supported_operators"] = list(self.supported_operators)
        return result


class UnhonourableFilterError(SearchError):
    """Raised when one or more conditions cannot become a clause.

    The message names each field and operator so a saved or shared filter can
    be repaired from it.
    """

    code = "unhonourable_filter"

    def __init__(self, conditions: list[UnhonouredCondition]) -> None:
        parts = "; ".join(condition.describe() for condition in conditions)
        subject, obj = (
            ("that condition", "it")
            if len(conditions) == 1
            else ("those conditions", "them")
        )
        super().__init__(
            f"Cannot run this filter: {parts}. Fix or remove {subject}; "
            f"running the filter without {obj} would answer a broader question."
        )
        self.conditions = tuple(conditions)


@dataclass(frozen=True)
class FilterCondition:
    """One field/operator/value comparison."""

    field: str
    operator: str
    value: Scalar | tuple[Scalar | None, ...] | None


@dataclass(frozen=True)
class FilterGroup:
    """Conditions and nested groups joined by one operator."""

    operator: Join
    conditions: tuple[FilterCondition, ...]
    groups: tuple[FilterGroup, ...]


def _parse_value(value: Any, where: str) -> Scalar | tuple[Scalar | None, ...] | None:
    def scalar(item: Any) -> bool:
        return item is None or (
            isinstance(item, (str, int, float)) and not isinstance(item, bool)
        )

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        if len(value) > MAX_CONDITION_VALUES:
            raise InvalidFilterError(
                f"{where}.value has more than {MAX_CONDITION_VALUES} values"
            )
        if not all(scalar(item) for item in value):
            raise InvalidFilterError(f"{where}.value must hold strings or numbers")
        # Nulls are kept: ``between`` reads ``[min, null]`` as an open bound.
        return tuple(value)
    if not scalar(value):
        raise InvalidFilterError(
            f"{where}.value must be a string, a number, or a list of them"
        )
    return value


def parse_filter_group(body: Any) -> FilterGroup:
    """Validate the JSON form of a filter into a :class:`FilterGroup`.

    A group is ``{"operator": "AND"|"OR", "conditions": [...], "groups":
    [...]}`` and a condition is ``{"field", "operator", "value"}``; other keys,
    such as the ids the Atlas builder assigns, are ignored. Raises
    :class:`InvalidFilterError` naming the offending path when the structure
    is wrong or exceeds the depth or condition limits.
    """
    count = 0

    def group(node: Any, where: str, depth: int) -> FilterGroup:
        nonlocal count
        if not isinstance(node, dict):
            raise InvalidFilterError(f"{where} must be an object")
        if depth > MAX_FILTER_DEPTH:
            raise InvalidFilterError(
                f"Filter groups nest deeper than {MAX_FILTER_DEPTH} levels"
            )
        operator = node.get("operator", "AND")
        if operator not in ("AND", "OR"):
            raise InvalidFilterError(f'{where}.operator must be "AND" or "OR"')
        raw_conditions = node.get("conditions", [])
        raw_groups = node.get("groups", [])
        if not isinstance(raw_conditions, list) or not isinstance(raw_groups, list):
            raise InvalidFilterError(f"{where}.conditions and .groups must be lists")

        conditions = []
        for i, raw in enumerate(raw_conditions):
            at = f"{where}.conditions[{i}]"
            if not isinstance(raw, dict):
                raise InvalidFilterError(f"{at} must be an object")
            field, op = raw.get("field"), raw.get("operator")
            if not isinstance(field, str) or not isinstance(op, str):
                raise InvalidFilterError(f"{at}.field and .operator must be strings")
            count += 1
            if count > MAX_FILTER_CONDITIONS:
                raise InvalidFilterError(
                    f"Filter has more than {MAX_FILTER_CONDITIONS} conditions"
                )
            conditions.append(
                FilterCondition(field, op, _parse_value(raw.get("value"), at))
            )
        groups = tuple(
            group(child, f"{where}.groups[{i}]", depth + 1)
            for i, child in enumerate(raw_groups)
        )
        return FilterGroup(operator, tuple(conditions), groups)

    return group(body, "filter", 1)


def _strings(value: Any) -> list[str]:
    items = value if isinstance(value, tuple) else (value,)
    return [
        text
        for text in (str(item).strip() for item in items if item is not None)
        if text
    ]


def _is_blank(condition: FilterCondition) -> bool:
    return condition.operator not in _VALUELESS_OPERATORS and not _strings(
        condition.value
    )


def _number(item: Any) -> float | None:
    if item is None or (isinstance(item, str) and not item.strip()):
        return None
    try:
        number = float(item)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _negate(query: Query) -> Query:
    # A boolean query whose only clauses are MustNot matches nothing, so the
    # exclusion is taken from the set of all regions.
    return Query.boolean_query(
        [(Occur.Must, Query.all_query()), (Occur.MustNot, query)]
    )


def _regex(index: Index, field: str, pattern: str) -> Query:
    return Query.regex_query(index.schema, field, pattern)


def _all_of(queries: list[Query]) -> Query:
    if len(queries) == 1:
        return queries[0]
    return Query.boolean_query([(Occur.Must, query) for query in queries])


def _exact_clause(
    index: Index, field: SearchField, operator: str, values: list[str]
) -> Query | None:
    schema = index.schema
    if operator in ("contains", "not_contains", "starts_with", "ends_with"):
        text = re.escape(values[0])
        pattern = {
            "starts_with": f"(?i){text}.*",
            "ends_with": f"(?i).*{text}",
        }.get(operator, f"(?i).*{text}.*")
        query = _regex(index, field.name, pattern)
        return _negate(query) if operator == "not_contains" else query
    if operator in ("equals", "not_equals"):
        query = Query.term_query(schema, field.name, values[0])
        return _negate(query) if operator == "not_equals" else query
    if operator in ("in", "not_in"):
        query = Query.term_set_query(schema, field.name, values)
        return _negate(query) if operator == "not_in" else query
    return None


def _word_clause(
    index: Index, field: SearchField, operator: str, values: list[str]
) -> Query | None:
    # Full-text and path fields hold words, so every word of the value must
    # occur inside some word of the field. The ``text`` field lowercases its
    # words; path components keep their case, hence the case-insensitive flag.
    text = " ".join(values)
    if field.tokenizer == "path":
        words = re.findall(PATH_TOKENIZER_PATTERN, text)
    else:
        words = [word.lower() for word in re.findall(r"[^\W_]+", text)]
    if not words:
        return None
    query = _all_of(
        [_regex(index, field.name, f"(?i).*{re.escape(word)}.*") for word in words]
    )
    return _negate(query) if operator == "not_contains" else query


def _integer_bounds(
    operator: str, number: float
) -> tuple[int | None, int | None] | None:
    """Integer bounds equivalent to a comparison with a possibly fractional number."""
    if operator == "gt":
        return math.floor(number) + 1, None
    if operator == "gte":
        return math.ceil(number), None
    if operator == "lt":
        return None, math.ceil(number) - 1
    if operator == "lte":
        return None, math.floor(number)
    if not number.is_integer():
        return None
    return int(number), int(number)


def _numeric_clause(
    index: Index, field: SearchField, operator: str, value: Any
) -> Query | None:
    is_integer = field.tokenizer == "integer"
    field_type = FieldType.Integer if is_integer else FieldType.Float

    def range_query(lower: float | None, upper: float | None) -> Query:
        return Query.range_query(
            index.schema, field.name, field_type, lower_bound=lower, upper_bound=upper
        )

    items = value if isinstance(value, tuple) else (value,)
    if operator == "between":
        low = _number(items[0]) if items else None
        high = _number(items[1]) if len(items) > 1 else low
        if low is None and high is None:
            return None
        if is_integer:
            return range_query(
                None if low is None else math.ceil(low),
                None if high is None else math.floor(high),
            )
        return range_query(low, high)

    number = _number(items[0]) if items else None
    if number is None:
        return None
    if is_integer:
        comparison = "equals" if operator == "not_equals" else operator
        bounds = _integer_bounds(comparison, number)
        query = Query.empty_query() if bounds is None else range_query(*bounds)
    else:
        query = {
            "gt": lambda: Query.range_query(
                index.schema, field.name, field_type, number, None, include_lower=False
            ),
            "gte": lambda: range_query(number, None),
            "lt": lambda: Query.range_query(
                index.schema, field.name, field_type, None, number, include_upper=False
            ),
            "lte": lambda: range_query(None, number),
        }.get(operator, lambda: range_query(number, number))()
    return _negate(query) if operator == "not_equals" else query


def _boolean_clause(
    index: Index, field: SearchField, operator: str, values: list[str]
) -> Query | None:
    text = values[0].lower()
    if text in ("true", "1", "yes"):
        flag = True
    elif text in ("false", "0", "no"):
        flag = False
    else:
        return None
    query = Query.term_query(index.schema, field.name, flag)
    return _negate(query) if operator == "not_equals" else query


def _condition_query(
    index: Index,
    condition: FilterCondition,
    unhonoured: list[UnhonouredCondition],
) -> Query | None:
    """Build one condition's clause, recording it when it cannot be built."""
    if _is_blank(condition):
        return None

    def reject(reason: str, supported: tuple[str, ...] = ()) -> None:
        unhonoured.append(
            UnhonouredCondition(
                condition.field,
                condition.operator,
                reason,
                (
                    list(condition.value)
                    if isinstance(condition.value, tuple)
                    else condition.value
                ),
                supported,
            )
        )

    if condition.field == RAW_QUERY_FIELD:
        if condition.operator not in RAW_QUERY_OPERATORS:
            reject("unsupported_operator", RAW_QUERY_OPERATORS)
            return None
        # Parser errors propagate as they do for a query string.
        return parse_query(index, " ".join(_strings(condition.value)))

    field = SEARCH_FIELDS_BY_NAME.get(condition.field)
    if field is None:
        reject("unknown_field")
        return None
    supported = OPERATORS_BY_KIND[field.kind]
    operator = condition.operator
    if operator not in supported:
        reject("unsupported_operator", supported)
        return None

    query: Query | None
    if operator in _VALUELESS_OPERATORS:
        query = Query.exists_query(field.name)
        query = _negate(query) if operator == "not_exists" else query
    elif field.kind == "exact":
        query = _exact_clause(index, field, operator, _strings(condition.value))
    elif field.kind in ("full_text", "path"):
        query = _word_clause(index, field, operator, _strings(condition.value))
    elif field.kind == "numeric":
        query = _numeric_clause(index, field, operator, condition.value)
    else:
        query = _boolean_clause(index, field, operator, _strings(condition.value))

    if query is None:
        reject("unusable_value", supported)
        return None
    # A filter clause either matches or not; its score carries no relevance.
    # A constant score lets equally matching regions tie, and ties keep index
    # order, instead of an order set by term statistics.
    return Query.const_score_query(query, 1.0)


def build_filter_query(index: Index, group: FilterGroup) -> Query:
    """Build the Tantivy query for ``group`` against ``index``.

    A group with no usable conditions matches every region. Raises
    :class:`UnhonourableFilterError` listing every condition that could not
    become a clause.
    """
    unhonoured: list[UnhonouredCondition] = []

    def build(node: FilterGroup) -> Query | None:
        clauses = [
            query
            for query in (
                *(_condition_query(index, c, unhonoured) for c in node.conditions),
                *(build(child) for child in node.groups),
            )
            if query is not None
        ]
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        occur = Occur.Should if node.operator == "OR" else Occur.Must
        return Query.boolean_query([(occur, clause) for clause in clauses])

    query = build(group)
    if unhonoured:
        raise UnhonourableFilterError(unhonoured)
    return query if query is not None else Query.all_query()
