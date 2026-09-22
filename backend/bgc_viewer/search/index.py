"""Build protocluster search indexes on top of the ``tantivy`` engine.

The Tantivy schema, the query-time default fields and boosts, and the fields
returned in hits are declared here as plain constants. The search schema
version is persisted as index metadata so a reader can validate
compatibility when it opens the index.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, cast

from tantivy import (
    Document,
    DocAddress,
    Index,
    Schema,
    SchemaBuilder,
    Searcher,
    TextAnalyzerBuilder,
    Tokenizer,
)
from tantivy import query_parser_error as parser_errors  # type: ignore[attr-defined]

from .document import PATH_TOKENIZER_PATTERN, SEARCH_SCHEMA_VERSION

# The custom ``path`` analyzer matches the runs *between* separators rather
# than the separators themselves, so ``nested/NC_003888.3.json`` tokenizes
# to ``nested``, ``NC_003888``, ``3``, ``json``. Splitting on ``/`` (the
# directory separator) and ``.`` (the extension separator) keeps each path
# component and the file stem searchable as its own term. The pattern lives in
# ``document.py`` so the example templates strip an extension the same way.
_PATH_TOKENIZER_NAME = "path"

# The Tantivy schema, declared in field order. Each entry is ``(name,
# tokenizer)``; ``"numeric"`` marks an integer field. Text tokenizers are:
# ``raw`` -- one whole-value token, no case folding, used for exact-match
# fields; ``default`` -- Unicode word segmentation with lowercase
# normalization and indexed positions, used for full-text fields; and the
# custom ``path`` tokenizer (see ``_register_custom_tokenizers``), which
# splits on ``/`` and ``.`` so a file path is searchable by directory, stem,
# or extension while the whole value still matches as a phrase.
_SCHEMA: tuple[tuple[str, str], ...] = (
    ("pfam", "raw"),
    ("pfam_name", "default"),
    ("organism", "default"),
    ("gene", "raw"),
    ("locus", "raw"),
    ("product", "raw"),
    ("category", "raw"),
    ("record", "raw"),
    ("region", "numeric"),
    ("protocluster", "numeric"),
    ("start", "numeric"),
    ("end", "numeric"),
    ("output_file", _PATH_TOKENIZER_NAME),
    ("input_file", _PATH_TOKENIZER_NAME),
)

# All indexed field names, in schema order.
_FIELD_NAMES: tuple[str, ...] = tuple(name for name, _ in _SCHEMA)

# Fields an unqualified term searches: every text field.
_DEFAULT_SEARCH_FIELDS: tuple[str, ...] = tuple(
    name for name, tokenizer in _SCHEMA if tokenizer != "numeric"
)

# Per-field relevance boosts applied to unqualified and fielded terms. Numeric
# fields are not boosted.
_FIELD_BOOSTS: dict[str, float] = {
    "pfam": 2.0,
    "pfam_name": 1.0,
    "organism": 1.0,
    "gene": 2.0,
    "locus": 2.0,
    "product": 2.0,
    "category": 2.0,
    "record": 2.0,
    "output_file": 2.0,
    "input_file": 2.0,
}

# Fields read back into ordinary hits, in display order. Every other field is
# still stored in the index for example collection and diagnostics.
_RETURNED_FIELDS: tuple[tuple[str, str], ...] = (
    ("organism", "text"),
    ("product", "text"),
    ("category", "text"),
    ("record", "text"),
    ("region", "numeric"),
    ("protocluster", "numeric"),
    ("start", "numeric"),
    ("end", "numeric"),
    ("output_file", "text"),
    ("input_file", "text"),
)


def _register_custom_tokenizers(index: Index) -> None:
    """Register the custom analyzers the schema references by name.

    Tantivy records only the tokenizer *name* in the schema, so every Index
    that reads or writes a ``path`` field -- whether freshly built or
    reopened from disk -- must register the analyzer under that name before
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
    index_path: str | PathLike[str] | None = None,
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
    index_dir = None if index_path is None else Path(index_path)
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


@dataclass(frozen=True)
class SearchHit:
    """One ranked protocluster hit with its stored summary values."""

    score: float
    fields: dict[str, Any]


@dataclass(frozen=True)
class SearchResults:
    """A page of search hits plus the total number of matching documents."""

    hits: tuple[SearchHit, ...]
    total: int


@dataclass(frozen=True)
class RegionHit:
    """One ranked region, scored by its best-matching protocluster."""

    score: float
    record: str
    region: int
    output_file: str
    input_file: str | None


@dataclass(frozen=True)
class RegionResults:
    """A page of unique regions plus the total number of matching regions."""

    hits: tuple[RegionHit, ...]
    total: int


@dataclass(frozen=True)
class RecordHit:
    """One ranked record, scored by its best-matching protocluster."""

    score: float
    record: str
    output_file: str
    input_file: str | None


@dataclass(frozen=True)
class RecordResults:
    """A page of unique records plus the total number of matching records."""

    hits: tuple[RecordHit, ...]
    total: int


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


def open_index(index_path: str | PathLike[str]) -> Index:
    """Open a previously built index for querying.

    The expected schema is rebuilt from the constants in this module, then the
    stored index is checked for schema and search-schema-version compatibility
    before it is returned.
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
    _validate_pagination(offset, limit)

    parsed = _parse_query(index, query)

    searcher: Any = index.searcher()
    result = searcher.search(parsed, limit=limit, offset=offset, count=True)
    hits = tuple(
        SearchHit(score=score, fields=_stored_fields(searcher, address))
        for score, address in result.hits
    )
    return SearchResults(hits=hits, total=result.count)


# Number of raw Tantivy hits pulled per round when collapsing matches. Keeps the
# full hit list (which can reach millions) from ever being materialized at once.
_FETCH_BATCH_SIZE = 1000


def _unique_matching_protoclusters(
    index: Index, parsed: Any, key_fields: tuple[str, ...]
) -> list[tuple[float, dict[str, Any]]]:
    """Return ``(score, stored_fields)`` for each distinct ``key_fields`` group.

    Matching protoclusters are fetched from Tantivy in batches of
    :data:`_FETCH_BATCH_SIZE` so the full hit list is never held in memory at
    once. Documents arrive in Tantivy relevance order, so the first occurrence of
    a grouping key carries that group's best score.
    """
    searcher: Searcher = index.searcher()
    total = searcher.search(parsed, limit=1, count=True).count
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
    return unique


def search_region(
    index: Index,
    query: str,
    offset: int = 0,
    limit: int = 10,
) -> RegionResults:
    """Run ``query`` and return a page of unique regions.

    A region is identified by its output file, record, and region number. Every
    protocluster matching ``query`` contributes to its parent region, but each
    region is reported once, scored by its highest-scoring matching
    protocluster, and ordered by that score. The total is the number of distinct
    matching regions, and ``offset``/``limit`` paginate that distinct set.
    """
    if not query.strip():
        raise EmptyQueryError()
    _validate_pagination(offset, limit)

    parsed = _parse_query(index, query)
    unique = _unique_matching_protoclusters(
        index, parsed, ("output_file", "record", "region")
    )
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
    return RegionResults(hits=hits, total=len(unique))


def search_record(
    index: Index,
    query: str,
    offset: int = 0,
    limit: int = 10,
) -> RecordResults:
    """Run ``query`` and return a page of unique records.

    A record is identified by its output file and record id. Every protocluster
    matching ``query`` contributes to its parent record, but each record is
    reported once, scored by its highest-scoring matching protocluster, and
    ordered by that score. The total is the number of distinct matching
    records, and ``offset``/``limit`` paginate that distinct set.
    """
    if not query.strip():
        raise EmptyQueryError()
    _validate_pagination(offset, limit)

    parsed = _parse_query(index, query)
    unique = _unique_matching_protoclusters(index, parsed, ("output_file", "record"))
    hits = tuple(
        RecordHit(
            score=score,
            record=fields.get("record", ""),
            output_file=fields.get("output_file", ""),
            input_file=fields.get("input_file"),
        )
        for score, fields in unique[offset : offset + limit]
    )
    return RecordResults(hits=hits, total=len(unique))
