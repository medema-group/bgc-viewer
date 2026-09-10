"""Build protocluster search indexes on top of the ``tantivy`` engine.

The Tantivy schema is derived entirely from the field registry in
:mod:`bgc_viewer.search.document`; biological fields are never hard-coded
here. Only the search schema version is persisted as index metadata so a
reader can validate compatibility when it opens the index.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, cast

from tantivy import Document, Index, Schema, SchemaBuilder
from tantivy import query_parser_error as parser_errors  # type: ignore[attr-defined]

from .document import (
    ProtoclusterSearchDocument,
    SEARCH_FIELD_REGISTRY,
    SEARCH_SCHEMA_VERSION,
    SearchFieldDefinition,
)

# Registry analyzer name -> Tantivy built-in analyzer name.
# ``exact`` uses the ``raw`` analyzer: one whole-value token with no case
# normalization. ``full_text`` uses Tantivy's ``default`` analyzer: Unicode
# word segmentation with lowercase normalization and indexed positions.
_ANALYZERS: dict[str, str] = {"exact": "raw", "full_text": "default"}

_SCHEMA_VERSION_KEY = "search_schema_version"
_META_FILE = "meta.json"


def _add_field(builder: SchemaBuilder, definition: SearchFieldDefinition) -> None:
    if definition.value_type == "numeric":
        builder.add_integer_field(
            definition.name,
            stored=definition.stored,
            indexed=True,
            fast=True,
        )
        return

    if definition.analyzer is None:
        raise ValueError(f"Field {definition.name} has no analyzer")
    tokenizer = _ANALYZERS.get(definition.analyzer)
    if tokenizer is None:
        raise ValueError(
            f"Field {definition.name} requests unregistered analyzer "
            f"{definition.analyzer!r}"
        )

    builder.add_text_field(
        definition.name,
        stored=definition.stored,
        tokenizer_name=tokenizer,
        index_option="position" if definition.analyzer == "full_text" else "freq",
    )


def build_schema() -> Schema:
    """Build the Tantivy schema from the current search-field registry."""
    builder = SchemaBuilder()
    for definition in SEARCH_FIELD_REGISTRY:
        _add_field(builder, definition)
    return builder.build()


def _to_tantivy_document(document: ProtoclusterSearchDocument) -> Document:
    tantivy_document = Document()
    for definition in SEARCH_FIELD_REGISTRY:
        value = document.field_value(definition)
        if definition.value_type == "numeric":
            tantivy_document.add_integer(definition.name, cast(int, value))
        elif definition.cardinality == "multi":
            for item in cast("tuple[str, ...]", value):
                tantivy_document.add_text(definition.name, item)
        elif value != "":
            tantivy_document.add_text(definition.name, cast(str, value))
    return tantivy_document


def _persist_schema_version(index_dir: Path, version: int) -> None:
    meta_path = index_dir / _META_FILE
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["payload"] = json.dumps({_SCHEMA_VERSION_KEY: version})
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


def build_index(
    documents: Iterable[ProtoclusterSearchDocument],
    index_path: str | PathLike[str] | None = None,
) -> Index:
    """Stream ``documents`` into a new Tantivy index and return it.

    When ``index_path`` is given the index is created on disk at that final
    path and the search schema version is persisted as index metadata after the
    final commit so a reader can validate compatibility when it reopens the
    index. When ``index_path`` is omitted an in-RAM index is built instead and
    no metadata is persisted.

    Documents are added one at a time in the order produced by the extraction
    iterator (selected-file, record, then protocluster order) so Python never
    retains a converted copy of the corpus and equal-score results resolve
    deterministically. A single writer thread is used to keep document order
    stable.
    """
    index_dir = None if index_path is None else Path(index_path)
    if index_dir is not None:
        index_dir.mkdir(parents=True, exist_ok=True)
        index = Index(build_schema(), path=str(index_dir))
    else:
        index = Index(build_schema())

    writer = index.writer(num_threads=1)
    try:
        for document in documents:
            writer.add_document(_to_tantivy_document(document))
        writer.commit()
        writer.wait_merging_threads()
    finally:
        del writer

    if index_dir is not None:
        _persist_schema_version(index_dir, SEARCH_SCHEMA_VERSION)

    index.reload()
    return index


class SearchError(Exception):
    """Base class for structured search failures."""

    code = "search_error"


class EmptyQueryError(SearchError):
    """Raised when a search is attempted with an empty query."""

    code = "empty_query"

    def __init__(self) -> None:
        super().__init__("Query must not be empty")


class UnknownFieldError(SearchError):
    """Raised when a query references a field outside the registry."""

    code = "unknown_field"

    def __init__(self, field: str, available_fields: Iterable[str]) -> None:
        super().__init__(f"Unknown field: {field}")
        self.field = field
        self.available_fields = sorted(set(available_fields))


class QuerySyntaxError(SearchError):
    """Raised when the query parser rejects the query."""

    code = "invalid_query"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class IndexNotFoundError(SearchError):
    """Raised when no index is present at the requested path."""

    code = "missing_index"


class IndexIncompatibleError(SearchError):
    """Raised when an existing index is incompatible with the current schema."""

    code = "incompatible_schema"


class IndexCorruptError(SearchError):
    """Raised when an existing index cannot be read."""

    code = "corrupt_index"


@dataclass(frozen=True)
class SearchHit:
    """One ranked protocluster hit with its stored summary values."""

    score: float
    fields: dict[str, Any]


@dataclass(frozen=True)
class SearchResults:
    """A page of search hits plus the total number of matching documents."""

    query: str
    hits: tuple[SearchHit, ...]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class SearchIndex:
    """An open Tantivy index plus the query-time configuration it uses.

    The public field names, default search fields, and boosts are all derived
    from the registry so callers never touch internal schema details.
    """

    index: Index
    fields: tuple[str, ...]
    default_field_names: tuple[str, ...]
    field_boosts: dict[str, float]

    def searcher(self):
        return self.index.searcher()


def _query_configuration() -> tuple[tuple[str, ...], tuple[str, ...], dict[str, float]]:
    default_fields: list[str] = []
    boosts: dict[str, float] = {}
    names: list[str] = []
    for definition in SEARCH_FIELD_REGISTRY:
        names.append(definition.name)
        if definition.value_type != "numeric":
            boosts[definition.name] = definition.boost
        if definition.default_search:
            default_fields.append(definition.name)
    return tuple(names), tuple(default_fields), boosts


def _wrap(index: Index) -> SearchIndex:
    names, default_fields, boosts = _query_configuration()
    return SearchIndex(index, names, default_fields, boosts)


def _index_present(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return Index.exists(str(path))
    except (OSError, ValueError):
        return False


def _read_schema_version(path: Path) -> int | None:
    meta = json.loads((path / _META_FILE).read_text(encoding="utf-8"))
    payload = meta.get("payload")
    if not payload:
        return None
    return json.loads(payload).get(_SCHEMA_VERSION_KEY)


def open_index(index_path: str | PathLike[str]) -> SearchIndex:
    """Open a previously built index for querying.

    The expected schema is rebuilt from the current registry, then the stored
    index is checked for schema and search-schema-version compatibility before
    it is returned together with the query-time fields, default search fields,
    and boosts derived from the registry.
    """
    path = Path(index_path)
    if not _index_present(path):
        raise IndexNotFoundError(f"No search index found at {path}")

    try:
        index = Index(build_schema(), path=str(path), reuse=True)
    except ValueError as error:
        message = str(error).lower()
        if "corrupt" in message or "deserial" in message:
            raise IndexCorruptError(f"Search index at {path} is corrupt") from error
        raise IndexIncompatibleError(
            f"Search index at {path} is incompatible with the current schema"
        ) from error
    except OSError as error:
        raise IndexCorruptError(f"Search index at {path} is corrupt") from error

    stored_version = _read_schema_version(path)
    if stored_version != SEARCH_SCHEMA_VERSION:
        raise IndexIncompatibleError(
            f"Search index at {path} has schema version {stored_version!r}; "
            f"expected {SEARCH_SCHEMA_VERSION}"
        )
    return _wrap(index)


def _stored_fields(searcher, address: Any) -> dict[str, Any]:
    raw = searcher.doc(address).to_dict()
    summary: dict[str, Any] = {}
    for definition in SEARCH_FIELD_REGISTRY:
        if not definition.stored or definition.name not in raw:
            continue
        value = raw[definition.name]
        if definition.value_type == "numeric":
            summary[definition.name] = value[0] if value else None
        elif definition.cardinality == "single":
            summary[definition.name] = value[0] if value else ""
        else:
            summary[definition.name] = tuple(value)
    return summary


def _parse_query(index: SearchIndex, query: str):
    """Parse ``query``, mapping parser errors onto structured search errors."""
    parsed, errors = index.index.parse_query_lenient(
        query,
        default_field_names=list(index.default_field_names),
        field_boosts=index.field_boosts,
        allow_regexes=False,
    )
    for error in errors:
        if isinstance(error, parser_errors.FieldDoesNotExistError):
            raise UnknownFieldError(error.field, index.fields)
    if errors:
        raise QuerySyntaxError(str(errors[0]))
    return parsed


def search(
    index: SearchIndex,
    query: str,
    offset: int = 0,
    limit: int = 10,
) -> SearchResults:
    """Run ``query`` against an open ``index`` and return a page of hits.

    An empty query raises :class:`EmptyQueryError`. Unknown fields raise
    :class:`UnknownFieldError` naming the field and the available fields; the
    character position is not reported. Any other parser failure is surfaced as
    :class:`QuerySyntaxError` carrying the parser message. Results use Tantivy
    relevance ordering, include the total hit count, and carry the stored
    identity and display fields for every hit.
    """
    if not query.strip():
        raise EmptyQueryError()
    if offset < 0:
        raise ValueError("offset must not be negative")
    if limit < 1:
        raise ValueError("limit must be at least 1")

    parsed = _parse_query(index, query)

    searcher = index.searcher()
    result = searcher.search(parsed, limit=limit, offset=offset, count=True)
    hits = tuple(
        SearchHit(score=score, fields=_stored_fields(searcher, address))
        for score, address in result.hits
    )
    return SearchResults(
        query=query,
        hits=hits,
        total=result.count,
        offset=offset,
        limit=limit,
    )
