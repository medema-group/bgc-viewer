import json
from pathlib import Path

import pytest
from bgc_viewer.search.document import Location, LocationPart, SourceFile
from bgc_viewer.search.extraction import (
    ExtractionError,
    ExtractionWarning,
    extract,
    extract_documents,
)


def _values(document, name):
    return document.to_dict().get(name, [])


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

    [document] = extract_documents([Path("nested/sample.json")], tmp_path)

    assert document.to_dict() == {
        "record": ["record-1"],
        "region": [2],
        "protocluster": [3],
        "start": [200],
        "end": [700],
        "product": ["NRPS"],
        "category": ["NRPS"],
        "organism": ["Example organism"],
        "pfam": ["PF00512"],
        "pfam_name": ["His Kinase"],
        "gene": ["geneA"],
        "locus": ["LOC_1"],
        "output_file": ["nested/sample.json"],
        "input_file": ["sample.gbk"],
    }


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

    assert document.to_dict()["record"] == ["record-1"]
    assert document.to_dict()["input_file"] == ["sample.gbk"]


def test_extracts_regardless_of_declared_version():
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

    assert document.to_dict()["protocluster"] == [1]
    # An empty input_file is not indexed.
    assert "input_file" not in document.to_dict()


def test_error_identifies_source_file_and_version():
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
    assert _values(document, "region") == [1]
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
    assert "gene" not in document.to_dict()
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
    assert _values(document, "pfam") == ["PF00512"]
    assert _values(document, "pfam_name") == ["His Kinase"]
    assert "Orphan description" not in _values(document, "pfam_name")
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

    assert _values(document, "gene") == ["real_gene"]
    assert _values(document, "locus") == ["REAL_1"]
    assert _values(document, "pfam") == ["PF00512"]
    assert _values(document, "pfam_name") == ["Real Pfam"]
    assert "cds_gene" not in _values(document, "gene")
    assert "CDS_IGNORABLE" not in _values(document, "locus")
    assert "PF99999" not in _values(document, "pfam")
    assert "CDS decoy" not in _values(document, "pfam_name")
