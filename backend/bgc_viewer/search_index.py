"""Record-level full-text search for antiSMASH 8 results."""

import collections.abc
import pathlib
import shutil
import typing

import tantivy

SEARCH_INDEX_SUFFIX = ".tantivy"
SEARCH_FIELDS = ["record_id", "filename", "attribute_values", "attributes"]
SKIPPED_FIELDS = {"letter_annotations", "seq", "translation"}
MAX_SEARCH_VALUE_LENGTH = 100


def get_search_index_path(db_path: str | pathlib.Path) -> pathlib.Path:
    """Return the Tantivy directory stored alongside an attributes database."""
    return pathlib.Path(db_path).with_suffix(SEARCH_INDEX_SUFFIX)


def build_search_schema():
    """Build the stable record-level schema used for antiSMASH 8 JSON files."""
    builder = tantivy.SchemaBuilder()
    builder.add_integer_field(
        "record_internal_id", stored=True, indexed=True, fast=True
    )
    builder.add_text_field("record_id", stored=True)
    builder.add_text_field("filename", stored=True)
    builder.add_text_field("attribute_values")
    builder.add_json_field("attributes")
    return builder.build()


def create_search_index(db_path: str | pathlib.Path):
    """Create an empty search index, replacing a previous preprocessing run."""
    index_path = get_search_index_path(db_path)
    if index_path.exists():
        shutil.rmtree(index_path)
    index_path.mkdir(parents=True)
    return tantivy.Index(build_search_schema(), path=str(index_path))


def iter_search_values(
    value: typing.Any, path: tuple[str, ...] = ()
) -> collections.abc.Iterable[tuple[str, str]]:
    """Yield searchable scalar paths and values from an antiSMASH record."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key not in SKIPPED_FIELDS:
                yield from iter_search_values(child, (*path, key))
    elif isinstance(value, list):
        for child in value:
            yield from iter_search_values(child, path)
    elif value is not None:
        text = str(value)
        if text and len(text) <= MAX_SEARCH_VALUE_LENGTH:
            yield ".".join(path), text


def make_search_document(
    record_internal_id: int,
    record_id: str,
    filename: str,
    record: dict[str, typing.Any],
):
    """Create one compact Tantivy document for an antiSMASH record."""
    attributes: dict[str, list[str]] = {}
    for attribute_path, attribute_value in iter_search_values(record):
        attribute_name = attribute_path.rsplit(".", 1)[-1]
        attributes.setdefault(attribute_name, []).append(attribute_value)

    document = tantivy.Document(
        record_internal_id=record_internal_id,
        record_id=record_id,
        filename=filename,
        attribute_values=[
            value
            for attribute_values in attributes.values()
            for value in attribute_values
        ],
    )
    document.add_json("attributes", attributes)
    return document


def search_record_ids(
    db_path: str | pathlib.Path, search: str, limit: int, offset: int = 0
) -> tuple[list[int], int]:
    """Return matching SQLite record IDs and the total record count."""
    index_path = get_search_index_path(db_path)
    if not index_path.is_dir():
        raise FileNotFoundError(f"Search index not found: {index_path}")

    index = tantivy.Index.open(str(index_path))
    query = index.parse_query(search, SEARCH_FIELDS, conjunction_by_default=True)
    result: typing.Any = index.searcher().search(query, limit=limit, offset=offset)
    searcher = index.searcher()
    record_ids = [
        int(searcher.doc(address)["record_internal_id"][0])
        for _, address in result.hits
    ]
    return record_ids, int(result.count)
