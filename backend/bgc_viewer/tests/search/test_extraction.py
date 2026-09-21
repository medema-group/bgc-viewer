import json
from pathlib import Path

import pytest
from bgc_viewer.search.document import (
    SEARCH_FIELD_REGISTRY,
    SEARCH_SCHEMA_VERSION,
    Location,
    LocationPart,
    ProtoclusterSearchDocument,
    SearchFields,
    SourceFile,
)
from bgc_viewer.search.extraction import (
    ExtractionError,
    ExtractionWarning,
    extract,
    extract_documents,
)


def test_search_fields_expose_the_versioned_public_registry():
    assert SEARCH_SCHEMA_VERSION == 4
    assert [field.name for field in SEARCH_FIELD_REGISTRY] == [
        "pfam",
        "pfam_name",
        "organism",
        "gene",
        "locus",
        "product",
        "category",
        "record",
        "region",
        "protocluster",
        "start",
        "end",
        "output_file",
        "input_file",
    ]
    assert len({field.name for field in SEARCH_FIELD_REGISTRY}) == len(
        SEARCH_FIELD_REGISTRY
    )


def test_extracts_canonical_protocluster_document(tmp_path):
    source = {
        "version": "8.0.2",
        "input_file": "sample.gbk",
        "records": [
            {
                "id": "record-1",
                "features": [
                    {
                        "type": "source",
                        "location": "[0:1000](+)",
                        "qualifiers": {"organism": [" Example organism "]},
                    },
                    {
                        "type": "region",
                        "location": "[100:900](+)",
                        "qualifiers": {"region_number": ["2"]},
                    },
                    {
                        "type": "protocluster",
                        "location": "[200:700](+)",
                        "qualifiers": {
                            "protocluster_number": ["3"],
                            "product": ["NRPS"],
                            "category": ["NRPS"],
                        },
                    },
                    {
                        "type": "gene",
                        "location": "[250:400](+)",
                        "qualifiers": {
                            "gene": [" geneA ", "geneA"],
                            "locus_tag": ["LOC_1"],
                        },
                    },
                    {
                        "type": "PFAM_domain",
                        "location": "[650:750](+)",
                        "qualifiers": {
                            "db_xref": ["PF00512.28"],
                            "description": ["His Kinase"],
                        },
                    },
                    {
                        "type": "gene",
                        "location": "[700:800](+)",
                        "qualifiers": {"gene": ["touches-boundary"]},
                    },
                ],
            }
        ],
    }
    source_file = tmp_path / "nested" / "sample.json"
    source_file.parent.mkdir()
    source_file.write_text(json.dumps(source))

    expected: list[ProtoclusterSearchDocument] = [
        ProtoclusterSearchDocument(
            # document_key derives from its source and biological identity
            source=SourceFile(
                antismash_version="8.0.2",
                # JSON file specific props
                output_file="nested/sample.json",
                input_file="sample.gbk",
            ),
            search_fields=SearchFields(
                # record specific props
                record_id="record-1",
                # region specific props
                region_number=2,
                # protocluster specific props
                protocluster_number=3,
                location=Location.parse("[200:700](+)"),
                product="NRPS",
                category="NRPS",
                # overlapping searchable features
                organism="Example organism",
                pfam=("PF00512",),
                pfam_name=("His Kinase",),
                gene=("geneA",),
                locus=("LOC_1",),
            ),
        )
    ]

    documents = extract_documents([Path("nested/sample.json")], tmp_path)
    assert list(documents) == expected


def test_extracts_from_data_without_reading_a_file():
    source = {
        "version": "8.0.2",
        "input_file": "sample.gbk",
        "records": [
            {
                "id": "record-1",
                "features": [
                    {
                        "type": "region",
                        "location": "[0:500](+)",
                        "qualifiers": {"region_number": ["1"]},
                    },
                    {
                        "type": "protocluster",
                        "location": "[100:400](+)",
                        "qualifiers": {
                            "protocluster_number": ["1"],
                            "product": ["NRPS"],
                            "product_category": ["NRPS"],
                        },
                    },
                ],
            }
        ],
    }

    source_file = SourceFile(
        antismash_version=source["version"],
        output_file="memory/sample.json",
        input_file=source["input_file"],
    )
    [document] = extract(source["records"], source_file)

    assert document.source == SourceFile(
        antismash_version="8.0.2",
        output_file="memory/sample.json",
        input_file="sample.gbk",
    )
    assert document.search_fields.record_id == "record-1"


def test_compatible_unknown_major_version_uses_v8_adapter():
    source = {
        "version": "9.0.0",
        "records": [
            {
                "id": "record-1",
                "features": [
                    {
                        "type": "region",
                        "location": "[0:500](+)",
                        "qualifiers": {"region_number": ["1"]},
                    },
                    {
                        "type": "protocluster",
                        "location": "[100:400](+)",
                        "qualifiers": {
                            "protocluster_number": ["1"],
                            "product": ["NRPS"],
                            "product_category": ["NRPS"],
                        },
                    },
                ],
            }
        ],
    }

    source_file = SourceFile(
        antismash_version=source["version"],
        output_file="memory/sample.json",
        input_file="",
    )
    [document] = extract(source["records"], source_file)

    assert document.source.antismash_version == "9.0.0"


def test_incompatible_version_error_identifies_adapter_and_source():
    source = {"version": "7.1.0", "records": "incompatible"}

    source_file = SourceFile(
        antismash_version=source["version"],
        output_file="memory/sample.json",
        input_file="",
    )
    with pytest.raises(ExtractionError) as caught:
        list(extract(source["records"], source_file))

    message = str(caught.value)
    assert "memory/sample.json (antiSMASH 7.1.0)" in message
    assert "Antismash8Adapter" in message
    assert "records" in message


def test_selects_smallest_parent_region_and_warns_for_multiple_matches(
    tmp_path,
):
    source = {
        "version": "8.0.2",
        "records": [
            {
                "id": "record-1",
                "features": [
                    {
                        "type": "region",
                        "location": "[0:500](+)",
                        "qualifiers": {"region_number": ["9"]},
                    },
                    {
                        "type": "region",
                        "location": "[100:400](+)",
                        "qualifiers": {"region_number": ["2"]},
                    },
                    {
                        "type": "region",
                        "location": "[100:400](-)",
                        "qualifiers": {"region_number": ["1"]},
                    },
                    {
                        "type": "protocluster",
                        "location": "[150:350](+)",
                        "qualifiers": {
                            "protocluster_number": ["4"],
                            "product": ["PKS"],
                            "product_category": ["PKS"],
                        },
                    },
                ],
            }
        ],
    }
    (tmp_path / "sample.json").write_text(json.dumps(source))

    with pytest.warns(ExtractionWarning) as caught:
        document = next(extract_documents([Path("sample.json")], tmp_path))

    warning = caught[0].message
    assert isinstance(warning, ExtractionWarning)
    assert document.search_fields.region_number == 1
    assert warning.code == "multiple_parent_regions"
    assert warning.source_path == "sample.json"
    assert warning.record_id == "record-1"
    assert warning.json_path == "records[0].features[3]"


def test_skips_malformed_optional_features_with_structured_warning(tmp_path):
    source = {
        "version": "8.0.2",
        "records": [
            {
                "id": "record-1",
                "features": [
                    {
                        "type": "region",
                        "location": "[0:500](+)",
                        "qualifiers": {"region_number": ["1"]},
                    },
                    {
                        "type": "protocluster",
                        "location": "[100:400](+)",
                        "qualifiers": {
                            "protocluster_number": ["1"],
                            "product": ["NRPS"],
                            "product_category": ["NRPS"],
                        },
                    },
                    {
                        "type": "gene",
                        "location": "invalid",
                        "qualifiers": {"gene": ["ignored"]},
                    },
                ],
            }
        ],
    }
    (tmp_path / "sample.json").write_text(json.dumps(source))

    with pytest.warns(ExtractionWarning) as caught:
        document = next(extract_documents([Path("sample.json")], tmp_path))

    warning = caught[0].message
    assert isinstance(warning, ExtractionWarning)
    assert document.search_fields.gene == ()
    assert warning.code == "malformed_optional_feature"
    assert warning.json_path == "records[0].features[2]"


def test_stops_at_configured_warning_threshold_per_file_and_code(tmp_path):
    source = {
        "version": "8.0.2",
        "records": [
            {
                "id": "record-1",
                "features": [
                    {
                        "type": "region",
                        "location": "[0:500](+)",
                        "qualifiers": {"region_number": ["1"]},
                    },
                    {
                        "type": "protocluster",
                        "location": "[100:400](+)",
                        "qualifiers": {
                            "protocluster_number": ["1"],
                            "product": ["NRPS"],
                            "product_category": ["NRPS"],
                        },
                    },
                    {"type": "gene", "location": "invalid", "qualifiers": {}},
                    {"type": "gene", "location": None, "qualifiers": {}},
                ],
            }
        ],
    }
    (tmp_path / "sample.json").write_text(json.dumps(source))

    with (
        pytest.warns(ExtractionWarning, match="optional feature"),
        pytest.raises(
            ExtractionError,
            match="warning threshold.*malformed_optional_feature",
        ),
    ):
        list(
            extract_documents(
                [Path("sample.json")],
                tmp_path,
                warning_threshold=2,
            )
        )


def test_warns_and_yields_nothing_when_file_has_no_protoclusters(tmp_path):
    source = {
        "version": "8.0.2",
        "records": [{"id": "record-1", "features": []}],
    }
    (tmp_path / "sample.json").write_text(json.dumps(source))

    with pytest.warns(ExtractionWarning) as caught:
        documents = list(extract_documents([Path("sample.json")], tmp_path))

    warning = caught[0].message
    assert isinstance(warning, ExtractionWarning)
    assert documents == []
    assert warning.code == "no_protoclusters"
    assert warning.source_path == "sample.json"


def test_rejects_duplicate_biological_identity_across_source_files(tmp_path):
    def source(version):
        return {
            "version": version,
            "input_file": "same.gbk",
            "records": [
                {
                    "id": "record-1",
                    "features": [
                        {
                            "type": "region",
                            "location": "[0:500](+)",
                            "qualifiers": {"region_number": ["1"]},
                        },
                        {
                            "type": "protocluster",
                            "location": "[100:400](+)",
                            "qualifiers": {
                                "protocluster_number": ["1"],
                                "product": ["NRPS"],
                                "product_category": ["NRPS"],
                            },
                        },
                    ],
                }
            ],
        }

    (tmp_path / "first.json").write_text(json.dumps(source("8.0.1")))
    (tmp_path / "second.json").write_text(json.dumps(source("9.0.0")))

    with pytest.raises(ExtractionError) as caught:
        list(extract_documents([Path("first.json"), Path("second.json")], tmp_path))

    message = str(caught.value)
    assert "same.gbk:record-1:1:1" in message
    assert "first.json (antiSMASH 8.0.1)" in message
    assert "second.json (antiSMASH 9.0.0)" in message


def test_location_parses_antismash_fuzzy_and_compound_syntax():
    location = Location.parse("join{[<900:1000](+), [0:>200](+)}")

    assert location.parts == (LocationPart(900, 1000), LocationPart(0, 200))
    assert location.start == 0
    assert location.end == 1000

    with pytest.raises(ValueError, match="Invalid antiSMASH location"):
        Location.parse("prefix [1:2](+) suffix")


def test_warns_when_pfam_annotation_has_no_usable_accession(tmp_path):
    source = {
        "version": "8.0.2",
        "records": [
            {
                "id": "record-1",
                "features": [
                    {
                        "type": "region",
                        "location": "[0:1000](+)",
                        "qualifiers": {"region_number": ["1"]},
                    },
                    {
                        "type": "protocluster",
                        "location": "[100:900](+)",
                        "qualifiers": {
                            "protocluster_number": ["1"],
                            "product": ["NRPS"],
                            "product_category": ["NRPS"],
                        },
                    },
                    {
                        "type": "PFAM_domain",
                        "location": "[200:300](+)",
                        "qualifiers": {
                            "db_xref": ["PF00512.28"],
                            "description": ["His Kinase"],
                        },
                    },
                    {
                        "type": "PFAM_domain",
                        "location": "[400:500](+)",
                        "qualifiers": {
                            "db_xref": [""],
                            "description": ["Orphan description"],
                        },
                    },
                ],
            }
        ],
    }
    (tmp_path / "sample.json").write_text(json.dumps(source))

    with pytest.warns(ExtractionWarning) as caught:
        document = next(extract_documents([Path("sample.json")], tmp_path))

    warning = caught[0].message
    assert isinstance(warning, ExtractionWarning)
    assert document.search_fields.pfam == ("PF00512",)
    assert document.search_fields.pfam_name == ("His Kinase",)
    assert "Orphan description" not in document.search_fields.pfam_name
    assert warning.code == "missing_pfam_accession"
    assert warning.source_path == "sample.json"
    assert warning.record_id == "record-1"
    assert warning.json_path == "records[0].features[3]"


def test_pfam_missing_accession_is_subject_to_warning_threshold(tmp_path):
    source = {
        "version": "8.0.2",
        "records": [
            {
                "id": "record-1",
                "features": [
                    {
                        "type": "region",
                        "location": "[0:1000](+)",
                        "qualifiers": {"region_number": ["1"]},
                    },
                    {
                        "type": "protocluster",
                        "location": "[100:900](+)",
                        "qualifiers": {
                            "protocluster_number": ["1"],
                            "product": ["NRPS"],
                            "product_category": ["NRPS"],
                        },
                    },
                    {
                        "type": "PFAM_domain",
                        "location": "[200:300](+)",
                        "qualifiers": {"description": ["No accession"]},
                    },
                ],
            }
        ],
    }
    (tmp_path / "sample.json").write_text(json.dumps(source))

    with (
        pytest.warns(ExtractionWarning, match="usable accession"),
        pytest.raises(
            ExtractionError,
            match="warning threshold.*missing_pfam_accession",
        ),
    ):
        list(
            extract_documents(
                [Path("sample.json")],
                tmp_path,
                warning_threshold=1,
            )
        )


def test_cds_features_do_not_contribute_search_fields(tmp_path):
    source = {
        "version": "8.0.2",
        "records": [
            {
                "id": "record-1",
                "features": [
                    {
                        "type": "region",
                        "location": "[0:1000](+)",
                        "qualifiers": {"region_number": ["1"]},
                    },
                    {
                        "type": "protocluster",
                        "location": "[100:900](+)",
                        "qualifiers": {
                            "protocluster_number": ["1"],
                            "product": ["NRPS"],
                            "product_category": ["NRPS"],
                        },
                    },
                    {
                        "type": "gene",
                        "location": "[200:400](+)",
                        "qualifiers": {"gene": ["real_gene"], "locus_tag": ["REAL_1"]},
                    },
                    {
                        "type": "PFAM_domain",
                        "location": "[250:350](+)",
                        "qualifiers": {
                            "db_xref": ["PF00512.1"],
                            "description": ["Real Pfam"],
                        },
                    },
                    {
                        "type": "CDS",
                        "location": "[200:400](+)",
                        "qualifiers": {
                            "gene": ["cds_gene"],
                            "locus_tag": ["CDS_IGNORABLE"],
                            "db_xref": ["PF99999.1"],
                            "description": ["CDS decoy"],
                            "translation": ["MAQ"],
                        },
                    },
                ],
            }
        ],
    }
    (tmp_path / "sample.json").write_text(json.dumps(source))

    document = next(extract_documents([Path("sample.json")], tmp_path))
    fields = document.search_fields

    assert fields.gene == ("real_gene",)
    assert fields.locus == ("REAL_1",)
    assert fields.pfam == ("PF00512",)
    assert fields.pfam_name == ("Real Pfam",)
    assert "cds_gene" not in fields.gene
    assert "CDS_IGNORABLE" not in fields.locus
    assert "PF99999" not in fields.pfam
    assert "CDS decoy" not in fields.pfam_name
