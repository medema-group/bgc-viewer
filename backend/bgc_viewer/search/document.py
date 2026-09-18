"""Canonical search documents and antiSMASH location parsing."""

import re
from dataclasses import dataclass, field
from typing import Literal, Mapping

SEARCH_SCHEMA_VERSION = 2

FieldValueType = Literal["text", "keyword", "numeric"]
FieldCardinality = Literal["single", "multi"]
FieldAnalyzer = Literal["full_text", "exact"]


@dataclass(frozen=True)
class SearchFieldDefinition:
    name: str
    attribute: str
    value_type: FieldValueType
    cardinality: FieldCardinality
    analyzer: FieldAnalyzer | None
    returned: bool
    default_search: bool
    boost: float
    required: bool


SEARCH_FIELD_REGISTRY: tuple[SearchFieldDefinition, ...] = (
    SearchFieldDefinition(
        name="pfam",
        attribute="pfam",
        value_type="keyword",
        cardinality="multi",
        analyzer="exact",
        returned=False,
        default_search=True,
        boost=2.0,
        required=False,
    ),
    SearchFieldDefinition(
        name="pfam_name",
        attribute="pfam_name",
        value_type="text",
        cardinality="multi",
        analyzer="full_text",
        returned=False,
        default_search=True,
        boost=1.0,
        required=False,
    ),
    SearchFieldDefinition(
        name="organism",
        attribute="organism",
        value_type="text",
        cardinality="single",
        analyzer="full_text",
        returned=True,
        default_search=True,
        boost=1.0,
        required=False,
    ),
    SearchFieldDefinition(
        name="gene",
        attribute="gene",
        value_type="keyword",
        cardinality="multi",
        analyzer="exact",
        returned=False,
        default_search=True,
        boost=2.0,
        required=False,
    ),
    SearchFieldDefinition(
        name="locus",
        attribute="locus",
        value_type="keyword",
        cardinality="multi",
        analyzer="exact",
        returned=False,
        default_search=True,
        boost=2.0,
        required=False,
    ),
    SearchFieldDefinition(
        name="product",
        attribute="product",
        value_type="keyword",
        cardinality="single",
        analyzer="exact",
        returned=True,
        default_search=True,
        boost=2.0,
        required=True,
    ),
    SearchFieldDefinition(
        name="category",
        attribute="category",
        value_type="keyword",
        cardinality="single",
        analyzer="exact",
        returned=True,
        default_search=True,
        boost=2.0,
        required=True,
    ),
    SearchFieldDefinition(
        name="record",
        attribute="record_id",
        value_type="keyword",
        cardinality="single",
        analyzer="exact",
        returned=True,
        default_search=True,
        boost=2.0,
        required=True,
    ),
    SearchFieldDefinition(
        name="region",
        attribute="region_number",
        value_type="numeric",
        cardinality="single",
        analyzer=None,
        returned=True,
        default_search=False,
        boost=1.0,
        required=True,
    ),
    SearchFieldDefinition(
        name="protocluster",
        attribute="protocluster_number",
        value_type="numeric",
        cardinality="single",
        analyzer=None,
        returned=True,
        default_search=False,
        boost=1.0,
        required=True,
    ),
    SearchFieldDefinition(
        name="start",
        attribute="start",
        value_type="numeric",
        cardinality="single",
        analyzer=None,
        returned=True,
        default_search=False,
        boost=1.0,
        required=True,
    ),
    SearchFieldDefinition(
        name="end",
        attribute="end",
        value_type="numeric",
        cardinality="single",
        analyzer=None,
        returned=True,
        default_search=False,
        boost=1.0,
        required=True,
    ),
    SearchFieldDefinition(
        name="output_file",
        attribute="output_file",
        value_type="keyword",
        cardinality="single",
        analyzer="exact",
        returned=True,
        default_search=True,
        boost=2.0,
        required=True,
    ),
    SearchFieldDefinition(
        name="input_file",
        attribute="input_file",
        value_type="keyword",
        cardinality="single",
        analyzer="exact",
        returned=True,
        default_search=True,
        boost=2.0,
        required=False,
    ),
)

# Every registered field is stored in the Tantivy index so its value can be read
# back for example collection and diagnostics. The ``returned`` flag is the only
# storage-related decision: it selects which stored fields come back in ordinary
# search hits. PFAMs, PFAM names, genes, and locus tags are stored but are not
# returned in ordinary hits.

ExampleValueFilter = Literal["any", "single_word", "multi_word"]

_BARE_SAFE_PATTERN = re.compile(r"\w+", re.ASCII)

# Characters Tantivy's query parser must not see inside a bare term. Mirrors
# ``ESCAPE_IN_WORD`` in tantivy-query-grammar, plus whitespace and a leading
# ``-`` (a leading hyphen is the negation operator). Everything else -- a
# mid-term ``-``, ``.``, ``/``, ``*``, ``?``, ``~`` -- is safe unquoted: the
# term text is passed through the field's analyzer, and 0.26 has no wildcard
# query (regex is gated behind ``allow_regexes``, which we disable).
_TANTIVY_ESCAPE_IN_WORD = frozenset("^`:{}\"'[]()\\")
_RESERVED_TERMS = frozenset({"OR", "AND", "NOT", "IN"})


def _needs_quoting(value: str) -> bool:
    """Whether ``value`` cannot stand as a bare term in Tantivy's parser."""
    if not value or value in _RESERVED_TERMS:
        return True
    if value[0] == "-" or value[0] in _TANTIVY_ESCAPE_IN_WORD:
        return True
    return any(ch.isspace() or ch in _TANTIVY_ESCAPE_IN_WORD for ch in value)


def _escape_quoted(value: str) -> str:
    """Escape a value placed inside double quotes."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_term(value: str) -> str:
    """Render a value for a bare term position, quoting it only when needed.

    Tantivy accepts any character in a bare term except whitespace, the
    ``ESCAPE_IN_WORD`` set, and a leading ``-``, so values like ``hglE-KS``
    stay unquoted. Anything that would break parsing is wrapped in double
    quotes with embedded quotes and backslashes escaped.
    """
    if not _needs_quoting(value):
        return value
    return f'"{_escape_quoted(value)}"'


def _default_search_field_names() -> tuple[str, ...]:
    return tuple(
        definition.name
        for definition in SEARCH_FIELD_REGISTRY
        if definition.default_search
    )


def _passes_value_filter(value: str, value_filter: ExampleValueFilter) -> bool:
    if value_filter == "single_word":
        return bool(_BARE_SAFE_PATTERN.fullmatch(value))
    if value_filter == "multi_word":
        return len(value.split()) >= 2
    return True


@dataclass(frozen=True)
class ExampleSlot:
    """One value placeholder consumed by an example template.

    ``candidates`` lists public field names in priority order; an empty tuple
    means every field that participates in unqualified search. ``value_filter``
    narrows which collected values the slot accepts, and ``quoted`` renders the
    value inside double quotes (for phrase templates) instead of the
    quote-when-needed rendering used for bare terms.
    """

    name: str
    candidates: tuple[str, ...]
    value_filter: ExampleValueFilter
    quoted: bool = False

    def select(self, values: Mapping[str, str]) -> tuple[str, str] | None:
        """Return the ``(field, value)`` this slot resolves to, or ``None``."""
        candidates = self.candidates or _default_search_field_names()
        for name in candidates:
            value = values.get(name)
            if value and _passes_value_filter(value, self.value_filter):
                return name, value
        return None


@dataclass(frozen=True)
class ExampleTemplate:
    """A runnable example query shape built from collected field values.

    ``pattern`` is a ``str.format`` template whose placeholders are filled from
    the value each slot resolves to: ``{slot}_field`` is the public field name
    the value came from and ``{slot}_value`` is the escaped value. The template
    is instantiable only when every slot resolves to a value.
    """

    template_id: str
    pattern: str
    slots: tuple[ExampleSlot, ...]

    def instantiate(self, values: Mapping[str, str]) -> str | None:
        """Return the runnable query, or ``None`` if a slot cannot be filled."""
        context: dict[str, str] = {}
        for slot in self.slots:
            selected = slot.select(values)
            if selected is None:
                return None
            name, value = selected
            context[f"{slot.name}_field"] = name
            context[f"{slot.name}_value"] = (
                _escape_quoted(value) if slot.quoted else _escape_term(value)
            )
        return self.pattern.format(**context)


# The declared registry is the version of the example set: it is rebuilt with
# the attributes database on every preprocessing run, so it carries no
# separate version number. The templates mirror the query shapes demonstrated
# by ``_CLI_EXAMPLES`` in ``bgc_viewer/search/cli.py``.
EXAMPLE_TEMPLATE_REGISTRY: tuple[ExampleTemplate, ...] = (
    ExampleTemplate(
        template_id="unqualified_word",
        pattern="{word_value}",
        slots=(ExampleSlot(name="word", candidates=(), value_filter="single_word"),),
    ),
    ExampleTemplate(
        template_id="fielded_word",
        pattern="{term_field}:{term_value}",
        slots=(
            ExampleSlot(
                name="term",
                candidates=("category", "product"),
                value_filter="single_word",
            ),
        ),
    ),
    ExampleTemplate(
        template_id="quoted_phrase",
        pattern='"{phrase_value}"',
        slots=(
            ExampleSlot(
                name="phrase",
                candidates=("organism", "pfam_name"),
                value_filter="multi_word",
                quoted=True,
            ),
        ),
    ),
    ExampleTemplate(
        template_id="and_fields",
        pattern="{left_field}:{left_value} AND {right_field}:{right_value}",
        slots=(
            ExampleSlot(name="left", candidates=("category",), value_filter="any"),
            ExampleSlot(name="right", candidates=("product",), value_filter="any"),
        ),
    ),
    ExampleTemplate(
        template_id="negation",
        pattern="{left_field}:{left_value} NOT {right_field}:{right_value}",
        slots=(
            ExampleSlot(name="left", candidates=("organism",), value_filter="any"),
            ExampleSlot(name="right", candidates=("product",), value_filter="any"),
        ),
    ),
)


def generate_example_queries(values: Mapping[str, str]) -> list[tuple[str, str]]:
    """Return ``(template_id, query)`` rows in deterministic template order.

    A template is omitted when any of its slots cannot be filled from the
    collected first values, so a corpus missing a required value simply yields
    fewer examples.
    """
    rows: list[tuple[str, str]] = []
    for template in EXAMPLE_TEMPLATE_REGISTRY:
        query = template.instantiate(values)
        if query is not None:
            rows.append((template.template_id, query))
    return rows


_SIMPLE_LOCATION_PATTERN = r"\[[<>]?\d+:[<>]?\d+\](?:\([+\-?]\))?"
_LOCATION_PATTERN = re.compile(
    rf"(?:{_SIMPLE_LOCATION_PATTERN}|[A-Za-z_]+\{{{_SIMPLE_LOCATION_PATTERN}"
    rf"(?:, {_SIMPLE_LOCATION_PATTERN})+\}})"
)


@dataclass(frozen=True)
class LocationPart:
    start: int
    end: int


@dataclass(frozen=True)
class Location:
    """A parsed antiSMASH feature location.

    ``parse`` accepts a simple ``[start:end](strand)`` location such as
    ``[200:700](+)``. Either bound may be fuzzy, as in
    ``[<900:>1000](-)``, and the strand suffix may be omitted. The strand
    may be ``+``, ``-``, or ``?``.

    Compound locations contain two or more comma-separated simple locations
    under an operator, for example
    ``join{[<900:1000](+), [0:>200](+)}``.

    Parsing validates the complete serialized value, then captures the numeric
    bounds from each simple location as ``LocationPart`` instances. Fuzzy
    markers and compound operators remain available in ``serialized`` while
    ``parts``, ``start``, and ``end`` support interval comparisons.
    """

    serialized: str
    parts: tuple[LocationPart, ...] = field(init=False)

    def __post_init__(self) -> None:
        if _LOCATION_PATTERN.fullmatch(self.serialized) is None:
            raise ValueError(f"Invalid antiSMASH location: {self.serialized}")
        matches = re.findall(r"\[[<>]?(\d+):[<>]?(\d+)\]", self.serialized)
        parts = tuple(LocationPart(int(start), int(end)) for start, end in matches)
        if not parts or any(part.start >= part.end for part in parts):
            raise ValueError(f"Invalid antiSMASH location: {self.serialized}")
        object.__setattr__(self, "parts", parts)

    @classmethod
    def parse(cls, serialized: str) -> "Location":
        """Parse an antiSMASH location such as ``[200:700](+)``."""
        return cls(serialized)

    @property
    def start(self) -> int:
        return min(part.start for part in self.parts)

    @property
    def end(self) -> int:
        return max(part.end for part in self.parts)

    def overlaps(self, other: "Location") -> bool:
        return any(
            left.start < right.end and right.start < left.end
            for left in self.parts
            for right in other.parts
        )

    def contains(self, other: "Location") -> bool:
        return all(
            any(
                outer.start <= inner.start and inner.end <= outer.end
                for outer in self.parts
            )
            for inner in other.parts
        )


@dataclass(frozen=True)
class SourceFile:
    antismash_version: str
    source_path: str
    output_file: str
    input_file: str


@dataclass(frozen=True)
class SearchFields:
    record_id: str
    region_number: int
    protocluster_number: int
    location: Location
    product: str
    category: str
    organism: str
    pfam: tuple[str, ...]
    pfam_name: tuple[str, ...]
    gene: tuple[str, ...]
    # TODO locus is too generic it is used as genbank root level, rename to gene_locus?
    locus: tuple[str, ...]

    @property
    def start(self) -> int:
        return self.location.start

    @property
    def end(self) -> int:
        return self.location.end


@dataclass(frozen=True)
class ProtoclusterSearchDocument:
    source: SourceFile
    search_fields: SearchFields

    def __post_init__(self) -> None:
        for definition in SEARCH_FIELD_REGISTRY:
            value = self.field_value(definition)
            if definition.cardinality == "multi":
                if not isinstance(value, tuple):
                    raise TypeError(f"Field {definition.name} must be multi-valued")
                if any(not isinstance(item, str) or not item for item in value):
                    raise ValueError(f"Field {definition.name} contains an empty value")
                if len(value) != len(set(value)):
                    raise ValueError(f"Field {definition.name} contains duplicates")
            elif definition.value_type == "numeric":
                if not isinstance(value, int) or isinstance(value, bool):
                    raise TypeError(f"Field {definition.name} must be numeric")
            elif not isinstance(value, str):
                raise TypeError(f"Field {definition.name} must be a string")

            if definition.required and (value == "" or value == ()):
                raise ValueError(f"Field {definition.name} is required")

    def field_value(self, definition: SearchFieldDefinition) -> object:
        if hasattr(self.search_fields, definition.attribute):
            return getattr(self.search_fields, definition.attribute)
        return getattr(self.source, definition.attribute)

    @property
    def document_key(self) -> str:
        fields = self.search_fields
        return (
            f"{self.source.source_path}:{fields.record_id}:"
            f"{fields.region_number}:{fields.protocluster_number}"
        )
