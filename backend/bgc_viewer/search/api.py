"""Request parsing and response dataclasses for the protocluster search endpoints.

This module owns the framework-agnostic pieces of the search HTTP layer:
parsing and validating the JSON request body into a :class:`SearchRequest`,
building the minimal :class:`SearchResponse` from the core
:mod:`bgc_viewer.search.index` result types, and mapping structured search
errors onto HTTP status codes. The Flask routes stay thin: each resolves its
index, calls its own ``search_*`` function, wraps the result in a
:class:`SearchResponse`, and returns it through ``jsonify``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    """The minimal search response body: ranked hits plus the total match count.

    Request parameters (query, page, per-page) are deliberately not echoed
    back; the client already knows them. ``total`` is the number of distinct
    matching units at the selected level, so the client can derive page
    counts itself from its own ``per_page``.
    """

    hits: tuple[SearchHit | RegionHit | RecordHit, ...]
    total: int

    @classmethod
    def from_results(
        cls, results: SearchResults | RegionResults | RecordResults
    ) -> "SearchResponse":
        return cls(hits=results.hits, total=results.total)


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
