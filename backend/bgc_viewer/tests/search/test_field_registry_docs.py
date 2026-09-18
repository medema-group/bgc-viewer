"""Hygiene guard for the search-field registry.

This test guards the registry itself rather than search behavior, which is why it
lives on its own instead of in the Stage 2 behavior suites. It fails when a
definition in :mod:`bgc_viewer.search.document` is internally inconsistent, is
rejected by the ``tantivy`` schema builder, or is missing the user-facing
description that the help popup and
``docs/guide/development/search-index.md`` depend on.

The registry is documented as the single source of truth for public search
fields, so every field has to be well-formed here before it can reach a query.
"""

import json

import pytest
from tantivy import SchemaBuilder

from bgc_viewer.search.document import SEARCH_FIELD_REGISTRY
from bgc_viewer.search.index import _ANALYZERS, _add_field

VALID_VALUE_TYPES = frozenset({"text", "keyword", "numeric"})
VALID_CARDINALITIES = frozenset({"single", "multi"})


@pytest.mark.parametrize("definition", SEARCH_FIELD_REGISTRY, ids=lambda d: d.name)
def test_field_name_is_non_empty(definition):
    assert definition.name.strip()


def test_field_names_are_unique():
    names = [definition.name for definition in SEARCH_FIELD_REGISTRY]
    assert len(set(names)) == len(names)


@pytest.mark.parametrize("definition", SEARCH_FIELD_REGISTRY, ids=lambda d: d.name)
def test_value_type_is_registered(definition):
    assert definition.value_type in VALID_VALUE_TYPES


@pytest.mark.parametrize("definition", SEARCH_FIELD_REGISTRY, ids=lambda d: d.name)
def test_cardinality_is_registered(definition):
    assert definition.cardinality in VALID_CARDINALITIES


@pytest.mark.parametrize("definition", SEARCH_FIELD_REGISTRY, ids=lambda d: d.name)
def test_analyzer_is_consistent_with_value_type(definition):
    """Numeric fields carry no analyzer; every other field names a registered one.

    ``public_kind`` classifies a field by analyzer for text and by value type for
    numeric, so a text field without an analyzer has no user-facing kind.
    """
    if definition.value_type == "numeric":
        assert definition.analyzer is None
    else:
        assert definition.analyzer is not None
        assert definition.analyzer in _ANALYZERS


@pytest.mark.parametrize("definition", SEARCH_FIELD_REGISTRY, ids=lambda d: d.name)
def test_numeric_fields_are_excluded_from_unqualified_search(definition):
    if definition.value_type == "numeric":
        assert definition.default_search is False


@pytest.mark.parametrize("definition", SEARCH_FIELD_REGISTRY, ids=lambda d: d.name)
def test_boost_is_positive(definition):
    assert definition.boost > 0


@pytest.mark.parametrize("definition", SEARCH_FIELD_REGISTRY, ids=lambda d: d.name)
def test_description_is_non_empty_plain_prose(definition):
    """The description is rendered verbatim in the browser help popup.

    RST or Markdown code markup would be shown literally there, so descriptions
    carry plain prose only.
    """
    description = definition.description.strip()
    assert description
    assert "``" not in description


@pytest.mark.parametrize("definition", SEARCH_FIELD_REGISTRY, ids=lambda d: d.name)
def test_tantivy_schema_builder_accepts_field(definition):
    builder = SchemaBuilder()
    _add_field(builder, definition)
    assert builder.build() is not None


def test_every_registered_field_reaches_the_built_index(tmp_path):
    from bgc_viewer.search.index import build_index

    build_index(iter(()), tmp_path / "tantivy.index")

    meta = json.loads(
        (tmp_path / "tantivy.index" / "meta.json").read_text(encoding="utf-8")
    )
    schema_names = {field["name"] for field in meta["schema"]}
    assert schema_names == {d.name for d in SEARCH_FIELD_REGISTRY}
