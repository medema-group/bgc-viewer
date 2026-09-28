"""Build protocluster search indexes on top of the ``tantivy`` engine.

The Tantivy schema, the query-time default fields and boosts, and the fields
returned in hits are projected from the single field registry in
``document.py``. The search schema version is persisted as index metadata so a
reader can validate compatibility when it opens the index.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar, cast

from tantivy import (
    DocAddress,
    Document,
    Index,
    Schema,
    SchemaBuilder,
    Searcher,
    TextAnalyzerBuilder,
    Tokenizer,
)
from tantivy import query_parser_error as parser_errors  # type: ignore[attr-defined]

from .document import PATH_TOKENIZER_PATTERN, SEARCH_FIELDS, SEARCH_SCHEMA_VERSION

# The custom ``path`` tokenizer matches the runs *between* separators rather
# than the separators themselves, so ``nested/NC_003888.3.json`` tokenizes
# to ``nested``, ``NC_003888``, ``3``, ``json``. Splitting on ``/`` (the
# directory separator) and ``.`` (the extension separator) keeps each path
# component and the file stem searchable as its own term. The pattern lives in
# ``document.py`` so the example templates strip an extension the same way.
_PATH_TOKENIZER_NAME = "path"

# The Tantivy schema, query-time config, and hit projection are all projected
# from the single field registry in ``document.py``. A registry entry's
# tokenizer is ``raw`` -- one whole-value token, no case folding, for exact
# matches; ``default`` -- Unicode word segmentation with lowercase
# normalization and indexed positions, for full text; ``path`` -- the custom
# tokenizer (see ``_register_custom_tokenizers``) that splits on ``/`` and
# ``.``; or ``numeric`` -- a stored integer.
_SCHEMA: tuple[tuple[str, str], ...] = tuple(
    (field.name, field.tokenizer) for field in SEARCH_FIELDS
)

# All indexed field names, in schema order.
_FIELD_NAMES: tuple[str, ...] = tuple(field.name for field in SEARCH_FIELDS)

# Fields a bare term searches: every non-numeric field.
_DEFAULT_SEARCH_FIELDS: tuple[str, ...] = tuple(
    field.name for field in SEARCH_FIELDS if field.default_search
)

# Per-field relevance boosts applied to bare and fielded terms. Numeric fields
# declare no boost.
_FIELD_BOOSTS: dict[str, float] = {
    field.name: field.boost for field in SEARCH_FIELDS if field.boost is not None
}

# Fields read back into ordinary hits, in registry order. Every other field is
# still stored in the index for example collection and diagnostics.
_RETURNED_FIELDS: tuple[tuple[str, str], ...] = tuple(
    (field.name, field.returned_kind) for field in SEARCH_FIELDS if field.in_hits
)


def _register_custom_tokenizers(index: Index) -> None:
    """Register the custom tokenizers the schema references by name.

    Tantivy records only the tokenizer *name* in the schema, so every Index
    that reads or writes a ``path`` field -- whether freshly built or
    reopened from disk -- must register the tokenizer under that name before
    the field is used, or query parsing fails with ``tokenizer 'path' is
    unknown``.
    """
    index.register_tokenizer(
        _PATH_TOKENIZER_NAME,
        TextAnalyzerBuilder(Tokenizer.regex(PATH_TOKENIZER_PATTERN)).build(),
    )


_VERSION_FILE = "version.txt"


def build_schema() -> Schema:
    """Build the Tantivy schema from the field declarations above.

    Every field is stored so its value can be read back for example collection
    and diagnostics; ``_RETURNED_FIELDS`` selects what comes back in ordinary
    hits. Text fields use ``freq`` indexing when their tokenizer is ``raw``
    (a single whole-value token) and ``position`` indexing otherwise, so
    full-text phrases and path phrases/prefixes that span tokens work.
    """
    builder = SchemaBuilder()
    for name, tokenizer in _SCHEMA:
        if tokenizer == "numeric":
            builder.add_integer_field(name, stored=True, indexed=True, fast=True)
        else:
            builder.add_text_field(
                name,
                stored=True,
                tokenizer_name=tokenizer,
                index_option="freq" if tokenizer == "raw" else "position",
            )
    return builder.build()


def _persist_schema_version(index_dir: Path, version: int) -> None:
    (index_dir / _VERSION_FILE).write_text(str(version), encoding="utf-8")


def build_index(
    documents: Iterable[Document],
    index_path: Path | None = None,
) -> Index:
    """Stream Tantivy ``documents`` into a new index and return it.

    When ``index_path`` is given the index is created on disk at that final
    path and the search schema version is persisted as index metadata after the
    final commit so a reader can validate compatibility when it reopens the
    index. When ``index_path`` is omitted an in-RAM index is built instead and
    no metadata is persisted.

    Documents are added one at a time in the order produced by the extraction
    iterator (selected-file, record, then protocluster order) so Python never
    retains the whole corpus and equal-score results resolve deterministically.
    A single writer thread is used to keep document order stable.
    """
    index_dir = index_path
    if index_dir is not None:
        index_dir.mkdir(parents=True, exist_ok=True)
        index = Index(build_schema(), path=str(index_dir))
    else:
        index = Index(build_schema())
    _register_custom_tokenizers(index)

    writer = index.writer(num_threads=1)
    try:
        for document in documents:
            writer.add_document(document)
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
    """Raised when a query references a field outside the schema."""

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


HitT = TypeVar("HitT")


@dataclass(frozen=True)
class Results(Generic[HitT]):
    """A page of hits plus whether more matching units remain."""

    hits: tuple[HitT, ...]
    has_more: bool


@dataclass(frozen=True)
class SearchHit:
    """One ranked protocluster hit with its stored summary values."""

    score: float
    fields: dict[str, Any]


@dataclass(frozen=True)
class RegionHit:
    """One ranked region, scored by its best-matching protocluster."""

    score: float
    record: str
    region: int
    output_file: str
    input_file: str | None


@dataclass(frozen=True)
class RecordHit:
    """One ranked record, scored by its best-matching protocluster."""

    score: float
    record: str
    output_file: str
    input_file: str | None


def _index_present(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return Index.exists(str(path))
    except (OSError, ValueError):
        return False


def _read_schema_version(path: Path) -> int | None:
    version_path = path / _VERSION_FILE
    if not version_path.exists():
        return None
    return int(version_path.read_text(encoding="utf-8"))


def open_index(index_path: Path) -> Index:
    """Open a previously built index for querying.

    The expected schema is rebuilt from the constants in this module, then the
    stored index is checked for schema and search-schema-version compatibility
    before it is returned.
    """
    path = index_path
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
    _register_custom_tokenizers(index)

    stored_version = _read_schema_version(path)
    if stored_version != SEARCH_SCHEMA_VERSION:
        raise IndexIncompatibleError(
            f"Search index at {path} has schema version {stored_version!r}; "
            f"expected {SEARCH_SCHEMA_VERSION}"
        )
    return index


def _stored_fields(searcher, address: Any) -> dict[str, Any]:
    raw = searcher.doc(address).to_dict()
    summary: dict[str, Any] = {}
    for name, kind in _RETURNED_FIELDS:
        if name not in raw:
            continue
        value = raw[name]
        if kind == "numeric":
            summary[name] = value[0] if value else None
        else:
            summary[name] = value[0] if value else ""
    return summary


def collect_first_values(index: Index) -> dict[str, str]:
    """Read the first non-empty stored value for each text field from ``index``.

    Documents are visited in Tantivy document-address order. The index is built
    by a single writer thread with a single commit, so it is a single segment
    and this order is the deterministic selected-file, record, protocluster
    insertion order the plan calls for. The scan stops as soon as every text
    field has a value or the corpus ends, and a multi-valued field contributes
    its first stored value. Numeric fields are skipped because no example
    template consumes them.
    """
    text_fields = _DEFAULT_SEARCH_FIELDS
    values: dict[str, str] = {}
    searcher = index.searcher()
    for segment_ord in range(searcher.num_segments):
        if len(values) == len(text_fields):
            break
        doc_id = 0
        while True:
            try:
                raw = searcher.doc(DocAddress(segment_ord, doc_id)).to_dict()
            except ValueError:
                break
            for name in text_fields:
                if name in values:
                    continue
                items = raw.get(name)
                if items and items[0]:
                    values[name] = items[0]
            if len(values) == len(text_fields):
                break
            doc_id += 1
    return values


def _parse_query(index: Index, query: str):
    """Parse ``query``, mapping parser errors onto structured search errors."""
    parsed, errors = index.parse_query_lenient(
        query,
        default_field_names=list(_DEFAULT_SEARCH_FIELDS),
        field_boosts=dict(_FIELD_BOOSTS),
        allow_regexes=False,
    )
    for error in errors:
        if isinstance(error, parser_errors.FieldDoesNotExistError):
            raise UnknownFieldError(error.field, _FIELD_NAMES)
    if errors:
        raise QuerySyntaxError(str(errors[0]))
    return parsed


def _validate_pagination(offset: int, limit: int) -> None:
    if offset < 0:
        raise ValueError("offset must not be negative")
    if limit < 1:
        raise ValueError("limit must be at least 1")


def search_protoclusters(
    index: Index,
    query: str,
    offset: int = 0,
    limit: int = 10,
) -> Results[SearchHit]:
    """Run ``query`` against an open ``index`` and return a page of hits.

    An empty query raises :class:`EmptyQueryError`. Unknown fields raise
    :class:`UnknownFieldError` naming the field and the available fields; the
    character position is not reported. Any other parser failure is surfaced as
    :class:`QuerySyntaxError` carrying the parser message. Results use Tantivy
    relevance ordering and carry the stored identity and display fields for
    every hit. One extra hit beyond ``limit`` is fetched so ``has_more`` reports
    whether further pages exist without counting the whole result set.
    """
    if not query.strip():
        raise EmptyQueryError()
    _validate_pagination(offset, limit)

    parsed = _parse_query(index, query)

    searcher: Any = index.searcher()
    result = searcher.search(parsed, limit=limit + 1, offset=offset, count=False)
    fetched = list(result.hits)
    has_more = len(fetched) > limit
    hits = tuple(
        SearchHit(score=score, fields=_stored_fields(searcher, address))
        for score, address in fetched[:limit]
    )
    return Results(hits=hits, has_more=has_more)


# Number of raw Tantivy hits pulled per round when collapsing matches. Keeps the
# full hit list (which can reach millions) from ever being materialized at once.
_FETCH_BATCH_SIZE = 1000


def _unique_matching_protoclusters(
    index: Index, parsed: Any, key_fields: tuple[str, ...], max_needed: int
) -> list[tuple[float, dict[str, Any]]]:
    """Return up to ``max_needed`` ``(score, stored_fields)`` distinct groups.

    Matching protoclusters are fetched from Tantivy in batches of
    :data:`_FETCH_BATCH_SIZE` and collapsed on ``key_fields`` so the full hit
    list (which can reach millions) is never held in memory at once. Documents
    arrive in Tantivy relevance order, so the first occurrence of a grouping key
    carries that group's best score. Collapsing stops as soon as ``max_needed``
    distinct groups have been collected, leaving the caller to tell from the
    returned length whether more groups remain.
    """
    searcher: Searcher = index.searcher()
    # Tantivy exposes count at runtime, but its SearchResult stub omits it.
    total = searcher.search(parsed, limit=1, count=True).count  # type: ignore[attr-defined]
    seen: set[tuple[Any, ...]] = set()
    unique: list[tuple[float, dict[str, Any]]] = []
    for offset in range(0, total, _FETCH_BATCH_SIZE):
        result = searcher.search(
            parsed, limit=_FETCH_BATCH_SIZE, offset=offset, count=False
        )
        if not result.hits:
            break
        for score, address in result.hits:
            fields = _stored_fields(searcher, address)
            key = tuple(fields.get(name) for name in key_fields)
            if key in seen:
                continue
            seen.add(key)
            unique.append((score, fields))
            if len(unique) >= max_needed:
                return unique
    return unique


def search_region(
    index: Index,
    query: str,
    offset: int = 0,
    limit: int = 10,
) -> Results[RegionHit]:
    """Run ``query`` and return a page of unique regions.

    A region is identified by its output file, record, and region number. Every
    protocluster matching ``query`` contributes to its parent region, but each
    region is reported once, scored by its highest-scoring matching
    protocluster, and ordered by that score. ``offset``/``limit`` paginate that
    distinct set; one extra group is collapsed so ``has_more`` reports whether
    further regions remain.
    """
    if not query.strip():
        raise EmptyQueryError()
    _validate_pagination(offset, limit)

    parsed = _parse_query(index, query)
    unique = _unique_matching_protoclusters(
        index, parsed, ("output_file", "record", "region"), offset + limit + 1
    )
    has_more = len(unique) > offset + limit
    hits = tuple(
        RegionHit(
            score=score,
            record=fields.get("record", ""),
            region=cast(int, fields.get("region")),
            output_file=fields.get("output_file", ""),
            input_file=fields.get("input_file"),
        )
        for score, fields in unique[offset : offset + limit]
    )
    return Results(hits=hits, has_more=has_more)


def search_record(
    index: Index,
    query: str,
    offset: int = 0,
    limit: int = 10,
) -> Results[RecordHit]:
    """Run ``query`` and return a page of unique records.

    A record is identified by its output file and record id. Every protocluster
    matching ``query`` contributes to its parent record, but each record is
    reported once, scored by its highest-scoring matching protocluster, and
    ordered by that score. ``offset``/``limit`` paginate that distinct set; one
    extra group is collapsed so ``has_more`` reports whether further records
    remain.
    """
    if not query.strip():
        raise EmptyQueryError()
    _validate_pagination(offset, limit)

    parsed = _parse_query(index, query)
    unique = _unique_matching_protoclusters(
        index, parsed, ("output_file", "record"), offset + limit + 1
    )
    has_more = len(unique) > offset + limit
    hits = tuple(
        RecordHit(
            score=score,
            record=fields.get("record", ""),
            output_file=fields.get("output_file", ""),
            input_file=fields.get("input_file"),
        )
        for score, fields in unique[offset : offset + limit]
    )
    return Results(hits=hits, has_more=has_more)
