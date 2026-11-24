import multiprocessing
import os
import warnings
from collections.abc import Callable, Iterable, Iterator, Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

import ijson
from tantivy import Document

from bgc_viewer.data_loader import open_file

from . import facets
from .document import (
    KIND_FIELD,
    SEARCH_FIELDS,
    TEXT_FIELD,
    DocumentKind,
    Location,
    SourceFile,
)
from .facets import RegionScope, normalize_pfam


class ExtractionError(ValueError):
    pass


class ExtractionWarning(UserWarning):
    def __init__(
        self,
        code: str,
        source_path: str,
        record_id: str,
        json_path: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.source_path = source_path
        self.record_id = record_id
        self.json_path = json_path

    def __reduce__(self):
        # Rebuild from all fields so warnings survive the trip back from an
        # extraction worker process.
        return (
            self.__class__,
            (self.code, self.source_path, self.record_id, self.json_path, str(self)),
        )


@dataclass(frozen=True)
class _Feature:
    feature_type: str
    location: Location
    qualifiers: Mapping[str, object]
    json_path: str


# Feature types that only contribute optional values, so a malformed one is
# skipped with a warning instead of failing the file.
_OPTIONAL_FEATURE_TYPES = frozenset(
    {"gene", "PFAM_domain", "CDS", "aSDomain", "cand_cluster"}
)

# CDS ``gene_kind`` qualifier -> the field counting CDS features of that kind.
_GENE_KIND_FIELDS = {
    "biosynthetic": "n_core_biosynthetic",
    "biosynthetic-additional": "n_additional_biosynthetic",
    "transport": "n_transport",
    "regulatory": "n_regulatory",
    "resistance": "n_resistance",
}


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ExtractionError(f"Missing or incompatible object at {path}")
    return value


def _items(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise ExtractionError(f"Missing or incompatible array at {path}")
    return value


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExtractionError(f"Missing or incompatible string at {path}")
    return value.strip()


def _values(qualifiers: Mapping[str, object], name: str) -> tuple[str, ...]:
    raw = qualifiers.get(name, [])
    values = raw if isinstance(raw, list) else [raw]
    return tuple(
        dict.fromkeys(
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        )
    )


def _required_value(qualifiers: Mapping[str, object], name: str, path: str) -> str:
    values = _values(qualifiers, name)
    if not values:
        raise ExtractionError(f"Missing qualifier at {path}.{name}")
    return values[0]


def _number(qualifiers: Mapping[str, object], name: str, path: str) -> int:
    value = _required_value(qualifiers, name, path)
    try:
        return int(value)
    except ValueError as error:
        raise ExtractionError(f"Invalid integer at {path}.{name}") from error


def _feature(value: object, path: str) -> _Feature:
    feature = _mapping(value, path)
    feature_type = _text(feature.get("type"), f"{path}.type")
    location = Location.parse(_text(feature.get("location"), f"{path}.location"))
    qualifiers = _mapping(feature.get("qualifiers", {}), f"{path}.qualifiers")
    return _Feature(feature_type, location, qualifiers, path)


def _cds_name(cds: _Feature) -> str | None:
    """The name antiSMASH gives a CDS, and keys its module results by."""
    for qualifier in ("locus_tag", "gene", "protein_id"):
        values = _values(cds.qualifiers, qualifier)
        if values:
            return values[0]
    return None


def _parent_region_key(region: _Feature, record_path: str) -> tuple[int, int, str]:
    size = sum(part.end - part.start for part in region.location.parts)
    region_number = _number(region.qualifiers, "region_number", record_path)
    return size, region_number, region.location.serialized


def _emit_warning(
    warning: ExtractionWarning,
    counts: dict[str, int],
    threshold: int,
) -> None:
    warnings.warn(warning, stacklevel=3)
    counts[warning.code] = counts.get(warning.code, 0) + 1
    if counts[warning.code] >= threshold:
        raise ExtractionError(
            f"Reached warning threshold {threshold} for {warning.code} "
            f"in {warning.source_path}"
        )


def _parse_features(
    record: Mapping[str, object],
    record_path: str,
    source_path: str,
    record_id: str,
    warning_counts: dict[str, int],
    warning_threshold: int,
) -> list[_Feature]:
    features: list[_Feature] = []
    raw_features = _items(record.get("features"), f"{record_path}.features")
    for feature_index, value in enumerate(raw_features):
        feature_path = f"{record_path}.features[{feature_index}]"
        raw_feature = _mapping(value, feature_path)
        feature_type = raw_feature.get("type")
        try:
            features.append(_feature(raw_feature, feature_path))
        except (ExtractionError, ValueError) as error:
            if feature_type not in _OPTIONAL_FEATURE_TYPES:
                raise
            _emit_warning(
                ExtractionWarning(
                    code="malformed_optional_feature",
                    source_path=source_path,
                    record_id=record_id,
                    json_path=feature_path,
                    message=f"Skipping malformed optional feature: {error}",
                ),
                warning_counts,
                warning_threshold,
            )
    return features


def _select_parent_region(
    protocluster: _Feature,
    regions: list[_Feature],
    record_path: str,
    source_path: str,
    record_id: str,
    warning_counts: dict[str, int],
    warning_threshold: int,
) -> _Feature:
    parents = [
        region for region in regions if region.location.contains(protocluster.location)
    ]
    if not parents:
        raise ExtractionError(f"No containing region for protocluster in {record_path}")
    if len(parents) > 1:
        _emit_warning(
            ExtractionWarning(
                code="multiple_parent_regions",
                source_path=source_path,
                record_id=record_id,
                json_path=protocluster.json_path,
                message=(
                    f"Protocluster has {len(parents)} containing regions; "
                    "selecting deterministically"
                ),
            ),
            warning_counts,
            warning_threshold,
        )
    return min(
        parents,
        key=partial(_parent_region_key, record_path=record_path),
    )


def _annotation_values(
    region: _Feature,
    annotations: list[_Feature],
    source_path: str,
    record_id: str,
    warning_counts: dict[str, int],
    warning_threshold: int,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    genes: list[str] = []
    loci: list[str] = []
    pfams: list[str] = []
    pfam_names: list[str] = []
    for annotation in annotations:
        if not region.location.overlaps(annotation.location):
            continue
        if annotation.feature_type == "gene":
            genes.extend(_values(annotation.qualifiers, "gene"))
            loci.extend(_values(annotation.qualifiers, "locus_tag"))
        else:
            accessions = _values(annotation.qualifiers, "db_xref")
            if not accessions:
                _emit_warning(
                    ExtractionWarning(
                        code="missing_pfam_accession",
                        source_path=source_path,
                        record_id=record_id,
                        json_path=annotation.json_path,
                        message=(
                            "Skipping PFAM annotation without a usable "
                            "accession and its description"
                        ),
                    ),
                    warning_counts,
                    warning_threshold,
                )
                continue
            pfams.extend(normalize_pfam(value) for value in accessions)
            pfam_names.extend(_values(annotation.qualifiers, "description"))
    return (
        tuple(dict.fromkeys(genes)),
        tuple(dict.fromkeys(loci)),
        tuple(dict.fromkeys(pfams)),
        tuple(dict.fromkeys(pfam_names)),
    )


@dataclass(frozen=True)
class _RecordContext:
    """The parts of a record every one of its regions is extracted from."""

    record_id: str
    record_path: str
    organism: str
    annotations: list[_Feature]
    cds_features: list[_Feature]
    candidates: list[_Feature]
    domain_cds: Mapping[str, str]
    modules: Mapping[str, Any]


def _protocluster_values(
    protoclusters: list[_Feature], record_path: str
) -> tuple[list[str], list[str], list[str], frozenset[str]]:
    products: list[str] = []
    categories: list[str] = []
    rules: list[str] = []
    numbers: set[str] = set()
    for protocluster in protoclusters:
        products.append(
            _required_value(protocluster.qualifiers, "product", record_path)
        )
        category = _values(protocluster.qualifiers, "product_category") or _values(
            protocluster.qualifiers, "category"
        )
        if not category:
            raise ExtractionError(
                f"Missing protocluster product category in {record_path}"
            )
        categories.append(category[0])
        rules.extend(_values(protocluster.qualifiers, "detection_rule"))
        numbers.add(
            str(_number(protocluster.qualifiers, "protocluster_number", record_path))
        )
    return products, categories, rules, frozenset(numbers)


@dataclass(frozen=True)
class _Extent:
    """What one document covers: a whole region, or one of its protoclusters.

    ``feature`` is the region or protocluster whose location bounds every
    location-derived value. ``protoclusters`` are the protoclusters the
    document describes: all of the region's, or the one protocluster.
    ``rules`` are detection rules beyond the protoclusters' own,
    ``candidate_kinds`` the kinds of the candidate clusters it belongs to, and
    ``contig_edge`` the contig edge qualifier that decides ``is_complete``.
    Region-level values (``region_number`` and ``num_protoclusters``) are those
    of the region or the protocluster's parent region.
    """

    kind: DocumentKind
    feature: _Feature
    region_number: int
    num_protoclusters: int
    protoclusters: list[_Feature]
    rules: tuple[str, ...]
    candidate_kinds: list[str]
    contig_edge: tuple[str, ...]
    protocluster_number: int | None = None


def _region_extent(
    region: _Feature,
    region_number: int,
    protoclusters: list[_Feature],
    context: _RecordContext,
) -> _Extent:
    return _Extent(
        kind="region",
        feature=region,
        region_number=region_number,
        num_protoclusters=len(protoclusters),
        protoclusters=protoclusters,
        rules=_values(region.qualifiers, "rules"),
        candidate_kinds=[
            kind
            for candidate in context.candidates
            if region.location.contains(candidate.location)
            for kind in _values(candidate.qualifiers, "kind")
        ],
        contig_edge=_values(region.qualifiers, "contig_edge"),
    )


def _protocluster_extent(
    protocluster: _Feature,
    region: _Feature,
    region_number: int,
    siblings: list[_Feature],
    context: _RecordContext,
) -> _Extent:
    """The extent of one protocluster, over its full location.

    A protocluster belongs to the candidate clusters that list its number, and
    falls back to its region's contig edge mark when it has none of its own.
    """
    number = _number(
        protocluster.qualifiers, "protocluster_number", context.record_path
    )
    return _Extent(
        kind="protocluster",
        feature=protocluster,
        region_number=region_number,
        num_protoclusters=len(siblings),
        protoclusters=[protocluster],
        rules=(),
        candidate_kinds=[
            kind
            for candidate in context.candidates
            if str(number) in _values(candidate.qualifiers, "protoclusters")
            for kind in _values(candidate.qualifiers, "kind")
        ],
        contig_edge=_values(protocluster.qualifiers, "contig_edge")
        or _values(region.qualifiers, "contig_edge"),
        protocluster_number=number,
    )


def _document_values(
    extent: _Extent,
    context: _RecordContext,
    source: SourceFile,
    warning_counts: dict[str, int],
    warning_threshold: int,
) -> dict[str, list[Any]]:
    """Collect every field value of one region or protocluster, keyed by field."""
    feature = extent.feature
    products, categories, rules, protocluster_numbers = _protocluster_values(
        extent.protoclusters, context.record_path
    )
    if not extent.protoclusters:
        products = list(_values(feature.qualifiers, "product"))

    extent_cds = [
        cds for cds in context.cds_features if feature.location.overlaps(cds.location)
    ]
    gene_kind_counts = dict.fromkeys(_GENE_KIND_FIELDS.values(), 0)
    for cds in extent_cds:
        kinds = _values(cds.qualifiers, "gene_kind")
        if kinds and kinds[0] in _GENE_KIND_FIELDS:
            gene_kind_counts[_GENE_KIND_FIELDS[kinds[0]]] += 1

    genes, loci, pfams, pfam_names = _annotation_values(
        feature,
        context.annotations,
        source.output_file,
        context.record_id,
        warning_counts,
        warning_threshold,
    )

    contig_edge = extent.contig_edge
    values: dict[str, list[Any]] = {
        "record": [context.record_id],
        "region": [extent.region_number],
        "start": [feature.location.start],
        "end": [feature.location.end],
        "length": [sum(part.end - part.start for part in feature.location.parts)],
        "product": list(dict.fromkeys(products)),
        "product_category": list(dict.fromkeys(categories)),
        "protocluster_number": (
            [extent.protocluster_number]
            if extent.protocluster_number is not None
            else []
        ),
        "num_protoclusters": [extent.num_protoclusters],
        "candidate_kind": list(dict.fromkeys(extent.candidate_kinds)),
        "detection_rules": list(dict.fromkeys([*extent.rules, *rules])),
        "is_complete": [not (contig_edge and contig_edge[0].lower() == "true")],
        "organism": [context.organism] if context.organism else [],
        "output_file": [source.output_file],
        "input_file": [source.input_file] if source.input_file else [],
        "gene": list(genes),
        "locus": list(loci),
        "num_cds_features": [len(extent_cds)],
        **{name: [count] for name, count in gene_kind_counts.items()},
    }

    # Module results keyed by region number resolve against the parent region,
    # so a protocluster inherits them; everything else is bounded by the
    # extent's own location and protocluster numbers.
    scope = RegionScope(
        location=feature.location,
        number=extent.region_number,
        products=tuple(values["product"]),
        cds_names=frozenset(
            name for name in map(_cds_name, extent_cds) if name is not None
        ),
        protocluster_numbers=protocluster_numbers,
        domain_cds=context.domain_cds,
    )
    functional, hit_pfams, hit_pfam_names = facets.functional_hits(
        context.modules, scope
    )
    values["pfam"] = list(dict.fromkeys([*pfams, *hit_pfams]))
    values["pfam_desc"] = list(dict.fromkeys([*pfam_names, *hit_pfam_names]))
    values.update(functional)
    values.update(facets.go_terms(context.modules, values["pfam"]))
    values.update(facets.nrps_pks(context.modules, scope))
    values.update(facets.terpene_t2pks(context.modules, scope))
    values.update(facets.ripp(context.modules, scope))
    values.update(facets.comparative(context.modules, scope))
    return values


def build_document(
    values: Mapping[str, list[Any]], kind: DocumentKind = "region"
) -> Document:
    """Write collected field values into a Tantivy document of ``kind``.

    Each value is added once with the method for its field's type, so facet
    counts count a document once per value, and the text values of every field
    that sets ``in_text`` are also added to the catch-all text field.
    """
    unknown = set(values) - {field.name for field in SEARCH_FIELDS}
    if unknown:
        raise AssertionError(f"Values for unregistered fields: {sorted(unknown)}")
    document = Document()
    document.add_text(KIND_FIELD, kind)
    text: list[str] = []
    for field in SEARCH_FIELDS:
        for value in dict.fromkeys(values.get(field.name, ())):
            if field.is_text:
                document.add_text(field.name, value)
                if field.in_text:
                    text.append(value)
            elif field.tokenizer == "integer":
                document.add_integer(field.name, value)
            elif field.tokenizer == "float":
                document.add_float(field.name, value)
            else:
                document.add_boolean(field.name, value)
    for value in dict.fromkeys(text):
        document.add_text(TEXT_FIELD, value)
    return document


def _check_identity(
    source: SourceFile,
    record_id: str,
    region_number: int,
    identities: dict[tuple[str, str, int], SourceFile],
) -> None:
    identity = (source.input_file, record_id, region_number)
    previous_source = identities.get(identity)
    if previous_source is not None:
        identity_text = ":".join(str(value) for value in identity)
        raise ExtractionError(
            f"Duplicate biological identity {identity_text}: "
            f"{previous_source.output_file} "
            f"(antiSMASH {previous_source.antismash_version}) and "
            f"{source.output_file} (antiSMASH {source.antismash_version})"
        )
    identities[identity] = source


def _record_context(
    record: Mapping[str, object],
    record_id: str,
    record_path: str,
    features: list[_Feature],
) -> _RecordContext:
    source_features = [
        feature for feature in features if feature.feature_type == "source"
    ]
    organism_values = (
        _values(source_features[0].qualifiers, "organism") if source_features else ()
    )
    domain_cds: dict[str, str] = {}
    for feature in features:
        if feature.feature_type != "aSDomain":
            continue
        domain_ids = _values(feature.qualifiers, "domain_id")
        cds_names = _values(feature.qualifiers, "locus_tag")
        if domain_ids and cds_names:
            domain_cds[domain_ids[0]] = cds_names[0]
    modules = record.get("modules")
    return _RecordContext(
        record_id=record_id,
        record_path=record_path,
        organism=organism_values[0] if organism_values else "",
        annotations=[
            feature
            for feature in features
            if feature.feature_type in {"gene", "PFAM_domain"}
        ],
        cds_features=[feature for feature in features if feature.feature_type == "CDS"],
        candidates=[
            feature for feature in features if feature.feature_type == "cand_cluster"
        ],
        domain_cds=domain_cds,
        modules=modules if isinstance(modules, dict) else {},
    )


def _extract_records(
    records: Iterable[object],
    source: SourceFile,
    warning_threshold: int,
    identities: dict[tuple[str, str, int], SourceFile],
) -> Iterator[Document]:
    source_path = source.output_file
    warning_counts: dict[str, int] = {}
    found_region = False

    for record_index, raw_record in enumerate(records):
        record_path = f"records[{record_index}]"
        record = _mapping(raw_record, record_path)
        record_id = _text(record.get("id"), f"{record_path}.id")
        features = _parse_features(
            record,
            record_path,
            source_path,
            record_id,
            warning_counts,
            warning_threshold,
        )
        regions = [feature for feature in features if feature.feature_type == "region"]

        # Each protocluster belongs to the smallest region containing it.
        protoclusters: dict[str, list[_Feature]] = {
            region.json_path: [] for region in regions
        }
        for protocluster in (
            feature for feature in features if feature.feature_type == "protocluster"
        ):
            parent = _select_parent_region(
                protocluster,
                regions,
                record_path,
                source_path,
                record_id,
                warning_counts,
                warning_threshold,
            )
            protoclusters[parent.json_path].append(protocluster)

        context = _record_context(record, record_id, record_path, features)
        for region in regions:
            found_region = True
            region_number = _number(region.qualifiers, "region_number", record_path)
            children = protoclusters[region.json_path]
            extents = [
                _region_extent(region, region_number, children, context),
                *(
                    _protocluster_extent(
                        protocluster, region, region_number, children, context
                    )
                    for protocluster in children
                ),
            ]
            _check_identity(source, record_id, region_number, identities)
            for extent in extents:
                values = _document_values(
                    extent, context, source, warning_counts, warning_threshold
                )
                yield build_document(values, extent.kind)

    if not found_region:
        _emit_warning(
            ExtractionWarning(
                code="no_regions",
                source_path=source_path,
                record_id="",
                json_path="records",
                message="Selected file contains no regions",
            ),
            warning_counts,
            warning_threshold,
        )


_MISSING = object()


def _read_file_metadata(source_path: Path) -> tuple[str, str]:
    version: object = _MISSING
    input_file: object = _MISSING
    with open_file(source_path, "rb") as handle:
        for prefix, _event, value in ijson.parse(handle):
            if prefix == "version" and version is _MISSING:
                version = value
            elif prefix == "input_file" and input_file is _MISSING:
                input_file = value
            if version is not _MISSING and input_file is not _MISSING:
                break
    text_version = _text(None if version is _MISSING else version, "version")
    text_input = input_file.strip() if isinstance(input_file, str) else ""
    return text_version, text_input


def extract(
    records: Iterable[object],
    source: SourceFile,
    *,
    warning_threshold: int = 100,
    identities: dict[tuple[str, str, int], SourceFile] | None = None,
) -> Iterator[Document]:
    """Extract Tantivy documents from already-decoded antiSMASH record objects.

    This entry point performs no file I/O: callers supply the decoded
    ``records`` iterable and a fully-populated :class:`SourceFile`, so the
    same core serves in-memory callers and the streaming file path in
    :func:`extract_documents`. The ``identities`` mapping is threaded
    through so :func:`extract_documents` can detect duplicate biological
    identities across files; when omitted, each call tracks its own.
    """
    if warning_threshold < 1:
        raise ValueError("warning_threshold must be at least 1")
    try:
        yield from _extract_records(
            records,
            source,
            warning_threshold,
            identities if identities is not None else {},
        )
    except ExtractionError as error:
        raise ExtractionError(
            f"{source.output_file} (antiSMASH {source.antismash_version}): {error}"
        ) from error


_Identity = tuple[str, str, int]


@dataclass(frozen=True)
class _FileResult:
    """Everything one worker extracted from one file, in file order."""

    source: SourceFile | None
    documents: list[Document]
    identities: list[_Identity]
    warnings: list[Warning | str]
    error: ExtractionError | None


def _extract_file(
    source_path: Path, relative_path: str, warning_threshold: int
) -> _FileResult:
    """Extract one file. Runs in a worker process, so it shares no state.

    Warnings and errors are captured rather than raised, so the caller can
    replay them in file order exactly as a sequential run would. Duplicate
    identities within the file are caught here; duplicates across files are
    checked by the caller from the returned ``identities``.
    """
    source = None
    documents: list[Document] = []
    identities: dict[_Identity, SourceFile] = {}
    error = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            version, input_file = _read_file_metadata(source_path)
            source = SourceFile(version, relative_path, input_file)
            with open_file(source_path, "rb") as handle:
                records = ijson.items(handle, "records.item", use_float=True)
                documents.extend(
                    extract(
                        records,
                        source,
                        warning_threshold=warning_threshold,
                        identities=identities,
                    )
                )
        except ExtractionError as extraction_error:
            # Errors from the records already name the file; one from its
            # header, read before the file is known as a source, does not.
            error = (
                extraction_error
                if source is not None
                else ExtractionError(f"{relative_path}: {extraction_error}")
            )
    return _FileResult(
        source,
        documents,
        list(identities),
        [warning.message for warning in caught],
        error,
    )


def default_extraction_workers() -> int:
    return os.cpu_count() or 1


def extract_documents(
    files: Iterable[Path],
    source_root: Path,
    *,
    warning_threshold: int = 100,
    workers: int | None = None,
    file_progress: Callable[[int, int], None] | None = None,
) -> Iterator[Document]:
    """Stream Tantivy documents for ``files``, in file order.

    ``file_progress`` receives the number of files whose documents have all
    been yielded and the total number of files, once before the first file and
    again after each file.

    Parsing antiSMASH JSON is CPU-bound Python, so files are extracted in
    parallel worker processes (``workers``, default one per CPU) while this
    generator replays each file's warnings and documents in the order the
    files were given. The output, warnings, and errors are the same as a
    sequential run, which is used for a single file or ``workers=1``.
    """
    if warning_threshold < 1:
        raise ValueError("warning_threshold must be at least 1")
    root = source_root.resolve()
    selected: list[tuple[Path, str]] = []
    for selected_path in files:
        source_path = (root / selected_path).resolve()
        try:
            relative_path = source_path.relative_to(root).as_posix()
        except ValueError as error:
            raise ExtractionError(
                f"Selected path is outside source root: {selected_path}"
            ) from error
        selected.append((source_path, relative_path))

    if file_progress:
        file_progress(0, len(selected))

    workers = min(workers or default_extraction_workers(), len(selected))
    if workers <= 1:
        yield from _merge_results(
            (
                _extract_file(source_path, relative_path, warning_threshold)
                for source_path, relative_path in selected
            ),
            len(selected),
            file_progress,
        )
        return

    # Spawned rather than forked workers: the caller may be a thread of a
    # multithreaded server, and forking a multithreaded process is unsafe.
    pool = ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    )
    try:
        yield from _merge_results(
            pool.map(
                _extract_file,
                [source_path for source_path, _ in selected],
                [relative_path for _, relative_path in selected],
                [warning_threshold] * len(selected),
            ),
            len(selected),
            file_progress,
        )
    finally:
        # Do not wait for files nobody will consume after an error or an
        # abandoned generator.
        pool.shutdown(wait=False, cancel_futures=True)


def _merge_results(
    results: Iterable[_FileResult],
    total_files: int,
    file_progress: Callable[[int, int], None] | None,
) -> Iterator[Document]:
    """Replay per-file results in order, checking identities across files."""
    identities: dict[_Identity, SourceFile] = {}
    for files_done, result in enumerate(results, start=1):
        for message in result.warnings:
            warnings.warn(message, stacklevel=2)
        if result.error is not None:
            raise result.error
        assert result.source is not None
        source = result.source
        # A file yields a region document and its protoclusters' documents per
        # identity, so the whole file is checked before any of it is yielded.
        for _, record_id, region in result.identities:
            try:
                _check_identity(source, record_id, region, identities)
            except ExtractionError as error:
                raise ExtractionError(
                    f"{source.output_file} (antiSMASH {source.antismash_version}): "
                    f"{error}"
                ) from error
        yield from result.documents
        if file_progress:
            file_progress(files_done, total_files)
