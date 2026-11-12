"""Tests for structured filters, facet counts, value suggestions, and sorting.

Covers :func:`parse_filter_group` validation, every operator of every field
kind in :func:`build_filter_query`, the unhonourable-condition report, and the
index helpers the structured search relies on: :func:`facet_counts`,
:func:`field_values`, and sorted region and record searches.
"""

from typing import Any

import pytest
from bgc_viewer.search.document import OPERATORS_BY_KIND, SEARCH_FIELDS
from bgc_viewer.search.extraction import build_document
from bgc_viewer.search.index import (
    FacetBucket,
    FacetFieldError,
    QuerySyntaxError,
    Sort,
    UnknownFieldError,
    build_index,
    facet_counts,
    field_values,
    search_record,
    search_regions,
)
from bgc_viewer.search.query import (
    MAX_FILTER_CONDITIONS,
    MAX_FILTER_DEPTH,
    RAW_QUERY_FIELD,
    FilterCondition,
    FilterGroup,
    InvalidFilterError,
    UnhonourableFilterError,
    build_filter_query,
    parse_filter_group,
)


def _region(record: str, region: int, **values: Any) -> dict[str, list]:
    base: dict[str, list] = {
        "record": [record],
        "region": [region],
        "start": [region * 1000],
        "end": [region * 1000 + 500],
        "output_file": [f"out/{record}.json"],
    }
    base.update(
        {
            name: value if isinstance(value, list) else [value]
            for name, value in values.items()
        }
    )
    return base


REGIONS = [
    _region(
        "recA",
        1,
        organism="Streptomyces coelicolor A3(2)",
        product=["NRPS", "T1PKS"],
        product_category=["NRPS", "PKS"],
        length=30000,
        is_complete=True,
        substrates=["Leu", "Ser"],
        knowncluster_top_similarity=80,
        mibig_comparison_top_score=0.75,
        pfam=["PF00501", "PF00550"],
    ),
    _region(
        "recA",
        2,
        organism="Streptomyces coelicolor A3(2)",
        product="lanthipeptide-class-i",
        product_category="RiPP",
        length=12000,
        is_complete=True,
        knowncluster_top_similarity=40,
        mibig_comparison_top_score=0.5,
        pfam="PF00501",
    ),
    _region(
        "recB",
        1,
        organism="Amycolatopsis mediterranei",
        product="terpene",
        product_category="terpene",
        length=21000,
        is_complete=False,
    ),
]


@pytest.fixture(scope="module")
def index():
    return build_index(build_document(values) for values in REGIONS)


def _filter(*conditions, operator="AND", groups=()) -> dict:
    return {
        "operator": operator,
        "conditions": list(conditions),
        "groups": list(groups),
    }


def _c(field: str, operator: str, value: Any = None) -> dict:
    return {"field": field, "operator": operator, "value": value}


def _matches(index, body: dict) -> set[tuple[str, int]]:
    query = build_filter_query(index, parse_filter_group(body))
    hits = search_regions(index, query, limit=50).hits
    return {(hit.fields["record"], hit.fields["region"]) for hit in hits}


A1, A2, B1 = ("recA", 1), ("recA", 2), ("recB", 1)
ALL = {A1, A2, B1}


class TestParseFilterGroup:
    def test_parses_nested_groups_and_ignores_extra_keys(self):
        group = parse_filter_group(
            {
                "id": "root",
                "operator": "OR",
                "conditions": [{"id": "c1", **_c("product", "in", ["NRPS", None])}],
                "groups": [_filter(_c("is_complete", "equals", True))],
            }
        )
        assert group == FilterGroup(
            "OR",
            (FilterCondition("product", "in", ("NRPS", None)),),
            (
                FilterGroup(
                    "AND", (FilterCondition("is_complete", "equals", "true"),), ()
                ),
            ),
        )

    def test_missing_keys_default_to_an_empty_and_group(self):
        assert parse_filter_group({}) == FilterGroup("AND", (), ())

    @pytest.mark.parametrize(
        "body",
        [
            [],
            {"operator": "XOR"},
            {"conditions": {}},
            {"groups": "x"},
            {"conditions": ["x"]},
            {"conditions": [{"field": 1, "operator": "equals"}]},
            {"conditions": [_c("product", "equals", {"a": 1})]},
            {"conditions": [_c("product", "in", [["nested"]])]},
            {"groups": [5]},
        ],
    )
    def test_malformed_filters_are_rejected(self, body):
        with pytest.raises(InvalidFilterError):
            parse_filter_group(body)

    def test_error_names_the_offending_path(self):
        with pytest.raises(
            InvalidFilterError, match=r"filter\.groups\[0\]\.conditions\[1\]"
        ):
            parse_filter_group(
                {"groups": [{"conditions": [_c("a", "equals", 1), "bad"]}]}
            )

    def test_depth_is_limited(self):
        body: dict = {}
        for _ in range(MAX_FILTER_DEPTH):
            body = {"groups": [body]}
        with pytest.raises(InvalidFilterError, match="deeper"):
            parse_filter_group(body)

    def test_condition_count_is_limited(self):
        conditions = [_c("product", "equals", "x")] * (MAX_FILTER_CONDITIONS + 1)
        with pytest.raises(InvalidFilterError, match="conditions"):
            parse_filter_group({"conditions": conditions})


class TestExactOperators:
    @pytest.mark.parametrize(
        "condition, expected",
        [
            (_c("product", "equals", "NRPS"), {A1}),
            (_c("product", "equals", "nrps"), set()),
            (_c("product", "not_equals", "NRPS"), {A2, B1}),
            (_c("product", "in", ["terpene", "T1PKS"]), {A1, B1}),
            (_c("product", "not_in", ["terpene", "T1PKS"]), {A2}),
            (_c("product", "contains", "PEPTIDE"), {A2}),
            (_c("product", "not_contains", "pks"), {A2, B1}),
            (_c("product", "starts_with", "lanthi"), {A2}),
            (_c("product", "ends_with", "class-I"), {A2}),
            (_c("organism", "contains", "A3(2)"), {A1, A2}),
            (_c("substrates", "exists"), {A1}),
            (_c("substrates", "not_exists"), {A2, B1}),
        ],
    )
    def test_operator(self, index, condition, expected):
        assert _matches(index, _filter(condition)) == expected


class TestNumericOperators:
    @pytest.mark.parametrize(
        "condition, expected",
        [
            (_c("length", "equals", 12000), {A2}),
            (_c("length", "equals", "12000"), {A2}),
            (_c("length", "equals", 12000.5), set()),
            (_c("length", "not_equals", 12000), {A1, B1}),
            (_c("length", "gt", 21000), {A1}),
            (_c("length", "gt", 20999.5), {A1, B1}),
            (_c("length", "gte", 21000), {A1, B1}),
            (_c("length", "lt", 21000), {A2}),
            (_c("length", "lte", 21000.5), {A2, B1}),
            (_c("length", "between", [12000, 21000]), {A2, B1}),
            (_c("length", "between", ["", 21000]), {A2, B1}),
            (_c("length", "between", [21000, None]), {A1, B1}),
            (_c("knowncluster_top_similarity", "not_exists"), {B1}),
            (_c("mibig_comparison_top_score", "gt", 0.5), {A1}),
            (_c("mibig_comparison_top_score", "gte", 0.5), {A1, A2}),
            (_c("mibig_comparison_top_score", "lt", 0.75), {A2}),
            (_c("mibig_comparison_top_score", "equals", 0.75), {A1}),
        ],
    )
    def test_operator(self, index, condition, expected):
        assert _matches(index, _filter(condition)) == expected


class TestBooleanOperators:
    @pytest.mark.parametrize(
        "value, expected",
        [(True, {A1, A2}), ("false", {B1}), ("yes", {A1, A2}), (0, {B1})],
    )
    def test_equals(self, index, value, expected):
        assert _matches(index, _filter(_c("is_complete", "equals", value))) == expected

    def test_not_equals(self, index):
        assert _matches(index, _filter(_c("is_complete", "not_equals", True))) == {B1}


class TestWordFields:
    def test_any_field_contains_matches_inside_words_without_case(self, index):
        assert _matches(index, _filter(_c("text", "contains", "COELI"))) == {A1, A2}

    def test_any_field_contains_needs_every_word(self, index):
        body = _filter(_c("text", "contains", "streptomyces lanthi"))
        assert _matches(index, body) == {A2}

    def test_any_field_not_contains(self, index):
        assert _matches(index, _filter(_c("text", "not_contains", "terpene"))) == {
            A1,
            A2,
        }

    def test_path_contains_matches_components(self, index):
        assert _matches(index, _filter(_c("output_file", "contains", "recb"))) == {B1}


class TestGroups:
    def test_empty_filter_matches_everything(self, index):
        assert _matches(index, _filter()) == ALL

    def test_blank_conditions_are_dropped(self, index):
        body = _filter(_c("product", "in", []), _c("organism", "equals", "  "))
        assert _matches(index, body) == ALL

    def test_and(self, index):
        body = _filter(_c("record", "equals", "recA"), _c("pfam", "equals", "PF00550"))
        assert _matches(index, body) == {A1}

    def test_or(self, index):
        body = _filter(
            _c("product", "equals", "terpene"),
            _c("length", "lt", 15000),
            operator="OR",
        )
        assert _matches(index, body) == {A2, B1}

    def test_negation_inside_or(self, index):
        body = _filter(
            _c("product", "not_equals", "NRPS"),
            _c("length", "equals", 30000),
            operator="OR",
        )
        assert _matches(index, body) == ALL

    def test_nested_group(self, index):
        body = _filter(
            _c("record", "equals", "recA"),
            groups=[
                _filter(
                    _c("product_category", "equals", "RiPP"),
                    _c("substrates", "equals", "Ser"),
                    operator="OR",
                )
            ],
        )
        assert _matches(index, body) == {A1, A2}


class TestRawQueryCondition:
    def test_runs_a_query_string(self, index):
        body = _filter(_c(RAW_QUERY_FIELD, "matches", "substrates:Leu OR terpene"))
        assert _matches(index, body) == {A1, B1}

    def test_combines_with_other_conditions(self, index):
        body = _filter(
            _c(RAW_QUERY_FIELD, "matches", "coelicolor"),
            _c("length", "lt", 20000),
        )
        assert _matches(index, body) == {A2}

    def test_parser_errors_propagate(self, index):
        with pytest.raises(QuerySyntaxError):
            _matches(index, _filter(_c(RAW_QUERY_FIELD, "matches", "pfam:(")))
        with pytest.raises(UnknownFieldError):
            _matches(index, _filter(_c(RAW_QUERY_FIELD, "matches", "nope:x")))


class TestUnhonourableConditions:
    def test_every_problem_is_reported_together(self, index):
        body = _filter(
            _c("nope", "equals", "x"),
            _c("length", "contains", "1"),
            groups=[_filter(_c("length", "gt", "abc"))],
        )
        with pytest.raises(UnhonourableFilterError) as raised:
            _matches(index, body)
        reasons = [(c.field, c.reason) for c in raised.value.conditions]
        assert reasons == [
            ("nope", "unknown_field"),
            ("length", "unsupported_operator"),
            ("length", "unusable_value"),
        ]
        assert (
            raised.value.conditions[1].supported_operators
            == OPERATORS_BY_KIND["numeric"]
        )
        assert 'operator "contains"' in str(raised.value)
        assert "without them" in str(raised.value)

    @pytest.mark.parametrize(
        "condition",
        [
            _c("is_complete", "equals", "maybe"),
            _c("text", "contains", "--"),
            _c("length", "between", ["x", "y"]),
            _c(RAW_QUERY_FIELD, "equals", "pfam:x"),
        ],
    )
    def test_unusable_condition(self, index, condition):
        with pytest.raises(UnhonourableFilterError):
            _matches(index, _filter(condition))

    def test_every_registered_operator_builds(self, index):
        for field in SEARCH_FIELDS:
            for operator in OPERATORS_BY_KIND[field.kind]:
                value = {
                    "numeric": [1, 2] if operator == "between" else 1,
                    "boolean": True,
                }.get(field.kind, "x")
                build_filter_query(
                    index, parse_filter_group(_filter(_c(field.name, operator, value)))
                )


class TestFacetCounts:
    def test_counts_values_over_matching_regions(self, index):
        query = build_filter_query(
            index, parse_filter_group(_filter(_c("record", "equals", "recA")))
        )
        facets = facet_counts(index, query, ["product_category", "is_complete"])
        assert sorted(facets["product_category"], key=lambda b: b.value) == [
            FacetBucket("NRPS", 1),
            FacetBucket("PKS", 1),
            FacetBucket("RiPP", 1),
        ]
        assert facets["is_complete"] == [FacetBucket("true", 2)]

    def test_size_limits_values(self, index):
        facets = facet_counts(index, "*", ["pfam"], size=1)
        assert facets["pfam"] == [FacetBucket("PF00501", 2)]

    def test_rejects_fields_that_cannot_be_counted(self, index):
        with pytest.raises(FacetFieldError):
            facet_counts(index, "recA", ["length"])
        with pytest.raises(UnknownFieldError):
            facet_counts(index, "recA", ["nope"])


class TestFieldValues:
    def test_prefix_matches_rank_first(self, index):
        values = field_values(index, "product", "pks")
        assert [bucket.value for bucket in values] == ["T1PKS"]
        values = field_values(index, "product", "t")
        assert [bucket.value for bucket in values][:2] == ["T1PKS", "terpene"]

    def test_counts_cover_the_whole_index(self, index):
        assert field_values(index, "pfam", "PF005") == [
            FacetBucket("PF00501", 2),
            FacetBucket("PF00550", 1),
        ]

    def test_size_limits_values(self, index):
        assert len(field_values(index, "product", size=2)) == 2

    def test_special_characters_are_literal(self, index):
        assert field_values(index, "organism", "A3(2") == [
            FacetBucket("Streptomyces coelicolor A3(2)", 2)
        ]

    def test_rejects_fields_that_cannot_be_counted(self, index):
        with pytest.raises(FacetFieldError):
            field_values(index, "text", "x")


class TestSorting:
    def test_regions_sort_by_field_without_scores(self, index):
        everything = build_filter_query(index, parse_filter_group(_filter()))
        ascending = search_regions(index, everything, sort=Sort("length"))
        assert [hit.fields["region"] for hit in ascending.hits] == [2, 1, 1]
        assert all(hit.score is None for hit in ascending.hits)
        descending = search_regions(index, everything, sort=Sort("length", True))
        assert [hit.fields["record"] for hit in descending.hits] == [
            "recA",
            "recB",
            "recA",
        ]

    def test_records_follow_their_first_region(self, index):
        everything = build_filter_query(index, parse_filter_group(_filter()))
        result = search_record(index, everything, sort=Sort("length", True))
        assert [hit.record for hit in result.hits] == ["recA", "recB"]
        assert result.total_regions == 3
