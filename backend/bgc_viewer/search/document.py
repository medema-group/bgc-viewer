"""Canonical search documents and antiSMASH location parsing."""

import re
from dataclasses import dataclass, field
from typing import ClassVar, Literal

SEARCH_SCHEMA_VERSION = 1

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
    stored: bool
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
        stored=False,
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
        stored=False,
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
        stored=True,
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
        stored=False,
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
        stored=False,
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
        stored=True,
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
        stored=True,
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
        stored=True,
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
        stored=True,
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
        stored=True,
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
        stored=True,
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
        stored=True,
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
        stored=True,
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
        stored=True,
        default_search=True,
        boost=2.0,
        required=False,
    ),
)

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
    registry: ClassVar[tuple[SearchFieldDefinition, ...]] = SEARCH_FIELD_REGISTRY

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
        for definition in self.search_fields.registry:
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
