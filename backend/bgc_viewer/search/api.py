"""Request parsing and response dataclasses for the protocluster search endpoints.

This module owns the framework-agnostic pieces of the search HTTP layer:
parsing and validating the JSON request body into a :class:`SearchRequest`,
building the minimal :class:`SearchResponse` from the core
:mod:`bgc_viewer.search.index` result types, assembling the level-independent
:class:`SchemaResponse` from the field registry and the SQLite example table,
and mapping structured search errors onto HTTP status codes. The Flask routes
stay thin: each resolves its index, calls its own ``search_*`` function, wraps
the result in a response dataclass, and returns it through ``jsonify``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from os import PathLike
from typing import Any

from .document import PUBLIC_FIELDS, PublicFieldInfo
from .index import (
    RecordHit,
    RecordResults,
    RegionHit,
    RegionResults,
    SearchError,
    SearchHit,
    SearchResults,
    UnknownFieldError,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

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
    """A validated search request with resolved pagination."""

    query: str
    page: int
    per_page: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


def parse_search_request(body: Any) -> SearchRequest:
    """Validate a parsed JSON body into a :class:`SearchRequest`.

    Raises :class:`InvalidRequestError` when the body is not an object, the
    query is not a string, or the pagination values are not positive integers.
    ``per_page`` is clamped to :data:`MAX_PAGE_SIZE`.
    """
    if not isinstance(body, dict):
        raise InvalidRequestError("Request body must be a JSON object")

    query = body.get("query", "")
    if not isinstance(query, str):
        raise InvalidRequestError("'query' must be a string")

    try:
        page = int(body.get("page", 1))
        per_page = int(body.get("per_page", DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        raise InvalidRequestError("'page' and 'per_page' must be integers") from None

    if page < 1:
        raise InvalidRequestError("'page' must be at least 1")
    if per_page < 1:
        raise InvalidRequestError("'per_page' must be at least 1")

    return SearchRequest(query=query, page=page, per_page=min(per_page, MAX_PAGE_SIZE))


@dataclass(frozen=True)
class SearchResponse:
    """The minimal search response body: ranked hits plus a ``has_more`` flag.

    Request parameters (query, page, per-page) are deliberately not echoed
    back; the client already knows them. ``has_more`` reports whether more
    matching units exist beyond this page at the selected level, so the client
    can show a "load more" affordance without a total count.
    """

    hits: tuple[SearchHit | RegionHit | RecordHit, ...]
    has_more: bool

    @classmethod
    def from_results(
        cls, results: SearchResults | RegionResults | RecordResults
    ) -> "SearchResponse":
        return cls(hits=results.hits, has_more=results.has_more)


@dataclass(frozen=True)
class SchemaResponse:
    """Level-independent search schema served to the shared help popup.

    Searchable fields and examples are identical at every level because the
    level changes only the hit shape and what happens when a hit is selected,
    so the payload carries no level. ``fields`` is projected from the registry
    and ``examples`` is read from SQLite; neither reads values from the index.
    """

    fields: tuple[PublicFieldInfo, ...]
    examples: tuple[str, ...]
    query_syntax_url: str


def read_example_queries(db_path: str | PathLike[str]) -> tuple[str, ...]:
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


def build_schema_response(db_path: str | PathLike[str]) -> SchemaResponse:
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
    if isinstance(error, SearchError):
        return error_payload(error.code, str(error)), _ERROR_STATUS.get(error.code, 500)
    return error_payload("search_failed", str(error)), 500
