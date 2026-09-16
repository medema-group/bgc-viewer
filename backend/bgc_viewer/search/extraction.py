import re
import warnings
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Protocol

import ijson

from .document import (
    Location,
    ProtoclusterSearchDocument,
    SearchFields,
    SourceFile,
)


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


class SourceAdapter(Protocol):
    name: str

    def extract(
        self,
        records: Iterable[object],
        source: SourceFile,
        warning_threshold: int,
        identities: dict[tuple[str, str, int, int], SourceFile],
    ) -> Iterator[ProtoclusterSearchDocument]: ...


@dataclass(frozen=True)
class _Feature:
    feature_type: str
    location: Location
    qualifiers: Mapping[str, object]
    json_path: str


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


def _normalize_pfam(accession: str) -> str:
    """Remove a numeric version from a standard PFAM accession.

    For example, ``PF00512.28`` becomes ``PF00512``. Non-standard database
    cross-references and unversioned accessions are retained unchanged.
    """
    match = re.fullmatch(r"(PF\d{5})\.\d+", accession)
    return match.group(1) if match else accession


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
            if feature_type not in {"gene", "PFAM_domain"}:
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
    protocluster: _Feature,
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
        if not protocluster.location.overlaps(annotation.location):
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
            pfams.extend(_normalize_pfam(value) for value in accessions)
            pfam_names.extend(_values(annotation.qualifiers, "description"))
    return (
        tuple(dict.fromkeys(genes)),
        tuple(dict.fromkeys(loci)),
        tuple(dict.fromkeys(pfams)),
        tuple(dict.fromkeys(pfam_names)),
    )


def _document(
    protocluster: _Feature,
    parent: _Feature,
    annotations: list[_Feature],
    organism: str,
    record_id: str,
    record_path: str,
    source: SourceFile,
    warning_counts: dict[str, int],
    warning_threshold: int,
) -> ProtoclusterSearchDocument:
    category = _values(protocluster.qualifiers, "product_category") or _values(
        protocluster.qualifiers, "category"
    )
    if not category:
        raise ExtractionError(f"Missing protocluster product category in {record_path}")
    region_number = _number(parent.qualifiers, "region_number", record_path)
    protocluster_number = _number(
        protocluster.qualifiers, "protocluster_number", record_path
    )
    genes, loci, pfams, pfam_names = _annotation_values(
        protocluster,
        annotations,
        source.source_path,
        record_id,
        warning_counts,
        warning_threshold,
    )
    return ProtoclusterSearchDocument(
        source=source,
        search_fields=SearchFields(
            record_id=record_id,
            region_number=region_number,
            protocluster_number=protocluster_number,
            location=protocluster.location,
            product=_required_value(protocluster.qualifiers, "product", record_path),
            category=category[0],
            organism=organism,
            pfam=pfams,
            pfam_name=pfam_names,
            gene=genes,
            locus=loci,
        ),
    )


def _check_identity(
    document: ProtoclusterSearchDocument,
    identities: dict[tuple[str, str, int, int], SourceFile],
) -> None:
    source = document.source
    fields = document.search_fields
    identity = (
        source.input_file,
        fields.record_id,
        fields.region_number,
        fields.protocluster_number,
    )
    previous_source = identities.get(identity)
    if previous_source is not None:
        identity_text = ":".join(str(value) for value in identity)
        raise ExtractionError(
            f"Duplicate biological identity {identity_text}: "
            f"{previous_source.source_path} "
            f"(antiSMASH {previous_source.antismash_version}) and "
            f"{source.source_path} (antiSMASH {source.antismash_version})"
        )
    identities[identity] = source


def _extract_records(
    records: Iterable[object],
    source: SourceFile,
    warning_threshold: int,
    identities: dict[tuple[str, str, int, int], SourceFile],
) -> Iterator[ProtoclusterSearchDocument]:
    source_path = source.source_path
    warning_counts: dict[str, int] = {}
    found_protocluster = False

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
        source_features = [
            feature for feature in features if feature.feature_type == "source"
        ]
        organism_values = (
            _values(source_features[0].qualifiers, "organism")
            if source_features
            else ()
        )
        regions = [feature for feature in features if feature.feature_type == "region"]
        annotations = [
            feature
            for feature in features
            if feature.feature_type in {"gene", "PFAM_domain"}
        ]

        for protocluster in (
            feature for feature in features if feature.feature_type == "protocluster"
        ):
            found_protocluster = True
            parent = _select_parent_region(
                protocluster,
                regions,
                record_path,
                source_path,
                record_id,
                warning_counts,
                warning_threshold,
            )
            document = _document(
                protocluster,
                parent,
                annotations,
                organism_values[0] if organism_values else "",
                record_id,
                record_path,
                source,
                warning_counts,
                warning_threshold,
            )
            _check_identity(document, identities)
            yield document

    if not found_protocluster:
        _emit_warning(
            ExtractionWarning(
                code="no_protoclusters",
                source_path=source_path,
                record_id="",
                json_path="records",
                message="Selected file contains no protoclusters",
            ),
            warning_counts,
            warning_threshold,
        )


class Antismash8Adapter:
    name = "Antismash8Adapter"

    def extract(
        self,
        records: Iterable[object],
        source: SourceFile,
        warning_threshold: int,
        identities: dict[tuple[str, str, int, int], SourceFile],
    ) -> Iterator[ProtoclusterSearchDocument]:
        yield from _extract_records(records, source, warning_threshold, identities)


_V8_ADAPTER = Antismash8Adapter()
_ADAPTERS: dict[int, SourceAdapter] = {8: _V8_ADAPTER}


def _declared_major(version: str) -> int | None:
    match = re.match(r"(\d+)", version)
    return int(match.group(1)) if match else None


def _select_adapter(version: str) -> SourceAdapter:
    major = _declared_major(version)
    return _V8_ADAPTER if major is None else _ADAPTERS.get(major, _V8_ADAPTER)


def _run_adapter(
    adapter: SourceAdapter,
    records: Iterable[object],
    source: SourceFile,
    warning_threshold: int,
    identities: dict[tuple[str, str, int, int], SourceFile],
) -> Iterator[ProtoclusterSearchDocument]:
    try:
        yield from adapter.extract(records, source, warning_threshold, identities)
    except ExtractionError as error:
        raise ExtractionError(
            f"{source.source_path} (antiSMASH {source.antismash_version}) is "
            f"incompatible with {adapter.name}: {error}"
        ) from error


def _iter_records(value: object) -> Iterator[object]:
    yield from _items(value, "records")


_MISSING = object()


def _read_file_metadata(source_path: Path) -> tuple[str, str]:
    version: object = _MISSING
    input_file: object = _MISSING
    with source_path.open("rb") as handle:
        for prefix, _event, value in ijson.parse(handle):
            if prefix == "version" and version is _MISSING:
                version = value
            elif prefix == "input_file" and input_file is _MISSING:
                input_file = value
            elif prefix == "records" and version is not _MISSING:
                break
    text_version = _text(None if version is _MISSING else version, "version")
    text_input = input_file.strip() if isinstance(input_file, str) else ""
    return text_version, text_input


def extract(
    data: object,
    source_path: str,
    *,
    warning_threshold: int = 100,
) -> Iterator[ProtoclusterSearchDocument]:
    """Extract search documents from decoded antiSMASH JSON data."""
    if warning_threshold < 1:
        raise ValueError("warning_threshold must be at least 1")
    obj = _mapping(data, source_path)
    version = _text(obj.get("version"), "version")
    adapter = _select_adapter(version)
    input_file_value = obj.get("input_file", "")
    input_file = input_file_value.strip() if isinstance(input_file_value, str) else ""
    source = SourceFile(version, source_path, Path(source_path).name, input_file)
    yield from _run_adapter(
        adapter, _iter_records(obj.get("records")), source, warning_threshold, {}
    )


def extract_documents(
    files: Iterable[Path],
    source_root: Path,
    *,
    warning_threshold: int = 100,
) -> Iterator[ProtoclusterSearchDocument]:
    if warning_threshold < 1:
        raise ValueError("warning_threshold must be at least 1")
    root = source_root.resolve()
    identities: dict[tuple[str, str, int, int], SourceFile] = {}
    for selected_path in files:
        source_path = (root / selected_path).resolve()
        try:
            relative_path = source_path.relative_to(root).as_posix()
        except ValueError as error:
            raise ExtractionError(
                f"Selected path is outside source root: {selected_path}"
            ) from error

        version, input_file = _read_file_metadata(source_path)
        adapter = _select_adapter(version)
        source = SourceFile(
            version, relative_path, Path(relative_path).name, input_file
        )
        with source_path.open("rb") as handle:
            records = ijson.items(handle, "records.item")
            yield from _run_adapter(
                adapter, records, source, warning_threshold, identities
            )
