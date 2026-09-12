import json
from pathlib import Path

import pytest
from bgc_viewer.search.document import (
    SEARCH_FIELD_REGISTRY,
    SEARCH_SCHEMA_VERSION,
    Location,
    ProtoclusterSearchDocument,
    SearchFields,
    SourceFile,
)
from bgc_viewer.search.extraction import extract_documents
from bgc_viewer.search.index import (
    EmptyQueryError,
    IndexCorruptError,
    IndexIncompatibleError,
    IndexNotFoundError,
    QuerySyntaxError,
    SearchIndex,
    UnknownFieldError,
    build_index,
    open_index,
    search_protoclusters,
    search_record,
    search_region,
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


def _open(corpus, tmp_path, name="tantivy.index") -> SearchIndex:
    index_dir = tmp_path / name
    build_index(iter(corpus), index_dir)
    return open_index(index_dir)


def test_open_index_reopens_a_committed_index(corpus, tmp_path):
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(corpus), index_dir)

    reopened = open_index(index_dir)
    result = search_protoclusters(reopened, "pfam:PF00512")
    assert result.total == 1


def test_open_index_missing_path_raises(tmp_path):
    with pytest.raises(IndexNotFoundError):
        open_index(tmp_path / "absent")


def test_open_index_empty_directory_raises(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(IndexNotFoundError):
        open_index(tmp_path / "empty")


def test_open_index_rejects_mismatched_schema_version(corpus, tmp_path):
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(corpus), index_dir)
    meta_path = index_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    payload = json.loads(meta["payload"])
    payload["search_schema_version"] = SEARCH_SCHEMA_VERSION + 1
    meta["payload"] = json.dumps(payload)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(IndexIncompatibleError):
        open_index(index_dir)


def test_open_index_rejects_incompatible_schema(tmp_path):
    from tantivy import Document, SchemaBuilder

    index_dir = tmp_path / "tantivy.index"
    index_dir.mkdir()
    builder = SchemaBuilder()
    builder.add_text_field("totally", tokenizer_name="raw")
    builder.add_text_field("different", tokenizer_name="raw")
    foreign = Index(builder.build(), path=str(index_dir))
    writer = foreign.writer(num_threads=1)
    document = Document()
    document.add_text("totally", "x")
    writer.add_document(document)
    writer.commit()
    meta_path = index_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["payload"] = json.dumps({"search_schema_version": SEARCH_SCHEMA_VERSION})
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(IndexIncompatibleError):
        open_index(index_dir)


def test_open_index_rejects_corrupt_index(corpus, tmp_path):
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(corpus), index_dir)
    (index_dir / "meta.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(IndexCorruptError):
        open_index(index_dir)


def test_search_returns_scores_and_stored_summary(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    result = search_protoclusters(target, "pfam:PF00512")

    assert result.total == 1
    hit = result.hits[0]
    assert hit.score > 0
    assert hit.fields["record"] == "recA"
    assert hit.fields["region"] == 1
    assert hit.fields["protocluster"] == 1
    assert hit.fields["start"] == 100
    assert hit.fields["end"] == 500
    assert hit.fields["product"] == "NRP"
    assert hit.fields["category"] == "NRPS"
    assert hit.fields["output_file"] == "rec.json"
    assert hit.fields["input_file"] == "rec.gbk"


def test_search_omits_indexed_only_fields(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    hit = search_protoclusters(target, "pfam:PF00512").hits[0]
    for field in ("pfam", "pfam_name", "gene", "locus"):
        assert field not in hit.fields


def test_search_omits_empty_optional_field(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    hit = search_protoclusters(target, "organism:coelicolor").hits[0]
    assert "input_file" not in hit.fields


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("pfam:PF00512", 1),
        ("pfam:pf00512", 0),
        ('product:"T1PKS"', 1),
        ('product:"t1pks"', 0),
    ],
)
def test_search_exact_fields_are_case_sensitive(corpus, tmp_path, query, expected):
    target = _open(corpus, tmp_path)
    assert search_protoclusters(target, query).total == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("organism:amycolatopsis", 1),
        ("organism:Amycolatopsis", 1),
        ('organism:"His Kinase"', 1),
        ('organism:"Kinase His"', 0),
    ],
)
def test_search_full_text_is_lowercased_and_phrasable(
    corpus, tmp_path, query, expected
):
    target = _open(corpus, tmp_path)
    assert search_protoclusters(target, query).total == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("pfam:PF00512 AND pfam:PF00513", 1),
        ("pfam:PF00512 AND pfam:PF00999", 0),
        ("pfam:PF00512 OR pfam:PF00999", 2),
        ("(pfam:PF00512 OR pfam:PF00999) AND organism:streptomyces", 1),
        ("organism:streptomyces NOT pfam:PF00999", 0),
        ("organism:amycolatopsis NOT pfam:PF00999", 1),
        ("gene:spaA AND gene:spaB", 1),
    ],
)
def test_search_boolean_precedence_and_nesting(corpus, tmp_path, query, expected):
    target = _open(corpus, tmp_path)
    assert search_protoclusters(target, query).total == expected


def test_search_unqualified_covers_default_fields(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    assert search_protoclusters(target, "spaA").total == 1
    assert search_protoclusters(target, "coelicolor").total == 1
    assert search_protoclusters(target, "SPAU_1").total == 1
    # Numeric navigation fields are excluded from unqualified search.
    assert search_protoclusters(target, "600").total == 0


@pytest.mark.parametrize(
    ("query", "expected"),
    [("start:[100 TO 500]", 1), ("end:[800 TO 1000]", 1), ("region:[1 TO 1]", 2)],
)
def test_search_numeric_range(corpus, tmp_path, query, expected):
    target = _open(corpus, tmp_path)
    assert search_protoclusters(target, query).total == expected


def test_search_pagination_and_total_counts(corpus, tmp_path):
    many = [
        _doc(number, pfam=("shared",), organism=f"organism {number}")
        for number in range(5)
    ]
    target = _open(many, tmp_path)

    page_one = search_protoclusters(target, "pfam:shared", offset=0, limit=2)
    assert page_one.total == 5
    assert [hit.fields["protocluster"] for hit in page_one.hits] == [0, 1]

    page_two = search_protoclusters(target, "pfam:shared", offset=3, limit=2)
    assert page_two.total == 5
    assert [hit.fields["protocluster"] for hit in page_two.hits] == [3, 4]

    beyond = search_protoclusters(target, "pfam:shared", offset=10, limit=2)
    assert beyond.total == 5
    assert beyond.hits == ()


def test_search_equal_scores_resolve_in_insertion_order(corpus, tmp_path):
    many = [_doc(number, pfam=("shared",)) for number in range(4)]
    target = _open(many, tmp_path)
    hits = search_protoclusters(target, "pfam:shared", limit=10).hits

    scores = [hit.score for hit in hits]
    assert scores == sorted(scores, reverse=True)
    assert len(set(scores)) == 1
    assert [hit.fields["protocluster"] for hit in hits] == [0, 1, 2, 3]


def test_search_boosts_exact_field_above_full_text(tmp_path):
    documents = [
        _doc(1, pfam=("shared",), organism="other organism"),
        _doc(2, pfam=("other",), organism="shared term"),
    ]
    target = _open(documents, tmp_path)
    hits = search_protoclusters(target, "shared", limit=10).hits

    assert hits[0].fields["protocluster"] == 1
    assert hits[0].score > hits[1].score


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_search_empty_query_raises(corpus, tmp_path, query):
    target = _open(corpus, tmp_path)
    with pytest.raises(EmptyQueryError):
        search_protoclusters(target, query)


def test_search_unknown_field_reports_field_and_available(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    with pytest.raises(UnknownFieldError) as excinfo:
        search_protoclusters(target, "pfam:PF00512 AND go:something")

    error = excinfo.value
    assert error.field == "go"
    assert error.available_fields == sorted(
        definition.name for definition in SEARCH_FIELD_REGISTRY
    )


@pytest.mark.parametrize("query", ["pfam:(", "(pfam:PF00512 AND", "-pfam:PF00512"])
def test_search_malformed_query_raises_structured_syntax_error(corpus, tmp_path, query):
    target = _open(corpus, tmp_path)
    with pytest.raises(QuerySyntaxError):
        search_protoclusters(target, query)


def test_search_syntax_error_carries_parser_message(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    with pytest.raises(QuerySyntaxError) as excinfo:
        search_protoclusters(target, "pfam:(")
    assert "Syntax Error" in excinfo.value.message


def test_search_validates_pagination_arguments(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    with pytest.raises(ValueError):
        search_protoclusters(target, "pfam:PF00512", offset=-1)
    with pytest.raises(ValueError):
        search_protoclusters(target, "pfam:PF00512", limit=0)


def test_search_over_index_built_from_fixture(tmp_path):
    documents = list(extract_documents([Path("multi.json")], FIXTURES / "antismash8"))
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(documents), index_dir)
    target = open_index(index_dir)
    assert search_protoclusters(target, 'category:"trans-AT PKS"').total == 1


@pytest.fixture
def grouped() -> list[ProtoclusterSearchDocument]:
    return [
        _doc(1, record_id="recA", region_number=1, pfam=("shared",)),
        _doc(2, record_id="recA", region_number=1, pfam=("shared",)),
        _doc(1, record_id="recA", region_number=2, pfam=("shared",)),
        _doc(1, record_id="recB", region_number=1, pfam=("shared",)),
    ]


def test_search_region_collapses_protoclusters_into_unique_regions(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    result = search_region(target, "pfam:shared")
    assert result.total == 3
    assert [(hit.record, hit.region) for hit in result.hits] == [
        ("recA", 1),
        ("recA", 2),
        ("recB", 1),
    ]
    assert all(isinstance(hit.region, int) for hit in result.hits)
    assert all(hit.output_file == "rec.json" for hit in result.hits)
    assert all(hit.input_file == "rec.gbk" for hit in result.hits)


def test_search_record_collapses_protoclusters_into_unique_records(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    result = search_record(target, "pfam:shared")
    assert result.total == 2
    assert [hit.record for hit in result.hits] == ["recA", "recB"]
    assert all(hit.output_file == "rec.json" for hit in result.hits)
    assert all(hit.input_file == "rec.gbk" for hit in result.hits)


def test_grouped_search_totals_are_nested(tmp_path):
    documents = [
        _doc(1, record_id="recA", region_number=1, pfam=("shared",)),
        _doc(2, record_id="recA", region_number=1, pfam=("shared",)),
        _doc(1, record_id="recA", region_number=2, pfam=("shared",)),
        _doc(1, record_id="recB", region_number=1, pfam=("shared",)),
    ]
    target = _open(documents, tmp_path)
    protoclusters = search_protoclusters(target, "pfam:shared", limit=10)
    regions = search_region(target, "pfam:shared", limit=10)
    records = search_record(target, "pfam:shared", limit=10)
    assert protoclusters.total == 4
    assert regions.total == 3
    assert records.total == 2


def test_region_score_is_best_matching_protocluster(tmp_path):
    documents = [
        _doc(
            1,
            record_id="recA",
            region_number=1,
            pfam=("shared",),
            organism="nothing here",
        ),
        _doc(
            2,
            record_id="recA",
            region_number=1,
            pfam=("nothing",),
            organism="shared term",
        ),
    ]
    target = _open(documents, tmp_path)
    protoclusters = search_protoclusters(target, "shared", limit=10)
    best = max(hit.score for hit in protoclusters.hits)
    lowest = min(hit.score for hit in protoclusters.hits)
    assert best > lowest

    region = search_region(target, "shared").hits[0]
    assert (region.record, region.region) == ("recA", 1)
    assert region.score == best

    record = search_record(target, "shared").hits[0]
    assert record.record == "recA"
    assert record.score == best


def test_search_region_pagination(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    page = search_region(target, "pfam:shared", offset=1, limit=1)
    assert page.total == 3
    assert [(hit.record, hit.region) for hit in page.hits] == [("recA", 2)]

    beyond = search_region(target, "pfam:shared", offset=5, limit=2)
    assert beyond.total == 3
    assert beyond.hits == ()


def test_search_record_pagination(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    page = search_record(target, "pfam:shared", offset=1, limit=1)
    assert page.total == 2
    assert [hit.record for hit in page.hits] == ["recB"]

    beyond = search_record(target, "pfam:shared", offset=3, limit=2)
    assert beyond.total == 2
    assert beyond.hits == ()


def test_grouped_search_omits_empty_input_file(tmp_path):
    documents = [
        _doc(1, record_id="recA", region_number=1, pfam=("shared",), input_file="")
    ]
    target = _open(documents, tmp_path)
    assert search_region(target, "pfam:shared").hits[0].input_file is None
    assert search_record(target, "pfam:shared").hits[0].input_file is None


def test_grouped_search_excludes_non_matching_regions(tmp_path):
    documents = [
        _doc(1, record_id="recA", region_number=1, pfam=("match",)),
        _doc(2, record_id="recB", region_number=1, pfam=("other",)),
    ]
    target = _open(documents, tmp_path)
    regions = search_region(target, "pfam:match")
    assert regions.total == 1
    assert (regions.hits[0].record, regions.hits[0].region) == ("recA", 1)
    records = search_record(target, "pfam:match")
    assert records.total == 1
    assert records.hits[0].record == "recA"


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_grouped_search_empty_query_raises(grouped, tmp_path, query):
    target = _open(grouped, tmp_path)
    with pytest.raises(EmptyQueryError):
        search_region(target, query)
    with pytest.raises(EmptyQueryError):
        search_record(target, query)


def test_grouped_search_unknown_field_raises(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    with pytest.raises(UnknownFieldError):
        search_region(target, "go:something")
    with pytest.raises(UnknownFieldError):
        search_record(target, "go:something")


def test_grouped_search_validates_pagination_arguments(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    for func in (search_region, search_record):
        with pytest.raises(ValueError):
            func(target, "pfam:shared", offset=-1)
        with pytest.raises(ValueError):
            func(target, "pfam:shared", limit=0)
