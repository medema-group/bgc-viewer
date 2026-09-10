import json
from pathlib import Path

import pytest
from bgc_viewer.search import (
    SEARCH_FIELD_REGISTRY,
    SEARCH_SCHEMA_VERSION,
    Location,
    ProtoclusterSearchDocument,
    SearchFields,
    SourceFile,
    build_index,
    extract_documents,
)
from tantivy import Index

BY_NAME = {definition.name: definition for definition in SEARCH_FIELD_REGISTRY}
FIXTURES = Path(__file__).parent / "fixtures"


def _doc(
    protocluster_number: int,
    *,
    record_id: str = "recA",
    region_number: int = 1,
    location: str = "[100:500](+)",
    product: str = "NRP",
    category: str = "NRPS",
    organism: str = "His Kinase Amycolatopsis",
    pfam: tuple[str, ...] = (),
    pfam_name: tuple[str, ...] = (),
    gene: tuple[str, ...] = (),
    locus: tuple[str, ...] = (),
    input_file: str = "rec.gbk",
) -> ProtoclusterSearchDocument:
    return ProtoclusterSearchDocument(
        source=SourceFile("8.0.2", "rec.json", "rec.json", input_file),
        search_fields=SearchFields(
            record_id=record_id,
            region_number=region_number,
            protocluster_number=protocluster_number,
            location=Location.parse(location),
            product=product,
            category=category,
            organism=organism,
            pfam=pfam,
            pfam_name=pfam_name,
            gene=gene,
            locus=locus,
        ),
    )


@pytest.fixture
def corpus() -> list[ProtoclusterSearchDocument]:
    return [
        _doc(
            1,
            pfam=("PF00512", "PF00513"),
            pfam_name=("His Kinase",),
            gene=("spaA", "spaB"),
            locus=("SPAU_1",),
        ),
        _doc(
            2,
            location="[600:900](+)",
            product="T1PKS",
            category="PKS",
            organism="Streptomyces coelicolor",
            pfam=("PF00999",),
            pfam_name=("Thioesterase",),
            input_file="",
        ),
    ]


@pytest.fixture
def built(corpus):
    index = build_index(iter(corpus))
    return index, index.searcher()


@pytest.fixture
def pfam_summary(built):
    index, searcher = built
    return _stored_hit(searcher, index, "pfam:PF00512")


def _hits(searcher, index, query: str) -> int:
    return len(searcher.search(index.parse_query(query), limit=100).hits)


def _stored_hit(searcher, index, query: str) -> dict:
    address = searcher.search(index.parse_query(query), limit=1).hits[0][1]
    return searcher.doc(address).to_dict()


def _empty_schema_dir(tmp_path) -> dict[str, dict]:
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(()), index_dir)
    meta = json.loads((index_dir / "meta.json").read_text(encoding="utf-8"))
    return {field["name"]: field for field in meta["schema"]}


def _assert_field_spec(field_spec: dict, expected: dict) -> None:
    assert field_spec["type"] == expected["type"]
    assert field_spec["options"]["stored"] is expected["stored"]
    for key, value in expected.get("indexing", {}).items():
        assert field_spec["options"]["indexing"][key] == value


def test_schema_is_derived_from_registry_not_hardcoded(tmp_path):
    schema_dir = _empty_schema_dir(tmp_path)
    assert set(schema_dir) == set(BY_NAME)


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("pfam", {"type": "text", "stored": False, "indexing": {"tokenizer": "raw"}}),
        (
            "organism",
            {
                "type": "text",
                "stored": True,
                "indexing": {"tokenizer": "default", "record": "position"},
            },
        ),
        ("region", {"type": "i64", "stored": True}),
        ("start", {"type": "i64", "stored": True}),
    ],
)
def test_schema_field_options(tmp_path, field, expected):
    _assert_field_spec(_empty_schema_dir(tmp_path)[field], expected)


def test_build_index_indexes_every_document(built, corpus):
    _, searcher = built
    assert searcher.num_docs == len(corpus)


def test_build_index_accepts_a_generator(corpus):
    def streaming():
        yield from corpus

    assert build_index(streaming()).searcher().num_docs == len(corpus)


def test_build_index_persists_search_schema_version(corpus, tmp_path):
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(corpus), index_dir)
    payload = json.loads((index_dir / "meta.json").read_text())["payload"]
    assert json.loads(payload) == {"search_schema_version": SEARCH_SCHEMA_VERSION}


@pytest.mark.parametrize(
    ("query", "expected_hits"),
    [
        ("pfam:PF00512", 1),
        ("pfam:pf00512", 0),
        ('product:"T1PKS"', 1),
        ('product:"t1pks"', 0),
    ],
)
def test_exact_fields_are_case_sensitive(built, query, expected_hits):
    index, searcher = built
    assert _hits(searcher, index, query) == expected_hits


@pytest.mark.parametrize(
    ("query", "expected_hits"),
    [
        ("organism:amycolatopsis", 1),
        ("organism:Amycolatopsis", 1),
        ('organism:"His Kinase"', 1),
        ('organism:"Kinase His"', 0),
    ],
)
def test_full_text_fields_are_lowercased_and_phrasable(built, query, expected_hits):
    index, searcher = built
    assert _hits(searcher, index, query) == expected_hits


@pytest.mark.parametrize(
    ("query", "expected_hits"),
    [
        ("pfam:PF00512 AND pfam:PF00513", 1),
        ("gene:spaA AND gene:spaB", 1),
        ("pfam:PF00512 AND pfam:PF00999", 0),
    ],
)
def test_multi_valued_exact_fields_combine_within_one_document(
    built, query, expected_hits
):
    index, searcher = built
    assert _hits(searcher, index, query) == expected_hits


@pytest.mark.parametrize(
    ("query", "expected_hits"),
    [
        ("start:[100 TO 500]", 1),
        ("end:[800 TO 1000]", 1),
        ("region:[1 TO 1]", 2),
    ],
)
def test_numeric_fields_are_range_queryable(built, query, expected_hits):
    index, searcher = built
    assert _hits(searcher, index, query) == expected_hits


def test_numeric_fields_are_stored(built):
    index, searcher = built
    stored = _stored_hit(searcher, index, "organism:coelicolor")
    assert stored["start"] == [600]
    assert stored["end"] == [900]
    assert stored["region"] == [1]
    assert stored["protocluster"] == [2]


def test_stored_summary_includes_display_fields(pfam_summary):
    assert pfam_summary["product"] == ["NRP"]
    assert pfam_summary["category"] == ["NRPS"]
    assert pfam_summary["record"] == ["recA"]


@pytest.mark.parametrize("field", ["pfam", "pfam_name", "gene", "locus"])
def test_indexed_only_fields_are_not_stored(pfam_summary, field):
    assert field not in pfam_summary


def test_empty_optional_single_field_is_not_indexed(built):
    index, searcher = built
    assert _hits(searcher, index, 'input_file:"rec.gbk"') == 1
    assert "input_file" not in _stored_hit(searcher, index, "organism:coelicolor")


def test_build_commit_close_and_reopen(corpus, tmp_path):
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(corpus), index_dir)
    assert Index.open(str(index_dir)).searcher().num_docs == len(corpus)

    reopened = Index.open(str(index_dir))
    reopened.reload()
    assert reopened.searcher().num_docs == len(corpus)


def test_generated_index_is_inspectable_with_standard_tooling(corpus, tmp_path):
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(corpus), index_dir)
    assert Index.exists(str(index_dir)) is True
    assert (index_dir / "meta.json").is_file()

    reopened = Index.open(str(index_dir))
    searcher = reopened.searcher()
    assert searcher.num_docs == len(corpus)
    stored = _stored_hit(searcher, reopened, "organism:streptomyces")
    assert stored["organism"] == ["Streptomyces coelicolor"]


def test_build_from_extracted_fixture():
    documents = list(extract_documents([Path("multi.json")], FIXTURES / "antismash8"))
    index = build_index(iter(documents))
    searcher = index.searcher()
    assert searcher.num_docs == len(documents)
    assert _hits(searcher, index, 'category:"trans-AT PKS"') == 1
