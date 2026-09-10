"""Build protocluster search indexes on top of the ``tantivy`` engine.

The Tantivy schema is derived entirely from the field registry in
:mod:`bgc_viewer.search.document`; biological fields are never hard-coded
here. Only the search schema version is persisted as index metadata so a
reader can validate compatibility when it opens the index.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from os import PathLike
from pathlib import Path
from typing import cast

from tantivy import Document, Index, Schema, SchemaBuilder

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
