"""Build region search indexes on top of the ``tantivy`` engine.

The Tantivy schema, the query-time default fields and boosts, and the fields
returned in hits are projected from the single field registry in
``document.py``. The search schema version is persisted as index metadata so a
reader can validate compatibility when it opens the index.
"""

from __future__ import annotations

import re

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

from tantivy import (
    DocAddress,
    Document,
    Index,
    Order,
    Query,
    Schema,
    SchemaBuilder,
    Searcher,
    TextAnalyzerBuilder,
    Tokenizer,
)
from tantivy import query_parser_error as parser_errors  # type: ignore[attr-defined]

from .document import (
    PATH_TOKENIZER_PATTERN,
    SEARCH_FIELDS,
    SEARCH_FIELDS_BY_NAME,
    SEARCH_SCHEMA_VERSION,
    SearchField,
)

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
# ``.``; or ``integer``, ``float``, or ``boolean`` for a stored value of that
# type.
# All indexed field names, in schema order.
_FIELD_NAMES: tuple[str, ...] = tuple(field.name for field in SEARCH_FIELDS)

# Fields a bare term searches: every text field.
_DEFAULT_SEARCH_FIELDS: tuple[str, ...] = tuple(
    field.name for field in SEARCH_FIELDS if field.default_search
)

# Per-field relevance boosts applied to bare and fielded terms. Numeric and
# boolean fields declare no boost.
_FIELD_BOOSTS: dict[str, float] = {
    field.name: field.boost for field in SEARCH_FIELDS if field.boost is not None
}

# Fields read back into ordinary hits, in registry order. Every other stored
# field is still kept in the index for example collection and diagnostics.
_RETURNED_FIELDS: tuple[SearchField, ...] = tuple(
    field for field in SEARCH_FIELDS if field.in_hits
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
    """Build the Tantivy schema from the field registry.

    Every field but the catch-all text field is stored so its value can be
    read back for example collection and diagnostics; ``_RETURNED_FIELDS``
    selects what comes back in ordinary hits. Text fields use ``freq``
    indexing when their tokenizer is ``raw`` (a single whole-value token) and
    ``position`` indexing otherwise, so full-text phrases and path
    phrases/prefixes that span tokens work. Exact text fields and all number
    and boolean fields are fast fields, so they can be sorted and aggregated.
    """
    builder = SchemaBuilder()
    for field in SEARCH_FIELDS:
        name, tokenizer, stored = field.name, field.tokenizer, field.stored
        if tokenizer == "integer":
            builder.add_integer_field(name, stored=stored, indexed=True, fast=True)
        elif tokenizer == "float":
            builder.add_float_field(name, stored=stored, indexed=True, fast=True)
        elif tokenizer == "boolean":
            builder.add_boolean_field(name, stored=stored, indexed=True, fast=True)
        else:
            builder.add_text_field(
                name,
                stored=stored,
                fast=tokenizer == "raw",
                tokenizer_name=tokenizer,
                index_option="freq" if tokenizer == "raw" else "position",
            )
    return builder.build()


def _persist_schema_version(index_dir: Path, version: int) -> None:
    (index_dir / _VERSION_FILE).write_text(str(version), encoding="utf-8")


def build_index(
    documents: Iterable[Document],
    index_path: Path | None = None,
    *,
    progress_callback: Callable[[str, int], None] | None = None,
) -> Index:
    """Stream Tantivy ``documents`` into a new index and return it.

    When ``index_path`` is given the index is created on disk at that final
    path and the search schema version is persisted as index metadata after the
    final commit so a reader can validate compatibility when it reopens the
    index. When ``index_path`` is omitted an in-RAM index is built instead and
    no metadata is persisted. ``progress_callback`` receives the phase and
    number of submitted documents, including commit and merge phases.
    """
    index_dir = index_path
    if index_dir is not None:
        index_dir.mkdir(parents=True, exist_ok=True)
        index = Index(build_schema(), path=str(index_dir))
    else:
        index = Index(build_schema())
    _register_custom_tokenizers(index)

    indexed = 0

    def report(phase: str) -> None:
        if progress_callback:
            progress_callback(phase, indexed)

    report("indexing")
    writer = index.writer()
    try:
        for document in documents:
            writer.add_document(document)
            indexed += 1
            report("indexing")
        report("committing")
        writer.commit()
        report("merging")
        writer.wait_merging_threads()
    finally:
        del writer

    if index_dir is not None:
        _persist_schema_version(index_dir, SEARCH_SCHEMA_VERSION)

    index.reload()
    report("complete")
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
    """A page of hits, whether more matching units remain, and the match count.

    ``total_regions`` counts every matching region, at the record level too,
    where several regions can share one record.
    """

    hits: tuple[HitT, ...]
    has_more: bool
    total_regions: int


@dataclass(frozen=True)
class SearchHit:
    """One ranked region hit with its stored summary values.

    ``score`` is the relevance score, or ``None`` when hits are sorted by a
    field.
    """

    score: float | None
    fields: dict[str, Any]


@dataclass(frozen=True)
class RecordHit:
    """One ranked record, scored by its best-matching region."""

    score: float | None
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

    try:
        stored_version = _read_schema_version(path)
    except (ValueError, UnicodeError) as error:
        raise IndexIncompatibleError(
            f"Search index at {path} has an invalid schema version"
        ) from error
    if stored_version != SEARCH_SCHEMA_VERSION:
        raise IndexIncompatibleError(
            f"Search index at {path} has schema version {stored_version!r}; "
            f"expected {SEARCH_SCHEMA_VERSION}"
        )
    return index


def _stored_fields(searcher, address: Any) -> dict[str, Any]:
    raw = searcher.doc(address).to_dict()
    summary: dict[str, Any] = {}
    for field in _RETURNED_FIELDS:
        if field.name not in raw:
            continue
        value = raw[field.name]
        if field.multi:
            summary[field.name] = list(value)
        elif field.is_text:
            summary[field.name] = value[0] if value else ""
        else:
            summary[field.name] = value[0] if value else None
    return summary


def collect_first_values(index: Index) -> dict[str, str]:
    """Read the first non-empty stored value for each text field from ``index``.

    Scan all segments until every stored text field has a value or the corpus
    ends, and a multi-valued field contributes its first stored value. Number
    and boolean fields are skipped because no example template consumes them,
    and so is the catch-all text field, which is not stored.
    """
    text_fields = tuple(
        field.name for field in SEARCH_FIELDS if field.is_text and field.stored
    )
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


def parse_query(index: Index, query: str) -> Query:
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


def prepare_query(index: Index, query: str | Query) -> Query:
    """Parse a query string, or pass an already built query through.

    An empty query string raises :class:`EmptyQueryError`; a built query, such
    as a structured filter, may match every region.
    """
    if isinstance(query, Query):
        return query
    if not query.strip():
        raise EmptyQueryError()
    return parse_query(index, query)


@dataclass(frozen=True)
class Sort:
    """Order hits by one sortable field instead of by relevance."""

    field: str
    descending: bool = False


def _validate_pagination(offset: int, limit: int) -> None:
    if offset < 0:
        raise ValueError("offset must not be negative")
    if limit < 1:
        raise ValueError("limit must be at least 1")


def _search(
    searcher: Any,
    parsed: Query,
    limit: int,
    offset: int,
    sort: Sort | None,
    *,
    count: bool,
) -> Any:
    if sort is None:
        return searcher.search(parsed, limit=limit, offset=offset, count=count)
    return searcher.search(
        parsed,
        limit=limit,
        offset=offset,
        count=count,
        order_by_field=sort.field,
        order=Order.Desc if sort.descending else Order.Asc,
    )


def search_regions(
    index: Index,
    query: str | Query,
    offset: int = 0,
    limit: int = 10,
    *,
    sort: Sort | None = None,
) -> Results[SearchHit]:
    """Run ``query`` against an open ``index`` and return a page of regions.

    ``query`` is a query string or a built query (see :func:`prepare_query`).
    Unknown fields raise :class:`UnknownFieldError` naming the field and the
    available fields; the character position is not reported. Any other parser
    failure is surfaced as :class:`QuerySyntaxError` carrying the parser
    message. Results use Tantivy relevance ordering, or ``sort`` when given,
    and carry the stored identity and display fields for every hit. One extra
    hit beyond ``limit`` is fetched so ``has_more`` reports whether further
    pages exist.
    """
    parsed = prepare_query(index, query)
    _validate_pagination(offset, limit)

    searcher: Any = index.searcher()
    result = _search(searcher, parsed, limit + 1, offset, sort, count=True)
    fetched = list(result.hits)
    has_more = len(fetched) > limit
    hits = tuple(
        SearchHit(
            score=None if sort else score,
            fields=_stored_fields(searcher, address),
        )
        for score, address in fetched[:limit]
    )
    return Results(hits=hits, has_more=has_more, total_regions=result.count)


# Number of raw Tantivy hits pulled per round when collapsing matches. Keeps the
# full hit list (which can reach millions) from ever being materialized at once.
_FETCH_BATCH_SIZE = 1000


def _unique_matching_regions(
    index: Index,
    parsed: Query,
    key_fields: tuple[str, ...],
    max_needed: int,
    sort: Sort | None,
) -> tuple[list[tuple[float | None, dict[str, Any]]], int]:
    """Return up to ``max_needed`` distinct groups and the matching region count.

    Each group is a ``(score, stored_fields)`` pair. Matching regions are
    fetched from Tantivy in batches of :data:`_FETCH_BATCH_SIZE` and collapsed
    on ``key_fields`` so the full hit list (which can reach millions) is never
    held in memory at once. Documents arrive in relevance (or ``sort``) order,
    so the first occurrence of a grouping key carries that group's best score
    and position. Collapsing stops as soon as ``max_needed`` distinct groups
    have been collected, leaving the caller to tell from the returned length
    whether more groups remain.
    """
    searcher: Searcher = index.searcher()
    # Tantivy exposes count at runtime, but its SearchResult stub omits it.
    total = searcher.search(parsed, limit=1, count=True).count  # type: ignore[attr-defined]
    seen: set[tuple[Any, ...]] = set()
    unique: list[tuple[float | None, dict[str, Any]]] = []
    for offset in range(0, total, _FETCH_BATCH_SIZE):
        result = _search(searcher, parsed, _FETCH_BATCH_SIZE, offset, sort, count=False)
        if not result.hits:
            break
        for score, address in result.hits:
            fields = _stored_fields(searcher, address)
            key = tuple(fields.get(name) for name in key_fields)
            if key in seen:
                continue
            seen.add(key)
            unique.append((None if sort else score, fields))
            if len(unique) >= max_needed:
                return unique, total
    return unique, total


def search_record(
    index: Index,
    query: str | Query,
    offset: int = 0,
    limit: int = 10,
    *,
    sort: Sort | None = None,
) -> Results[RecordHit]:
    """Run ``query`` and return a page of unique records.

    A record is identified by its output file and record id. Every region
    matching ``query`` contributes to its parent record, but each record is
    reported once, scored by its highest-scoring matching region, and ordered
    by that score, or by its first region in ``sort`` order. ``offset`` and
    ``limit`` paginate that distinct set; one extra group is collapsed so
    ``has_more`` reports whether further records remain.
    """
    parsed = prepare_query(index, query)
    _validate_pagination(offset, limit)

    unique, total = _unique_matching_regions(
        index, parsed, ("output_file", "record"), offset + limit + 1, sort
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
    return Results(hits=hits, has_more=has_more, total_regions=total)


@dataclass(frozen=True)
class FacetBucket:
    """One field value and the number of regions holding it."""

    value: str
    count: int


class FacetFieldError(SearchError):
    """Raised when values are requested for a field that cannot be counted."""

    code = "invalid_facet_field"

    def __init__(self, field: str) -> None:
        super().__init__(
            f"Values of field {field!r} cannot be counted; only exact text "
            "and yes/no fields can"
        )
        self.field = field


def _check_facet_field(name: str) -> SearchField:
    field = SEARCH_FIELDS_BY_NAME.get(name)
    if field is None:
        raise UnknownFieldError(name, _FIELD_NAMES)
    if not field.facet:
        raise FacetFieldError(name)
    return field


def _buckets(aggregation: dict[str, Any]) -> list[FacetBucket]:
    # Boolean buckets carry the value as ``key_as_string``, text buckets as ``key``.
    return [
        FacetBucket(
            value=str(bucket.get("key_as_string", bucket["key"])),
            count=int(bucket["doc_count"]),
        )
        for bucket in aggregation.get("buckets", [])
    ]


def facet_counts(
    index: Index, query: str | Query, fields: Iterable[str], size: int = 20
) -> dict[str, list[FacetBucket]]:
    """Count the most common values of ``fields`` over every region matching ``query``.

    Each field reports up to ``size`` values, most common first. Counts are
    regions, at the record level too. Raises :class:`UnknownFieldError` or
    :class:`FacetFieldError` for a field that cannot be counted.
    """
    names = list(dict.fromkeys(fields))
    for name in names:
        _check_facet_field(name)
    if not names:
        return {}
    parsed = prepare_query(index, query)
    result = index.searcher().aggregate(
        parsed,
        {name: {"terms": {"field": name, "size": size}} for name in names},
    )
    return {name: _buckets(result.get(name, {})) for name in names}


# Number of matching values ranked when suggesting values for a field.
_SUGGESTION_POOL = 1000


def field_values(
    index: Index, field: str, contains: str = "", size: int = 20
) -> list[FacetBucket]:
    """Suggest values of ``field`` containing ``contains``, ignoring case.

    Counts are regions across the whole index. Values that start with
    ``contains`` come first, then by count, then alphabetically, so typing the
    start of a value finds it even when a more common value contains it later.
    """
    _check_facet_field(field)
    needle = contains.strip()
    terms: dict[str, Any] = {"field": field, "size": _SUGGESTION_POOL}
    if needle:
        terms["include"] = f"(?i).*{re.escape(needle)}.*"
    result = index.searcher().aggregate(Query.all_query(), {"values": {"terms": terms}})
    buckets = _buckets(result.get("values", {}))
    lowered = needle.lower()
    buckets.sort(
        key=lambda bucket: (
            not bucket.value.lower().startswith(lowered),
            -bucket.count,
            bucket.value,
        )
    )
    return buckets[:size]
