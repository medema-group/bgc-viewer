"""Request parsing and response dataclasses for the region search endpoints.

This module owns the framework-agnostic pieces of the search HTTP layer:
parsing and validating the JSON request body into a :class:`SearchRequest`,
turning it into a Tantivy query (a query string or a structured filter),
building the :class:`SearchResponse` from the core
:mod:`bgc_viewer.search.index` result types, assembling the level-independent
:class:`SchemaResponse` from the field registry and the SQLite example table,
and mapping structured search errors onto HTTP status codes. The Flask routes
stay thin: each resolves its index, calls its own ``search_*`` function, wraps
the result in a response dataclass, and returns it through ``jsonify``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tantivy import Index, Query

from .document import PUBLIC_FIELDS, SEARCH_FIELDS_BY_NAME, PublicFieldInfo
from .index import (
    FacetBucket,
    RecordHit,
    Results,
    SearchError,
    SearchHit,
    Sort,
    UnknownFieldError,
    facet_counts,
    prepare_query,
)
from .query import (
    RAW_QUERY_FIELD,
    FilterGroup,
    UnhonourableFilterError,
    build_filter_query,
    parse_filter_group,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_FACET_SIZE = 20
MAX_FACET_SIZE = 100

# Generic link to the Tantivy query-language documentation. It points at the
# ``latest`` docs rather than a version-tagged URL so the user-facing response
# never reveals which Tantivy version backs the index.
QUERY_SYNTAX_URL = (
    "https://docs.rs/tantivy/latest/tantivy/query/struct.QueryParser.html"
)


class InvalidRequestError(SearchError):
    """Raised when the JSON request body is missing or malformed."""

    code = "invalid_request"


@dataclass(frozen=True)
class SearchRequest:
    """A validated search request with resolved pagination.

    Exactly one of ``query`` (a query string) and ``filter`` (a structured
    filter) is set. ``facets`` names the fields whose values are counted over
    every matching region, ``facet_size`` values each.
    """

    query: str | None
    filter: FilterGroup | None
    page: int
    per_page: int
    sort: Sort | None = None
    facets: tuple[str, ...] = ()
    facet_size: int = DEFAULT_FACET_SIZE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    def build_query(self, index: Index) -> Query:
        """The Tantivy query this request asks, built against ``index``."""
        if self.filter is not None:
            return build_filter_query(index, self.filter)
        return prepare_query(index, self.query or "")


def _positive_int(body: dict[str, Any], key: str, default: int) -> int:
    value = body.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidRequestError(f"'{key}' must be an integer")
    if value < 1:
        raise InvalidRequestError(f"'{key}' must be at least 1")
    return value


def _parse_sort(value: Any) -> Sort | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("field"), str):
        raise InvalidRequestError("'sort' must be an object with a 'field' string")
    order = value.get("order", "asc")
    if order not in ("asc", "desc"):
        raise InvalidRequestError('\'sort.order\' must be "asc" or "desc"')
    name = value["field"]
    field = SEARCH_FIELDS_BY_NAME.get(name)
    if field is None:
        raise UnknownFieldError(name, SEARCH_FIELDS_BY_NAME)
    if not field.sortable:
        raise InvalidRequestError(f"Hits cannot be sorted by field {name!r}")
    return Sort(field=name, descending=order == "desc")


def _parse_facets(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise InvalidRequestError("'facets' must be a list of field names")
    return tuple(dict.fromkeys(value))


def parse_search_request(body: Any) -> SearchRequest:
    """Validate a parsed JSON body into a :class:`SearchRequest`.

    The body carries either ``query`` (a query string) or ``filter`` (a
    structured filter, see :mod:`bgc_viewer.search.query`), never both; with
    neither, the query string is empty. Raises :class:`InvalidRequestError`
    when the body is not an object, a value has the wrong type, or the
    pagination values are not positive integers, and the filter parser's
    :class:`~bgc_viewer.search.query.InvalidFilterError` for a malformed
    filter. ``per_page`` and ``facet_size`` are clamped to their maximums.
    """
    if not isinstance(body, dict):
        raise InvalidRequestError("Request body must be a JSON object")

    query: str | None = None
    group: FilterGroup | None = None
    if body.get("filter") is not None:
        if "query" in body:
            raise InvalidRequestError("Send either 'query' or 'filter', not both")
        group = parse_filter_group(body["filter"])
    else:
        query = body.get("query", "")
        if not isinstance(query, str):
            raise InvalidRequestError("'query' must be a string")

    page = _positive_int(body, "page", 1)
    per_page = _positive_int(body, "per_page", DEFAULT_PAGE_SIZE)
    facet_size = _positive_int(body, "facet_size", DEFAULT_FACET_SIZE)

    return SearchRequest(
        query=query,
        filter=group,
        page=page,
        per_page=min(per_page, MAX_PAGE_SIZE),
        sort=_parse_sort(body.get("sort")),
        facets=_parse_facets(body.get("facets")),
        facet_size=min(facet_size, MAX_FACET_SIZE),
    )


@dataclass(frozen=True)
class ValuesRequest:
    """A validated request for suggested values of one field."""

    field: str
    contains: str
    size: int


def parse_values_request(args: Mapping[str, str]) -> ValuesRequest:
    """Validate the query-string arguments of a values request.

    ``field`` is required; ``q`` is the text a value must contain and ``size``
    the number of values, clamped to :data:`MAX_FACET_SIZE`.
    """
    field = args.get("field", "")
    if not field:
        raise InvalidRequestError("'field' is required")
    try:
        size = int(args.get("size", DEFAULT_FACET_SIZE))
    except ValueError:
        raise InvalidRequestError("'size' must be an integer") from None
    if size < 1:
        raise InvalidRequestError("'size' must be at least 1")
    return ValuesRequest(
        field=field, contains=args.get("q", ""), size=min(size, MAX_FACET_SIZE)
    )


@dataclass(frozen=True)
class ValuesResponse:
    """Suggested values of one field with their region counts."""

    field: str
    values: tuple[FacetBucket, ...]


@dataclass(frozen=True)
class SearchResponse:
    """The search response body: ranked hits, paging, and facet counts.

    Request parameters (query, page, per-page) are deliberately not echoed
    back; the client already knows them. ``has_more`` reports whether more
    matching units exist beyond this page at the selected level, so the client
    can show a "load more" affordance. ``total_regions`` counts every matching
    region, at the record level too. ``facets`` maps each requested facet
    field to its most common values over every matching region.
    """

    hits: tuple[SearchHit | RecordHit, ...]
    has_more: bool
    total_regions: int
    facets: dict[str, list[FacetBucket]]


def run_search(
    index: Index,
    request: SearchRequest,
    search: Callable[..., Results[Any]],
) -> SearchResponse:
    """Run ``request`` with a level's ``search`` function and count its facets."""
    query = request.build_query(index)
    results = search(
        index, query, offset=request.offset, limit=request.per_page, sort=request.sort
    )
    facets = facet_counts(index, query, request.facets, request.facet_size)
    return SearchResponse(
        hits=results.hits,
        has_more=results.has_more,
        total_regions=results.total_regions,
        facets=facets,
    )


@dataclass(frozen=True)
class SchemaResponse:
    """Level-independent search schema served to the shared help popup.

    Searchable fields and examples are identical at every level because the
    level changes only the hit shape and what happens when a hit is selected,
    so the payload carries no level. ``fields`` is projected from the registry
    and ``examples`` is read from SQLite; neither reads values from the index.
    ``raw_query_field`` is the pseudo-field of a filter condition that runs a
    query string.
    """

    fields: tuple[PublicFieldInfo, ...]
    examples: tuple[str, ...]
    query_syntax_url: str
    raw_query_field: str = RAW_QUERY_FIELD


def read_example_queries(db_path: Path) -> tuple[str, ...]:
    """Read generated example queries from a database in template order.

    Preprocessing inserts the rows in template order against an autoincrement
    primary key, so ordering by ``id`` reproduces the declared template order.
    A database without a ``search_examples`` table simply has no examples:
    the field half of the schema comes from the registry and stays valid, so
    this yields an empty tuple instead of failing the whole response.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT query FROM search_examples ORDER BY id").fetchall()
    except sqlite3.OperationalError:
        return ()
    finally:
        conn.close()
    return tuple(row[0] for row in rows)


def build_schema_response(db_path: Path) -> SchemaResponse:
    """Assemble the schema response from the registry and the example table."""
    return SchemaResponse(
        fields=PUBLIC_FIELDS,
        examples=read_example_queries(db_path),
        query_syntax_url=QUERY_SYNTAX_URL,
    )


# Structured search error code -> HTTP status.
_ERROR_STATUS: dict[str, int] = {
    "invalid_request": 400,
    "empty_query": 400,
    "unknown_field": 400,
    "invalid_query": 400,
    "invalid_filter": 400,
    "invalid_facet_field": 400,
    "no_database": 400,
    "missing_database": 404,
    "missing_index": 404,
    "incompatible_schema": 409,
    "corrupt_index": 500,
    "index_rebuilding": 409,
    "index_interrupted": 409,
}


def error_payload(
    code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the stable ``{"error": {...}}`` envelope, omitting empty details."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


def error_response(error: Exception) -> tuple[dict[str, Any], int]:
    """Map a raised exception onto the error envelope and an HTTP status code."""
    if isinstance(error, UnknownFieldError):
        return (
            error_payload(
                error.code,
                str(error),
                {"available_fields": list(error.available_fields)},
            ),
            400,
        )
    if isinstance(error, UnhonourableFilterError):
        return (
            error_payload(
                error.code,
                str(error),
                {"conditions": [c.to_dict() for c in error.conditions]},
            ),
            400,
        )
    if isinstance(error, SearchError):
        return error_payload(error.code, str(error)), _ERROR_STATUS.get(error.code, 500)
    return error_payload("search_failed", str(error)), 500
