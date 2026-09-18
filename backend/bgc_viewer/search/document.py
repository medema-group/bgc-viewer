"""Canonical search documents and antiSMASH location parsing."""

import re
from dataclasses import dataclass, field
from typing import Literal, Mapping

SEARCH_SCHEMA_VERSION = 2

FieldValueType = Literal["text", "keyword", "numeric"]
FieldCardinality = Literal["single", "multi"]
FieldAnalyzer = Literal["full_text", "exact"]

# User-facing field kind. Derived from the analyzer for text fields and from
# the value type for numeric fields, so the help popup can tell a searcher
# whether a field matches exactly, as full text, or as a number.
FieldKind = Literal["exact", "full_text", "numeric"]


@dataclass(frozen=True)
class SearchFieldDefinition:
    name: str
    description: str
    attribute: str
    value_type: FieldValueType
    cardinality: FieldCardinality
    analyzer: FieldAnalyzer | None
    returned: bool
    default_search: bool
    boost: float
    required: bool
    # Query-time tolerance. ``prefix_matches`` makes a term that is a prefix of an
    # indexed term match, and ``fuzzy_distance`` is the maximum Levenshtein
    # distance at which a term still matches, with a transposition of two
    # neighbouring characters counting as one. Both are applied by the query
    # parser rather than the index, so changing them does not alter the stored
    # Tantivy schema and does not bump SEARCH_SCHEMA_VERSION.
    #
    # They are deliberately left off identifier fields such as ``pfam``, whose
    # whole value is the lookup key: a prefix or typo-tolerant hit on an accession
    # is not a meaningful answer.
    prefix_matches: bool = False
    fuzzy_distance: int = 0


SEARCH_FIELD_REGISTRY: tuple[SearchFieldDefinition, ...] = (
    SearchFieldDefinition(
        name="pfam",
        description=(
            "PFAM accession of a PFAM_domain overlapping the protocluster, "
            "with the version suffix removed, so PF00512.28 is searched as "
            "PF00512."
        ),
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
        description=(
            "Description of a PFAM_domain overlapping the protocluster, from "
            "the domain's description qualifier."
        ),
        attribute="pfam_name",
        value_type="text",
        cardinality="multi",
        analyzer="full_text",
        returned=False,
        default_search=True,
        boost=1.0,
        required=False,
        prefix_matches=True,
        fuzzy_distance=1,
    ),
    SearchFieldDefinition(
        name="organism",
        description=(
            "Organism of the parent record, from the organism qualifier of its "
            "first source feature; empty when the record declares none."
        ),
        attribute="organism",
        value_type="text",
        cardinality="single",
        analyzer="full_text",
        returned=True,
        default_search=True,
        boost=1.0,
        required=False,
        prefix_matches=True,
        fuzzy_distance=1,
    ),
    SearchFieldDefinition(
        name="gene",
        description="Gene name of a gene feature overlapping the protocluster.",
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
        description=("Locus tag of a gene feature overlapping the protocluster."),
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
        description="Product of the protocluster, from its own product qualifier.",
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
        description=(
            "Product category of the protocluster, from its own "
            "product_category qualifier."
        ),
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
        description="antiSMASH record ID the protocluster belongs to.",
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
        description=(
            "Region number of the smallest region feature containing the "
            "protocluster."
        ),
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
        description="Protocluster number of the protocluster itself.",
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
        description=(
            "Lowest coordinate of the protocluster location, across every part "
            "of a compound location."
        ),
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
        description=(
            "Highest coordinate of the protocluster location, across every "
            "part of a compound location."
        ),
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
        description="Basename of the antiSMASH JSON file the protocluster was indexed from.",
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
        description=(
            "Input sequence filename antiSMASH reported for the source JSON; "
            "empty when absent."
        ),
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


def public_kind(definition: SearchFieldDefinition) -> FieldKind:
    """Map a registry entry onto the user-facing kind of a searchable field.

    Text fields report their analyzer; numeric fields have no analyzer and are
    reported by value type. A field that is neither is a registry error, so it
    raises rather than being silently classified.
    """
    if definition.value_type == "numeric":
        return "numeric"
    if definition.analyzer == "exact":
        return "exact"
    if definition.analyzer == "full_text":
        return "full_text"
    raise ValueError(f"Field {definition.name} has no user-facing kind")


@dataclass(frozen=True)
class PublicFieldInfo:
    """Public projection of one registry entry, as served to searchers.

    Cardinality and boosts are deliberately absent: they are internal indexing
    details. There is no storage flag because every registered field is stored;
    ``unqualified`` reports whether an unqualified term searches the field.
    """

    name: str
    kind: FieldKind
    unqualified: bool
    description: str


def public_field_metadata() -> tuple[PublicFieldInfo, ...]:
    """Project the registry onto public field metadata, in registry order."""
    return tuple(
        PublicFieldInfo(
            name=definition.name,
            kind=public_kind(definition),
            unqualified=definition.default_search,
            description=definition.description,
        )
        for definition in SEARCH_FIELD_REGISTRY
    )


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
