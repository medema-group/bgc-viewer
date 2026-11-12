import json
from pathlib import Path

import pytest
from bgc_viewer.search.document import SEARCH_FIELDS, SEARCH_SCHEMA_VERSION, Location
from bgc_viewer.search.extraction import build_document, extract_documents
from bgc_viewer.search.index import (
    EmptyQueryError,
    IndexCorruptError,
    IndexIncompatibleError,
    IndexNotFoundError,
    QuerySyntaxError,
    Results,
    SearchHit,
    UnknownFieldError,
    build_index,
    open_index,
    search_record,
    search_regions,
)
from tantivy import Document, Index

SCHEMA_FIELD_NAMES = tuple(field.name for field in SEARCH_FIELDS)
FIXTURES = Path(__file__).parent / "fixtures"


def _doc(
    region_number: int,
    *,
    record_id: str = "recA",
    location: str = "[100:500](+)",
    product: tuple[str, ...] = ("NRP",),
    category: tuple[str, ...] = ("NRPS",),
    organism: str = "His Kinase Amycolatopsis",
    pfam: tuple[str, ...] = (),
    pfam_desc: tuple[str, ...] = (),
    gene: tuple[str, ...] = (),
    locus: tuple[str, ...] = (),
    input_file: str = "rec.gbk",
    output_file: str = "rec.json",
) -> Document:
    """A region document, built the way extraction builds one."""
    parsed = Location.parse(location)
    return build_document(
        {
            "record": [record_id],
            "region": [region_number],
            "start": [parsed.start],
            "end": [parsed.end],
            "product": list(product),
            "product_category": list(category),
            "organism": [organism] if organism else [],
            "pfam": list(pfam),
            "pfam_desc": list(pfam_desc),
            "gene": list(gene),
            "locus": list(locus),
            "output_file": [output_file],
            "input_file": [input_file] if input_file else [],
        }
    )


@pytest.fixture
def corpus() -> list[Document]:
    return [
        _doc(
            1,
            pfam=("PF00512", "PF00513"),
            pfam_desc=("His Kinase",),
            gene=("spaA", "spaB"),
            locus=("SPAU_1",),
        ),
        _doc(
            2,
            location="[600:900](+)",
            product=("T1PKS",),
            category=("PKS",),
            organism="Streptomyces coelicolor",
            pfam=("PF00999",),
            pfam_desc=("Thioesterase",),
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
    if "fast" in expected:
        assert bool(field_spec["options"]["fast"]) is expected["fast"]
    for key, value in expected.get("indexing", {}).items():
        assert field_spec["options"]["indexing"][key] == value


def test_schema_has_the_declared_field_set(tmp_path):
    schema_dir = _empty_schema_dir(tmp_path)
    assert set(schema_dir) == set(SCHEMA_FIELD_NAMES)


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        (
            "pfam",
            {
                "type": "text",
                "stored": True,
                "fast": True,
                "indexing": {"tokenizer": "raw", "record": "freq"},
            },
        ),
        (
            "organism",
            {
                "type": "text",
                "stored": True,
                "fast": True,
                "indexing": {"tokenizer": "raw"},
            },
        ),
        (
            "text",
            {
                "type": "text",
                "stored": False,
                "fast": False,
                "indexing": {"tokenizer": "default", "record": "position"},
            },
        ),
        (
            "output_file",
            {
                "type": "text",
                "stored": True,
                "indexing": {"tokenizer": "path", "record": "position"},
            },
        ),
        (
            "input_file",
            {
                "type": "text",
                "stored": True,
                "indexing": {"tokenizer": "path", "record": "position"},
            },
        ),
        ("region", {"type": "i64", "stored": True, "fast": True}),
        ("start", {"type": "i64", "stored": True, "fast": True}),
        ("ripp_mass", {"type": "f64", "stored": True, "fast": True}),
        ("is_complete", {"type": "bool", "stored": True, "fast": True}),
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
    assert (index_dir / "version.txt").read_text(encoding="utf-8") == str(
        SEARCH_SCHEMA_VERSION
    )


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
        ('organism:"Streptomyces coelicolor"', 1),
        ("organism:Streptomyces", 0),
        ('organism:"streptomyces coelicolor"', 0),
    ],
)
def test_organism_matches_its_whole_value(built, query, expected_hits):
    index, searcher = built
    assert _hits(searcher, index, query) == expected_hits


@pytest.mark.parametrize(
    ("query", "expected_hits"),
    [
        ("text:amycolatopsis", 1),
        ("text:Amycolatopsis", 1),
        ('text:"His Kinase"', 1),
        ('text:"Kinase His"', 0),
        # Values are added in registry order, organism before gene, but the
        # words of different values are not adjacent.
        ('text:"Amycolatopsis spaA"', 0),
        ('text:"Amycolatopsis spaA"~1', 1),
    ],
)
def test_catch_all_text_is_lowercased_and_phrasable(built, query, expected_hits):
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
        ("region:[1 TO 2]", 2),
    ],
)
def test_numeric_fields_are_range_queryable(built, query, expected_hits):
    index, searcher = built
    assert _hits(searcher, index, query) == expected_hits


def test_numeric_fields_are_stored(built):
    index, searcher = built
    stored = _stored_hit(searcher, index, "text:coelicolor")
    assert stored["start"] == [600]
    assert stored["end"] == [900]
    assert stored["region"] == [2]


def test_stored_summary_includes_display_fields(pfam_summary):
    assert pfam_summary["product"] == ["NRP"]
    assert pfam_summary["product_category"] == ["NRPS"]
    assert pfam_summary["record"] == ["recA"]


@pytest.mark.parametrize("field", ["pfam", "pfam_desc", "gene", "locus"])
def test_every_registered_field_is_stored_in_the_index(pfam_summary, field):
    # Every registered field is stored so its value can be read back for
    # example collection and diagnostics, even though these fields are not
    # returned in ordinary hits (see test_search_omits_indexed_only_fields).
    assert field in pfam_summary


def test_empty_optional_single_field_is_not_indexed(built):
    index, searcher = built
    assert _hits(searcher, index, 'input_file:"rec.gbk"') == 1
    assert "input_file" not in _stored_hit(searcher, index, "text:coelicolor")


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
    stored = _stored_hit(searcher, reopened, "text:streptomyces")
    assert stored["organism"] == ["Streptomyces coelicolor"]


def test_build_from_extracted_fixture():
    documents = list(extract_documents([Path("multi.json")], FIXTURES / "antismash8"))
    index = build_index(iter(documents))
    searcher = index.searcher()
    assert searcher.num_docs == len(documents)
    assert _hits(searcher, index, 'product_category:"trans-AT PKS"') == 1


def _open(corpus, tmp_path, name="tantivy.index") -> Index:
    index_dir = tmp_path / name
    build_index(iter(corpus), index_dir)
    return open_index(index_dir)


def test_open_index_reopens_a_committed_index(corpus, tmp_path):
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(corpus), index_dir)

    reopened = open_index(index_dir)
    result = search_regions(reopened, "pfam:PF00512")
    assert len(result.hits) == 1


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
    (index_dir / "version.txt").write_text(
        str(SEARCH_SCHEMA_VERSION + 1), encoding="utf-8"
    )

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
    (index_dir / "version.txt").write_text(str(SEARCH_SCHEMA_VERSION), encoding="utf-8")

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
    result = search_regions(target, "pfam:PF00512")

    expected = Results(
        hits=(
            SearchHit(
                score=result.hits[0].score,
                fields={
                    "record": "recA",
                    "region": 1,
                    "start": 100,
                    "end": 500,
                    "product": ["NRP"],
                    "product_category": ["NRPS"],
                    "organism": "His Kinase Amycolatopsis",
                    "output_file": "rec.json",
                    "input_file": "rec.gbk",
                },
            ),
        ),
        has_more=False,
    )
    assert result == expected and result.hits[0].score > 0


def test_search_omits_indexed_only_fields(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    hit = search_regions(target, "pfam:PF00512").hits[0]
    for field in ("pfam", "pfam_desc", "gene", "locus", "text"):
        assert field not in hit.fields


def test_search_omits_empty_optional_field(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    hit = search_regions(target, "text:coelicolor").hits[0]
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
    assert len(search_regions(target, query).hits) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("text:amycolatopsis", 1),
        ("text:Amycolatopsis", 1),
        ('text:"His Kinase"', 1),
        ('text:"Kinase His"', 0),
    ],
)
def test_search_full_text_is_lowercased_and_phrasable(
    corpus, tmp_path, query, expected
):
    target = _open(corpus, tmp_path)
    assert len(search_regions(target, query).hits) == expected


@pytest.mark.parametrize(
    "query",
    [
        "text:Strepto",
        "text:Strepto*",
        "pfam_desc:Thioest",
        "pfam_desc:Thioest*",
        "Strepto*",
    ],
)
def test_single_word_prefix_is_not_supported(corpus, tmp_path, query):
    """A single word matches whole words only, with or without a trailing ``*``.

    Tantivy offers prefix matching only as a per-field parser option applied to
    *every* term on the field, which would widen a plain search without the
    searcher asking for it, so no field is configured for it. A ``*`` after a
    bare term is not a wildcard either: the grammar folds it into the term text
    and the tokenizer drops it. Prefix matching exists only inside a multi-word
    quoted phrase; see ``test_phrase_prefix_matches_the_last_word``.
    """
    target = _open(corpus, tmp_path)
    assert len(search_regions(target, query).hits) == 0


@pytest.mark.parametrize(
    "query",
    [
        "text:Streptomycez",
        "pfam_desc:Thioesteraz",
        "Thioesteraz",
    ],
)
def test_search_plain_terms_are_not_typo_tolerated(corpus, tmp_path, query):
    """Nothing widens a plain term to nearby spellings.

    Tantivy offers Levenshtein tolerance only as a per-field parser option applied
    to every term on the field, which would make a bare-term search fuzzy
    without the searcher asking for it, so no distance is configured.
    """
    target = _open(corpus, tmp_path)
    assert len(search_regions(target, query).hits) == 0


@pytest.mark.parametrize(
    "query",
    [
        "pfam:PF0051*",
        "product:T1PK*",
        "gene:spa*",
        "locus:SPAU_*",
    ],
)
def test_search_exact_fields_do_not_match_prefixes(corpus, tmp_path, query):
    target = _open(corpus, tmp_path)
    assert len(search_regions(target, query).hits) == 0


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # Whole value as a phrase matches exactly one document.
        ('output_file:"nested/NC_003888.3.json"', 1),
        # Each path component is its own term: directory, stem, and extension.
        ("output_file:nested", 1),
        ("output_file:NC_003888.3", 2),
        ("output_file:NC_003888.3.json", 2),
        ("output_file:json", 3),
        # Prefix on a multi-token phrase narrows the last component.
        ('output_file:"nested/NC_003888"*', 1),
        # The path analyzer is case-sensitive, like the raw analyzer it replaces.
        ("output_file:NESTED", 0),
        # A component that is not present matches nothing.
        ("output_file:missing", 0),
    ],
)
def test_path_field_matches_by_component_phrase_and_prefix(tmp_path, query, expected):
    """A ``path`` field keeps the whole value searchable while splitting on
    ``/`` and ``.`` so directory, stem, and extension each match on their own.
    """
    documents = [
        _doc(1, output_file="nested/NC_003888.3.json"),
        _doc(2, output_file="NC_003888.3.json"),
        _doc(3, output_file="top/Y16952.json"),
    ]
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(documents), index_dir)
    target = open_index(index_dir)
    assert len(search_regions(target, query).hits) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("input_file:rec", 2),
        ("input_file:gbk", 3),
        ("input_file:rec.gbk", 2),
        ("input_file:other", 1),
    ],
)
def test_input_file_is_path_tokenized(tmp_path, query, expected):
    documents = [
        _doc(1, input_file="rec.gbk"),
        _doc(2, input_file="rec.gbk"),
        _doc(3, input_file="other.gbk"),
    ]
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(documents), index_dir)
    target = open_index(index_dir)
    assert len(search_regions(target, query).hits) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ('text:"His Kinase Amycolatopsis"', 1),
        ('text:"His Amycolatopsis"', 0),
        ('text:"His Amycolatopsis"~1', 1),
        ('text:"His Amycolatopsis"~2', 1),
        ('text:"Kinase His"', 0),
        ('text:"Kinase His"~1', 0),
        ('text:"Kinase His"~2', 1),
        ('"His Amycolatopsis"~1', 1),
    ],
)
def test_phrase_slop_widens_the_gap_between_words(corpus, tmp_path, query, expected):
    """``"a b"~N`` is Tantivy's native phrase slop on a quoted phrase.

    Slop is the total number of positions the query words may shift from sitting
    next to each other, so skipping one word costs 1 and swapping two adjacent
    words costs 2. It is available on the catch-all text field without registry
    support and only when the searcher types it.
    """
    target = _open(corpus, tmp_path)
    assert len(search_regions(target, query).hits) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ('text:"streptomyces coeli"*', 1),
        ('text:"his ki"*', 1),
        ('text:"streptomyces coelicolor"*', 1),
        ('text:"coelicolor strepto"*', 0),
    ],
)
def test_phrase_prefix_matches_the_last_word(corpus, tmp_path, query, expected):
    """``"a b"*`` turns the last word of a quoted phrase into a prefix.

    This is Tantivy's native phrase prefix. The prefixed word still has to sit
    next to the words before it, so a reversed phrase matches nothing.
    """
    target = _open(corpus, tmp_path)
    assert len(search_regions(target, query).hits) == expected


@pytest.mark.parametrize(
    "query",
    ['text:"coeli"*', 'text:"ki"*'],
)
def test_single_word_phrase_prefix_is_rejected(corpus, tmp_path, query):
    """A prefix needs a phrase of at least two words, and says so.

    Tantivy refuses ``"word"*`` outright, which is the single-word prefix that
    is deliberately not offered.
    """
    target = _open(corpus, tmp_path)
    with pytest.raises(QuerySyntaxError):
        search_regions(target, query)


@pytest.mark.parametrize(
    "query",
    [
        "organism:Streptomyces~1",
        "text:Thioesterase~1",
        "pfam:PF00513~1",
    ],
)
def test_tilde_on_an_unquoted_term_matches_nothing(corpus, tmp_path, query):
    """The slop operator needs a quoted phrase; on a bare term the tilde is text.

    Tantivy attaches ``~N`` only to quoted phrases, so a tilde typed after an
    unquoted term stays part of the term and cannot match.
    """
    target = _open(corpus, tmp_path)
    assert len(search_regions(target, query).hits) == 0


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("pfam:PF00512 AND pfam:PF00513", 1),
        ("pfam:PF00512 AND pfam:PF00999", 0),
        ("pfam:PF00512 OR pfam:PF00999", 2),
        ("(pfam:PF00512 OR pfam:PF00999) AND text:streptomyces", 1),
        ("text:streptomyces NOT pfam:PF00999", 0),
        ("text:amycolatopsis NOT pfam:PF00999", 1),
        ("gene:spaA AND gene:spaB", 1),
    ],
)
def test_search_boolean_precedence_and_nesting(corpus, tmp_path, query, expected):
    target = _open(corpus, tmp_path)
    assert len(search_regions(target, query).hits) == expected


def test_search_bare_terms_cover_default_fields(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    assert len(search_regions(target, "spaA").hits) == 1
    assert len(search_regions(target, "coelicolor").hits) == 1
    assert len(search_regions(target, "SPAU_1").hits) == 1
    # A word inside a value matches through the catch-all text field.
    assert len(search_regions(target, "thioesterase").hits) == 1
    # Numeric navigation fields are excluded from default search.
    assert len(search_regions(target, "600").hits) == 0


@pytest.mark.parametrize(
    ("query", "expected"),
    [("start:[100 TO 500]", 1), ("end:[800 TO 1000]", 1), ("region:[1 TO 2]", 2)],
)
def test_search_numeric_range(corpus, tmp_path, query, expected):
    target = _open(corpus, tmp_path)
    assert len(search_regions(target, query).hits) == expected


def test_search_pagination_and_has_more(corpus, tmp_path):
    many = [
        _doc(number, pfam=("shared",), organism=f"organism {number}")
        for number in range(5)
    ]
    target = _open(many, tmp_path)

    full = search_regions(target, "pfam:shared", limit=10).hits
    assert {hit.fields["region"] for hit in full} == set(range(5))
    page_one = search_regions(target, "pfam:shared", offset=0, limit=2)
    assert page_one.hits == full[:2]
    assert page_one.has_more is True

    page_two = search_regions(target, "pfam:shared", offset=3, limit=2)
    assert page_two.hits == full[3:5]
    assert page_two.has_more is False

    beyond = search_regions(target, "pfam:shared", offset=10, limit=2)
    assert beyond.hits == ()
    assert beyond.has_more is False


def test_search_equal_scores_have_stable_order_for_unchanged_index(tmp_path):
    many = [_doc(number, pfam=("shared",)) for number in range(4)]
    target = _open(many, tmp_path)
    hits = search_regions(target, "pfam:shared", limit=10).hits

    scores = [hit.score for hit in hits]
    assert scores == sorted(scores, reverse=True)
    assert len(set(scores)) == 1
    assert {hit.fields["region"] for hit in hits} == set(range(4))
    for _ in range(3):
        assert search_regions(target, "pfam:shared", limit=10).hits == hits


def test_search_boosts_exact_field_above_full_text(tmp_path):
    documents = [
        _doc(1, pfam=("shared",), organism="other organism"),
        _doc(2, pfam=("other",), organism="shared term"),
    ]
    target = _open(documents, tmp_path)
    hits = search_regions(target, "shared", limit=10).hits

    assert hits[0].fields["region"] == 1
    assert hits[0].score > hits[1].score


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_search_empty_query_raises(corpus, tmp_path, query):
    target = _open(corpus, tmp_path)
    with pytest.raises(EmptyQueryError):
        search_regions(target, query)


def test_search_unknown_field_reports_field_and_available(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    with pytest.raises(UnknownFieldError) as excinfo:
        search_regions(target, "pfam:PF00512 AND go:something")

    error = excinfo.value
    assert error.field == "go"
    assert error.available_fields == sorted(SCHEMA_FIELD_NAMES)


@pytest.mark.parametrize("query", ["pfam:(", "(pfam:PF00512 AND", "-pfam:PF00512"])
def test_search_malformed_query_raises_structured_syntax_error(corpus, tmp_path, query):
    target = _open(corpus, tmp_path)
    with pytest.raises(QuerySyntaxError):
        search_regions(target, query)


def test_search_syntax_error_carries_parser_message(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    with pytest.raises(QuerySyntaxError) as excinfo:
        search_regions(target, "pfam:(")
    assert "Syntax Error" in excinfo.value.message


def test_search_validates_pagination_arguments(corpus, tmp_path):
    target = _open(corpus, tmp_path)
    with pytest.raises(ValueError):
        search_regions(target, "pfam:PF00512", offset=-1)
    with pytest.raises(ValueError):
        search_regions(target, "pfam:PF00512", limit=0)


def test_search_over_index_built_from_fixture(tmp_path):
    documents = list(extract_documents([Path("multi.json")], FIXTURES / "antismash8"))
    index_dir = tmp_path / "tantivy.index"
    build_index(iter(documents), index_dir)
    target = open_index(index_dir)
    assert len(search_regions(target, 'product_category:"trans-AT PKS"').hits) == 1


@pytest.fixture
def grouped() -> list[Document]:
    return [
        _doc(1, record_id="recA", pfam=("shared",)),
        _doc(2, record_id="recA", pfam=("shared",)),
        _doc(1, record_id="recB", pfam=("shared",)),
    ]


def test_search_record_collapses_regions_into_unique_records(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    result = search_record(target, "pfam:shared")
    assert len(result.hits) == 2
    assert {hit.record for hit in result.hits} == {"recA", "recB"}
    assert all(hit.output_file == "rec.json" for hit in result.hits)
    assert all(hit.input_file == "rec.gbk" for hit in result.hits)


def test_grouped_search_hit_counts_are_nested(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    regions = search_regions(target, "pfam:shared", limit=10)
    records = search_record(target, "pfam:shared", limit=10)
    assert len(regions.hits) == 3
    assert len(records.hits) == 2


def test_record_score_is_best_matching_region(tmp_path):
    documents = [
        _doc(1, record_id="recA", pfam=("shared",), organism="nothing here"),
        _doc(2, record_id="recA", pfam=("nothing",), organism="shared term"),
    ]
    target = _open(documents, tmp_path)
    regions = search_regions(target, "shared", limit=10)
    best = max(hit.score for hit in regions.hits)
    lowest = min(hit.score for hit in regions.hits)
    assert best > lowest

    record = search_record(target, "shared").hits[0]
    assert record.record == "recA"
    assert record.score == best


def test_search_record_pagination(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    page = search_record(target, "pfam:shared", offset=1, limit=1)
    full = search_record(target, "pfam:shared")
    assert page.hits == full.hits[1:2]
    assert page.has_more is False

    beyond = search_record(target, "pfam:shared", offset=3, limit=2)
    assert beyond.hits == ()
    assert beyond.has_more is False


def test_grouped_search_omits_empty_input_file(tmp_path):
    documents = [_doc(1, record_id="recA", pfam=("shared",), input_file="")]
    target = _open(documents, tmp_path)
    assert search_record(target, "pfam:shared").hits[0].input_file is None


def test_grouped_search_excludes_non_matching_regions(tmp_path):
    documents = [
        _doc(1, record_id="recA", pfam=("match",)),
        _doc(1, record_id="recB", pfam=("other",)),
    ]
    target = _open(documents, tmp_path)
    records = search_record(target, "pfam:match")
    assert len(records.hits) == 1
    assert records.hits[0].record == "recA"


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_grouped_search_empty_query_raises(grouped, tmp_path, query):
    target = _open(grouped, tmp_path)
    with pytest.raises(EmptyQueryError):
        search_record(target, query)


def test_grouped_search_unknown_field_raises(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    with pytest.raises(UnknownFieldError):
        search_record(target, "go:something")


def test_grouped_search_validates_pagination_arguments(grouped, tmp_path):
    target = _open(grouped, tmp_path)
    with pytest.raises(ValueError):
        search_record(target, "pfam:shared", offset=-1)
    with pytest.raises(ValueError):
        search_record(target, "pfam:shared", limit=0)


@pytest.mark.parametrize("count", [0, 3])
def test_build_reports_document_count_and_finishing_phases(count):
    progress = []
    target = build_index(
        (_doc(number) for number in range(count)),
        progress_callback=lambda phase, indexed: progress.append((phase, indexed)),
    )
    assert progress == [("indexing", indexed) for indexed in range(count + 1)] + [
        ("committing", count),
        ("merging", count),
        ("complete", count),
    ]
    assert target.searcher().num_docs == count


def test_failed_build_does_not_report_completion():
    progress = []

    def documents():
        yield _doc(1)
        raise RuntimeError("extraction failed")

    with pytest.raises(RuntimeError, match="extraction failed"):
        build_index(
            documents(),
            progress_callback=lambda phase, indexed: progress.append((phase, indexed)),
        )
    assert progress == [("indexing", 0), ("indexing", 1)]
