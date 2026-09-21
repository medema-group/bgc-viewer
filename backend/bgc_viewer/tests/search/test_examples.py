"""Tests for generated search examples: templates, collection, and persistence.

Covers Stage 2 step 6: the versioned example-template registry in
``document.py``, first-value collection from the built index in
``index.collect_first_values``, and the SQLite ``search_examples`` rows written
by preprocessing.
"""

import sqlite3

import pytest
from bgc_viewer.search.document import (
    EXAMPLE_TEMPLATE_REGISTRY,
    ProtoclusterSearchDocument,
    SearchFields,
    SourceFile,
    Location,
    generate_example_queries,
)
from bgc_viewer.search.index import build_index, collect_first_values


def _template(template_id: str):
    return next(t for t in EXAMPLE_TEMPLATE_REGISTRY if t.template_id == template_id)


def _doc(
    *,
    pfam=(),
    pfam_name=(),
    gene=(),
    locus=(),
    organism="Org One",
    product="Prod",
    category="Cat",
    input_file="in.gbk",
):
    return ProtoclusterSearchDocument(
        source=SourceFile("8.0.2", "f.json", input_file),
        search_fields=SearchFields(
            record_id="rec",
            region_number=1,
            protocluster_number=1,
            location=Location.parse("[100:500](+)"),
            product=product,
            category=category,
            organism=organism,
            pfam=pfam,
            pfam_name=pfam_name,
            gene=gene,
            locus=locus,
        ),
    )


# --- Template registry -------------------------------------------------------


def test_registry_has_the_declared_templates_in_order():
    assert [t.template_id for t in EXAMPLE_TEMPLATE_REGISTRY] == [
        "unqualified_word",
        "fielded_word",
        "quoted_phrase",
        "and_fields",
        "negation",
    ]


def test_unqualified_word_uses_first_single_word_default_field():
    values = {"pfam": "PF00512", "organism": "Streptomyces coelicolor"}
    assert _template("unqualified_word").instantiate(values) == "PF00512"


def test_fielded_word_introduces_only_the_field_prefix_without_quotes():
    # A single-word value keeps the example free of double quotes.
    assert _template("fielded_word").instantiate({"category": "PKS"}) == "category:PKS"


def test_fielded_word_falls_back_to_product_and_skips_multiword_category():
    values = {"category": "trans-AT PKS", "product": "T1PKS"}
    assert _template("fielded_word").instantiate(values) == "product:T1PKS"


def test_fielded_word_omitted_without_a_single_word_value():
    assert _template("fielded_word").instantiate({"category": "trans-AT PKS"}) is None


def test_unqualified_word_skips_multiword_default_fields():
    # organism is multi-word and fails the single-word filter; product passes.
    values = {"organism": "Streptomyces coelicolor", "product": "terpene"}
    assert _template("unqualified_word").instantiate(values) == "terpene"


def test_quoted_phrase_is_unqualified_and_prefers_organism_then_pfam_name():
    both = {"organism": "Homo sapiens", "pfam_name": "His Kinase"}
    assert _template("quoted_phrase").instantiate(both) == '"Homo sapiens"'
    only_pfam = {"pfam_name": "His Kinase"}
    assert _template("quoted_phrase").instantiate(only_pfam) == '"His Kinase"'


def test_quoted_phrase_omitted_without_a_multiword_value():
    assert _template("quoted_phrase").instantiate({"organism": "Amycolatopsis"}) is None


def test_quoted_phrase_content_always_contains_a_space():
    # The quotes are only meaningful because the value has whitespace; a value
    # without a space never reaches this template.
    query = _template("quoted_phrase").instantiate(
        {"organism": "Streptomyces coelicolor"}
    )
    inner = query.strip('"')
    assert " " in inner


def test_and_fields_binds_category_and_product():
    query = _template("and_fields").instantiate({"category": "PKS", "product": "T1PKS"})
    assert query == "category:PKS AND product:T1PKS"


def test_negation_binds_organism_and_product_and_quotes_multivalued_organism():
    query = _template("negation").instantiate(
        {"organism": "Streptomyces coelicolor", "product": "NRP"}
    )
    assert query == 'organism:"Streptomyces coelicolor" NOT product:NRP'


def test_bare_term_quotes_values_with_metacharacters():
    query = _template("and_fields").instantiate({"category": "a:b", "product": "x y"})
    assert query == 'category:"a:b" AND product:"x y"'


def test_bare_term_keeps_mid_word_hyphen_unquoted():
    # Tantivy allows '-' inside a bare term; only a leading '-' is the negation
    # operator, so hglE-KS needs no quotes.
    query = _template("and_fields").instantiate(
        {"category": "PKS", "product": "hglE-KS"}
    )
    assert query == "category:PKS AND product:hglE-KS"


def test_bare_term_quotes_leading_hyphen_and_reserved_words():
    query = _template("and_fields").instantiate({"category": "-x", "product": "NOT"})
    assert query == 'category:"-x" AND product:"NOT"'


def test_quoted_slot_escapes_embedded_quotes_and_backslashes():
    query = _template("quoted_phrase").instantiate({"organism": 'He said "hi" \\ ok'})
    assert query == '"He said \\"hi\\" \\\\ ok"'


def test_template_omitted_when_a_required_value_is_missing():
    assert _template("and_fields").instantiate({"category": "PKS"}) is None
    assert _template("negation").instantiate({"product": "NRP"}) is None


# --- generate_example_queries -----------------------------------------------


def test_generate_example_queries_returns_rows_in_template_order():
    values = {
        "pfam": "PF00512",
        "organism": "Streptomyces coelicolor",
        "category": "PKS",
        "product": "NRP",
    }
    rows = generate_example_queries(values)
    assert [template_id for template_id, _ in rows] == [
        "unqualified_word",
        "fielded_word",
        "quoted_phrase",
        "and_fields",
        "negation",
    ]


def test_generate_example_queries_omits_unfillable_templates():
    rows = generate_example_queries({"pfam": "PF00512"})
    assert [template_id for template_id, _ in rows] == ["unqualified_word"]


def test_generate_example_queries_empty_values_yields_no_rows():
    assert generate_example_queries({}) == []


# --- collect_first_values ---------------------------------------------------


def test_collect_first_values_reads_first_non_empty_value_per_field():
    docs = [
        _doc(
            pfam=("PF00512", "PF00513"),
            pfam_name=("Alpha",),
            gene=("gA",),
            locus=("L1",),
        ),
        _doc(
            pfam=("PF99999",),
            pfam_name=("Beta",),
            gene=("gB",),
            locus=("L2",),
        ),
    ]
    values = collect_first_values(build_index(iter(docs)))
    assert values["pfam"] == "PF00512"
    assert values["pfam_name"] == "Alpha"
    assert values["gene"] == "gA"
    assert values["locus"] == "L1"
    assert values["organism"] == "Org One"
    assert values["product"] == "Prod"
    assert values["category"] == "Cat"
    assert values["input_file"] == "in.gbk"


def test_collect_first_values_skips_numeric_fields():
    values = collect_first_values(build_index(iter([_doc()])))
    for numeric in ("region", "protocluster", "start", "end"):
        assert numeric not in values


def test_collect_first_values_takes_value_from_later_document_when_earlier_is_empty():
    docs = [
        _doc(pfam=(), pfam_name=()),
        _doc(pfam=("PF00001",), pfam_name=("Later",)),
    ]
    values = collect_first_values(build_index(iter(docs)))
    assert values["pfam"] == "PF00001"
    assert values["pfam_name"] == "Later"


def test_collect_first_values_empty_index_returns_nothing():
    assert collect_first_values(build_index(iter(()))) == {}


# --- Preprocessing persistence ---------------------------------------------


def _example_rows(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT template, query FROM search_examples ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def test_preprocessing_creates_search_examples_table(test_database):
    db_path, _ = test_database
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert "search_examples" in tables


def test_preprocessing_stores_generated_examples_in_template_order(test_database):
    db_path, _ = test_database
    rows = _example_rows(db_path)
    assert [template for template, _ in rows] == [
        "unqualified_word",
        "fielded_word",
        "quoted_phrase",
        "and_fields",
        "negation",
    ]
    queries = dict(rows)
    # The first protocluster of the sample corpus drives every collected value.
    assert queries["unqualified_word"] == "PF00501"
    assert queries["fielded_word"] == "category:PKS"
    assert queries["quoted_phrase"] == '"Streptomyces coelicolor"'
    assert queries["and_fields"] == "category:PKS AND product:polyketide"
    assert (
        queries["negation"]
        == 'organism:"Streptomyces coelicolor" NOT product:polyketide'
    )


def test_preprocessing_reports_example_count(test_database):
    db_path, _ = test_database
    assert len(_example_rows(db_path)) == 5


def test_rebuild_replaces_examples_without_duplicates(test_database):
    db_path, source_dir = test_database
    from bgc_viewer.preprocessing import preprocess_antismash_files

    preprocess_antismash_files(str(source_dir), str(db_path))
    rows = _example_rows(db_path)
    assert [template for template, _ in rows] == [
        "unqualified_word",
        "fielded_word",
        "quoted_phrase",
        "and_fields",
        "negation",
    ]
