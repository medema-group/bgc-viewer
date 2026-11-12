"""Tests for generated search examples: templates, collection, and persistence.

Covers Stage 2 step 6: the versioned example-template registry in
``document.py``, first-value collection from the built index in
``index.collect_first_values``, and the SQLite ``search_examples`` rows written
by preprocessing.
"""

import sqlite3

from bgc_viewer.search.document import (
    EXAMPLE_TEMPLATE_REGISTRY,
    Location,
    generate_example_queries,
)
from bgc_viewer.search.index import build_index, collect_first_values
from tantivy import Document


def _template(template_id: str):
    return next(t for t in EXAMPLE_TEMPLATE_REGISTRY if t.template_id == template_id)


def _doc(
    *,
    pfam=(),
    pfam_desc=(),
    gene=(),
    locus=(),
    organism="Org One",
    product="Prod",
    category="Cat",
    input_file="in.gbk",
):
    location = Location.parse("[100:500](+)")
    document = Document()
    document.add_text("record", "rec")
    document.add_integer("region", 1)
    document.add_integer("start", location.start)
    document.add_integer("end", location.end)
    document.add_text("product", product)
    document.add_text("product_category", category)
    if organism:
        document.add_text("organism", organism)
    for value in pfam:
        document.add_text("pfam", value)
    for value in pfam_desc:
        document.add_text("pfam_desc", value)
    for value in gene:
        document.add_text("gene", value)
    for value in locus:
        document.add_text("locus", value)
    document.add_text("output_file", "f.json")
    if input_file:
        document.add_text("input_file", input_file)
    return document


# --- Template registry -------------------------------------------------------


def test_registry_has_the_declared_templates_in_order():
    assert [t.template_id for t in EXAMPLE_TEMPLATE_REGISTRY] == [
        "unqualified_word",
        "fielded_word",
        "quoted_phrase",
        "path_prefix",
        "and_fields",
        "negation",
    ]


def test_unqualified_word_prefers_pfam():
    values = {"pfam": "PF00512", "product": "terpene", "record": "rec1"}
    assert _template("unqualified_word").instantiate(values) == "PF00512"


def test_fielded_word_introduces_only_the_field_prefix_without_quotes():
    # A single-word value keeps the example free of double quotes.
    assert _template("fielded_word").instantiate({"product_category": "PKS"}) == "product_category:PKS"


def test_fielded_word_falls_back_to_product_and_skips_multiword_category():
    values = {"product_category": "trans-AT PKS", "product": "T1PKS"}
    assert _template("fielded_word").instantiate(values) == "product:T1PKS"


def test_fielded_word_omitted_without_a_single_word_value():
    assert _template("fielded_word").instantiate({"product_category": "trans-AT PKS"}) is None


def test_unqualified_word_skips_values_that_are_not_a_single_word():
    # NRPS-like fails the single-word filter; the gene name passes.
    values = {"product": "NRPS-like", "gene": "bpsA"}
    assert _template("unqualified_word").instantiate(values) == "bpsA"


def test_quoted_phrase_is_unqualified_and_prefers_organism_then_pfam_desc():
    both = {"organism": "Homo sapiens", "pfam_desc": "His Kinase"}
    assert _template("quoted_phrase").instantiate(both) == '"Homo sapiens"'
    only_pfam = {"pfam_desc": "His Kinase"}
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
    query = _template("and_fields").instantiate({"product_category": "PKS", "product": "T1PKS"})
    assert query == "product_category:PKS AND product:T1PKS"


def test_negation_binds_organism_and_product_and_quotes_multivalued_organism():
    query = _template("negation").instantiate(
        {"organism": "Streptomyces coelicolor", "product": "NRP"}
    )
    assert query == 'organism:"Streptomyces coelicolor" NOT product:NRP'


def test_bare_term_quotes_values_with_metacharacters():
    query = _template("and_fields").instantiate({"product_category": "a:b", "product": "x y"})
    assert query == 'product_category:"a:b" AND product:"x y"'


def test_bare_term_keeps_mid_word_hyphen_unquoted():
    # Tantivy allows '-' inside a bare term; only a leading '-' is the negation
    # operator, so hglE-KS needs no quotes.
    query = _template("and_fields").instantiate(
        {"product_category": "PKS", "product": "hglE-KS"}
    )
    assert query == "product_category:PKS AND product:hglE-KS"


def test_bare_term_quotes_leading_hyphen_and_reserved_words():
    query = _template("and_fields").instantiate({"product_category": "-x", "product": "NOT"})
    assert query == 'product_category:"-x" AND product:"NOT"'


def test_quoted_slot_escapes_embedded_quotes_and_backslashes():
    query = _template("quoted_phrase").instantiate({"organism": 'He said "hi" \\ ok'})
    assert query == '"He said \\"hi\\" \\\\ ok"'


def test_path_prefix_strips_extension_and_adds_wildcard():
    # The usual json extension is dropped and the last component becomes a prefix.
    query = _template("path_prefix").instantiate({"output_file": "NC_003888.3.json"})
    assert query == 'output_file:"NC_003888.3"*'


def test_path_prefix_keeps_directory_and_strips_extension():
    query = _template("path_prefix").instantiate(
        {"output_file": "nested/NC_003888.3.json"}
    )
    assert query == 'output_file:"nested/NC_003888.3"*'


def test_path_prefix_prefers_output_file_then_input_file():
    both = {"output_file": "NC_003888.3.json", "input_file": "nested/NC_003888.gbk"}
    assert _template("path_prefix").instantiate(both) == 'output_file:"NC_003888.3"*'
    only_input = {"input_file": "nested/NC_003888.gbk"}
    assert (
        _template("path_prefix").instantiate(only_input)
        == 'input_file:"nested/NC_003888"*'
    )


def test_path_prefix_omitted_when_stripped_path_is_a_single_component():
    # A bare stem like Y16952.json strips to Y16952, which tokenizes to one
    # term and cannot form a two-term prefix phrase, so the template is skipped.
    assert _template("path_prefix").instantiate({"output_file": "Y16952.json"}) is None


def test_path_prefix_omitted_without_a_path_value():
    assert _template("path_prefix").instantiate({"organism": "Org"}) is None


def test_template_omitted_when_a_required_value_is_missing():
    assert _template("and_fields").instantiate({"product_category": "PKS"}) is None
    assert _template("negation").instantiate({"product": "NRP"}) is None


# --- generate_example_queries -----------------------------------------------


def test_generate_example_queries_returns_rows_in_template_order():
    values = {
        "pfam": "PF00512",
        "organism": "Streptomyces coelicolor",
        "product_category": "PKS",
        "product": "NRP",
        "output_file": "NC_003888.3.json",
    }
    rows = generate_example_queries(values)
    assert [template_id for template_id, _ in rows] == [
        "unqualified_word",
        "fielded_word",
        "quoted_phrase",
        "path_prefix",
        "and_fields",
        "negation",
    ]


def test_generate_example_queries_omits_unfillable_templates():
    rows = generate_example_queries({"pfam": "PF00512"})
    assert [template_id for template_id, _ in rows] == ["unqualified_word"]


def test_generate_example_queries_empty_values_yields_no_rows():
    assert generate_example_queries({}) == []


# --- collect_first_values ---------------------------------------------------


def test_collect_first_values_samples_non_empty_stored_values():
    docs = [
        _doc(
            pfam=("PF00512", "PF00513"),
            pfam_desc=("Alpha",),
            gene=("gA",),
            locus=("L1",),
        ),
        _doc(
            pfam=("PF99999",),
            pfam_desc=("Beta",),
            gene=("gB",),
            locus=("L2",),
        ),
    ]
    values = collect_first_values(build_index(iter(docs)))
    assert values["pfam"] in {"PF00512", "PF99999"}
    assert values["pfam_desc"] in {"Alpha", "Beta"}
    assert values["gene"] in {"gA", "gB"}
    assert values["locus"] in {"L1", "L2"}
    assert values["organism"] == "Org One"
    assert values["product"] == "Prod"
    assert values["product_category"] == "Cat"
    assert values["input_file"] == "in.gbk"


def test_collect_first_values_skips_numeric_fields():
    values = collect_first_values(build_index(iter([_doc()])))
    for numeric in ("region", "start", "end"):
        assert numeric not in values


def test_collect_first_values_takes_value_from_later_document_when_earlier_is_empty():
    docs = [
        _doc(pfam=(), pfam_desc=()),
        _doc(pfam=("PF00001",), pfam_desc=("Later",)),
    ]
    values = collect_first_values(build_index(iter(docs)))
    assert values["pfam"] == "PF00001"
    assert values["pfam_desc"] == "Later"


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
    # Either source record may supply the samples after parallel indexing.
    assert queries["unqualified_word"] == "PF00501"
    assert queries["fielded_word"] in {"product_category:PKS", "product_category:NRPS"}
    assert queries["quoted_phrase"] in {
        '"Streptomyces coelicolor"',
        '"Bacillus subtilis"',
    }
    assert queries["and_fields"] in {
        "product_category:PKS AND product:polyketide",
        "product_category:NRPS AND product:NRPS",
    }
    assert queries["negation"] in {
        'organism:"Streptomyces coelicolor" NOT product:polyketide',
        'organism:"Bacillus subtilis" NOT product:NRPS',
    }


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
