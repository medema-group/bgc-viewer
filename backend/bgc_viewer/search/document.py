import re
from dataclasses import dataclass, field


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
    serialized: str
    parts: tuple[LocationPart, ...] = field(init=False)

    def __post_init__(self) -> None:
        if _LOCATION_PATTERN.fullmatch(self.serialized) is None:
            raise ValueError(f"Invalid antiSMASH location: {self.serialized}")
        matches = re.findall(r"\[[<>]?(\d+):[<>]?(\d+)\]", self.serialized)
        parts = tuple(
            LocationPart(int(start), int(end)) for start, end in matches
        )
        if not parts or any(part.start >= part.end for part in parts):
            raise ValueError(f"Invalid antiSMASH location: {self.serialized}")
        object.__setattr__(self, "parts", parts)

    @classmethod
    def parse(cls, serialized: str) -> "Location":
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
    locus: tuple[str, ...]


@dataclass(frozen=True)
class ProtoclusterSearchDocument:
    source: SourceFile
    search_fields: SearchFields

    @property
    def document_key(self) -> str:
        fields = self.search_fields
        return (
            f"{self.source.source_path}:{fields.record_id}:"
            f"{fields.region_number}:{fields.protocluster_number}"
        )
