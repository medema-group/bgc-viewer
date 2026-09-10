import json
import re
import warnings
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class _Feature:
    feature_type: str
    location: Location
    qualifiers: Mapping[str, object]
    json_path: str


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
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


def _required_value(
    qualifiers: Mapping[str, object], name: str, path: str
) -> str:
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
    location = Location.parse(
        _text(feature.get("location"), f"{path}.location")
    )
    qualifiers = _mapping(
        feature.get("qualifiers", {}), f"{path}.qualifiers"
    )
    return _Feature(feature_type, location, qualifiers, path)


def _normalize_pfam(accession: str) -> str:
    match = re.fullmatch(r"(PF\d{5})\.\d+", accession)
    return match.group(1) if match else accession


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
        warning_counts: dict[str, int] = {}
        source_path = (root / selected_path).resolve()
        try:
            relative_path = source_path.relative_to(root).as_posix()
        except ValueError as error:
            raise ExtractionError(
                f"Selected path is outside source root: {selected_path}"
            ) from error

        with source_path.open(encoding="utf-8") as handle:
            raw_data: object = json.load(handle)
        data = _mapping(raw_data, relative_path)
        version = _text(data.get("version"), "version")
        input_file_value = data.get("input_file", "")
        if isinstance(input_file_value, str):
            input_file = input_file_value.strip()
        else:
            input_file = ""
        source = SourceFile(
            version, relative_path, source_path.name, input_file
        )
        found_protocluster = False

        for record_index, raw_record in enumerate(
            _items(data.get("records"), "records")
        ):
            record_path = f"records[{record_index}]"
            record = _mapping(raw_record, record_path)
            record_id = _text(record.get("id"), f"{record_path}.id")
            features: list[_Feature] = []
            raw_features = _items(
                record.get("features"), f"{record_path}.features"
            )
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
                            source_path=relative_path,
                            record_id=record_id,
                            json_path=feature_path,
                            message=(
                                "Skipping malformed optional feature: "
                                f"{error}"
                            ),
                        ),
                        warning_counts,
                        warning_threshold,
                    )
            source_features = [
                feature
                for feature in features
                if feature.feature_type == "source"
            ]
            organism_values = (
                _values(source_features[0].qualifiers, "organism")
                if source_features
                else ()
            )
            regions = [
                feature
                for feature in features
                if feature.feature_type == "region"
            ]
            annotations = [
                feature
                for feature in features
                if feature.feature_type in {"gene", "PFAM_domain"}
            ]

            for protocluster in (
                feature
                for feature in features
                if feature.feature_type == "protocluster"
            ):
                found_protocluster = True
                parents = [
                    region
                    for region in regions
                    if region.location.contains(protocluster.location)
                ]
                if not parents:
                    raise ExtractionError(
                        "No containing region for protocluster in "
                        f"{record_path}"
                    )
                if len(parents) > 1:
                    _emit_warning(
                        ExtractionWarning(
                            code="multiple_parent_regions",
                            source_path=relative_path,
                            record_id=record_id,
                            json_path=protocluster.json_path,
                            message=(
                                f"Protocluster has {len(parents)} containing "
                                "regions; "
                                "selecting deterministically"
                            ),
                        ),
                        warning_counts,
                        warning_threshold,
                    )
                parent = min(
                    parents,
                    key=lambda region: (
                        sum(
                            part.end - part.start
                            for part in region.location.parts
                        ),
                        _number(
                            region.qualifiers,
                            "region_number",
                            record_path,
                        ),
                        region.location.serialized,
                    ),
                )

                genes: list[str] = []
                loci: list[str] = []
                pfams: list[str] = []
                pfam_names: list[str] = []
                for annotation in annotations:
                    if not protocluster.location.overlaps(
                        annotation.location
                    ):
                        continue
                    if annotation.feature_type == "gene":
                        genes.extend(_values(annotation.qualifiers, "gene"))
                        loci.extend(
                            _values(annotation.qualifiers, "locus_tag")
                        )
                    else:
                        accessions = _values(annotation.qualifiers, "db_xref")
                        if accessions:
                            pfams.extend(
                                _normalize_pfam(value)
                                for value in accessions
                            )
                            pfam_names.extend(
                                _values(annotation.qualifiers, "description")
                            )

                category = _values(
                    protocluster.qualifiers, "product_category"
                ) or _values(
                    protocluster.qualifiers, "category"
                )
                if not category:
                    raise ExtractionError(
                        "Missing protocluster product category in "
                        f"{record_path}"
                    )
                region_number = _number(
                    parent.qualifiers, "region_number", record_path
                )
                protocluster_number = _number(
                    protocluster.qualifiers,
                    "protocluster_number",
                    record_path,
                )
                identity = (
                    input_file,
                    record_id,
                    region_number,
                    protocluster_number,
                )
                previous_source = identities.get(identity)
                if previous_source is not None:
                    identity_text = ":".join(
                        (
                            input_file,
                            record_id,
                            str(region_number),
                            str(protocluster_number),
                        )
                    )
                    raise ExtractionError(
                        f"Duplicate biological identity {identity_text}: "
                        f"{previous_source.source_path} "
                        f"(antiSMASH {previous_source.antismash_version}) and "
                        f"{relative_path} (antiSMASH {version})"
                    )
                identities[identity] = source
                yield ProtoclusterSearchDocument(
                    source=source,
                    search_fields=SearchFields(
                        record_id=record_id,
                        region_number=region_number,
                        protocluster_number=protocluster_number,
                        location=protocluster.location,
                        product=_required_value(
                            protocluster.qualifiers, "product", record_path
                        ),
                        category=category[0],
                        organism=organism_values[0] if organism_values else "",
                        pfam=tuple(dict.fromkeys(pfams)),
                        pfam_name=tuple(dict.fromkeys(pfam_names)),
                        gene=tuple(dict.fromkeys(genes)),
                        locus=tuple(dict.fromkeys(loci)),
                    ),
                )

        if not found_protocluster:
            _emit_warning(
                ExtractionWarning(
                    code="no_protoclusters",
                    source_path=relative_path,
                    record_id="",
                    json_path="records",
                    message="Selected file contains no protoclusters",
                ),
                warning_counts,
                warning_threshold,
            )
