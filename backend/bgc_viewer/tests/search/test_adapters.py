import dataclasses
import json
import warnings
from pathlib import Path

import pytest
from bgc_viewer.search.document import (
    Location,
    ProtoclusterSearchDocument,
    SearchFields,
    SourceFile,
)
from bgc_viewer.search.extraction import (
    ExtractionError,
    ExtractionWarning,
    extract,
)

FIXTURES = Path(__file__).parent / "fixtures"

EQUIVALENT = {
    "7.0.1": FIXTURES / "antismash7" / "equivalent.json",
    "8.0.2": FIXTURES / "antismash8" / "equivalent.json",
    "9.0.0": FIXTURES / "antismash9" / "equivalent.json",
}


def _load(path: Path, source_path: str) -> list[ProtoclusterSearchDocument]:
    data = json.loads(path.read_text())
    return list(extract(data, source_path))


def _equivalent_document(
    version: str,
    protocluster_number: int,
    location: str,
    product: str,
    category: str,
    pfam: tuple[str, ...],
    pfam_name: tuple[str, ...],
    gene: tuple[str, ...],
    locus: tuple[str, ...],
) -> ProtoclusterSearchDocument:
    return ProtoclusterSearchDocument(
        source=SourceFile(
            antismash_version=version,
            source_path="equivalent.json",
            output_file="equivalent.json",
            input_file="equivalent.gbk",
        ),
        search_fields=SearchFields(
            record_id="equivalent_record",
            region_number=1,
            protocluster_number=protocluster_number,
            location=Location.parse(location),
            product=product,
            category=category,
            organism="Equivalens modestus",
            pfam=pfam,
            pfam_name=pfam_name,
            gene=gene,
            locus=locus,
        ),
    )


def _expected_equivalent(version: str) -> list[ProtoclusterSearchDocument]:
    return [
        _equivalent_document(
            version,
            protocluster_number=1,
            location="[200:1000](+)",
            product="NRPS",
            category="NRPS",
            pfam=("PF00501",),
            pfam_name=("Thioesterase",),
            gene=("eqsA",),
            locus=("EQ_0001",),
        ),
        _equivalent_document(
            version,
            protocluster_number=2,
            location="[1100:1900](+)",
            product="T3PKS",
            category="PKS",
            pfam=(),
            pfam_name=(),
            gene=(),
            locus=(),
        ),
    ]


@pytest.mark.parametrize("version", sorted(EQUIVALENT))
def test_shared_contract_emits_expected_canonical_documents(version):
    documents = _load(EQUIVALENT[version], "equivalent.json")
    assert documents == _expected_equivalent(version)


@pytest.mark.parametrize("version", sorted(EQUIVALENT))
def test_equivalent_fixtures_match_across_versions_modulo_declared_version(version):
    baseline = _expected_equivalent("8.0.2")
    documents = _load(EQUIVALENT[version], "equivalent.json")

    assert [document.source.antismash_version for document in documents] == [
        version,
        version,
    ]
    normalized = [
        dataclasses.replace(
            document,
            source=dataclasses.replace(document.source, antismash_version="8.0.2"),
        )
        for document in documents
    ]
    assert normalized == baseline


@pytest.mark.parametrize("version", ["7.0.1", "9.0.0"])
def test_compatible_unknown_versions_extract_through_v8_path(version):
    documents = _load(EQUIVALENT[version], "equivalent.json")
    assert len(documents) == 2
    assert all(document.source.antismash_version == version for document in documents)


def test_shared_contract_ignores_cds_and_non_overlapping_pfam():
    documents = _load(EQUIVALENT["8.0.2"], "equivalent.json")
    fields = documents[0].search_fields
    assert fields.pfam == ("PF00501",)
    assert "PF12345" not in fields.pfam
    assert "PF99999" not in fields.pfam
    assert fields.gene == ("eqsA",)
    assert "ignored_cds" not in fields.gene


def test_additional_8x_fixture_multiple_records_regions_and_circular_locations():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        documents = _load(FIXTURES / "antismash8" / "multi.json", "multi.json")

    codes = [
        warning.message.code
        for warning in caught
        if isinstance(warning.message, ExtractionWarning)
    ]
    assert "multiple_parent_regions" in codes
    assert [document.document_key for document in documents] == [
        "multi.json:recA:1:1",
        "multi.json:recB:1:1",
    ]

    record_a, record_b = documents
    assert record_a.search_fields.region_number == 1
    assert record_a.search_fields.pfam == ("PF00668",)
    assert record_a.search_fields.category == "trans-AT PKS"

    assert record_b.search_fields.location.serialized == (
        "join{[<200:300](+), [3500:>3800](+)}"
    )
    assert (record_b.search_fields.start, record_b.search_fields.end) == (200, 3800)
    assert record_b.search_fields.gene == ("sunA",)
    assert record_b.search_fields.pfam == ("PF04818",)


def test_incompatible_7x_structure_reports_adapter_and_source():
    source = {"version": "7.1.0", "records": {"not": "a list"}}

    with pytest.raises(ExtractionError) as caught:
        list(extract(source, "memory/sample.json"))

    message = str(caught.value)
    assert "memory/sample.json (antiSMASH 7.1.0)" in message
    assert "Antismash8Adapter" in message
    assert "records" in message


def test_structured_warnings_carry_source_record_and_json_path():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _load(FIXTURES / "antismash8" / "multi.json", "multi.json")

    warning = next(
        entry.message
        for entry in caught
        if getattr(entry.message, "code", None) == "multiple_parent_regions"
    )
    assert isinstance(warning, ExtractionWarning)
    assert warning.source_path == "multi.json"
    assert warning.record_id == "recA"
    assert warning.json_path == "records[0].features[3]"
