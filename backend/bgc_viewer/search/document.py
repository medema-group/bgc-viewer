"""Search field metadata, antiSMASH location parsing, and example generation.

This module holds the data the search layer needs that is not itself the Tantivy
schema or the extraction code: the user-facing field descriptions served to the
help popup, the location parser, the path/escaping helpers shared with the index
tokenizer, and the runnable example-query templates.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Literal, Mapping

SEARCH_SCHEMA_VERSION = 1

# User-facing field kind reported to the help popup: whether a field matches
# exactly, as full text, as a path, or as a number. A ``path`` field keeps its
# whole value searchable while also splitting on ``/`` and ``.``, so a file path
# matches by directory, stem, or extension.
FieldKind = Literal["exact", "full_text", "path", "numeric"]


@dataclass(frozen=True)
class PublicFieldInfo:
    """One searchable field as served to searchers.

    Cardinality and boosts are deliberately absent: they are internal indexing
    details. ``unqualified`` reports whether an unqualified term searches the
    field.
    """

    name: str
    kind: FieldKind
    unqualified: bool
    description: str


# The public field list, in the order the help popup shows it. This is the single
# place the user-facing description of each field lives; the Tantivy schema in
# ``index.py`` and the extraction in ``extraction.py`` are kept in step with it
# by the tests rather than by a shared registry.
PUBLIC_FIELDS: tuple[PublicFieldInfo, ...] = (
    PublicFieldInfo(
        name="pfam",
        kind="exact",
        unqualified=True,
        description=(
            "PFAM accession of a PFAM_domain overlapping the protocluster, "
            "with the version suffix removed, so PF00512.28 is searched as "
            "PF00512."
        ),
    ),
    PublicFieldInfo(
        name="pfam_name",
        kind="full_text",
        unqualified=True,
        description=(
            "Description of a PFAM_domain overlapping the protocluster, from "
            "the domain's description qualifier."
        ),
    ),
    PublicFieldInfo(
        name="organism",
        kind="full_text",
        unqualified=True,
        description=(
            "Organism of the parent record, from the organism qualifier of its "
            "first source feature; empty when the record declares none."
        ),
    ),
    PublicFieldInfo(
        name="gene",
        kind="exact",
        unqualified=True,
        description="Gene name of a gene feature overlapping the protocluster.",
    ),
    PublicFieldInfo(
        name="locus",
        kind="exact",
        unqualified=True,
        description="Locus tag of a gene feature overlapping the protocluster.",
    ),
    PublicFieldInfo(
        name="product",
        kind="exact",
        unqualified=True,
        description="Product of the protocluster, from its own product qualifier.",
    ),
    PublicFieldInfo(
        name="category",
        kind="exact",
        unqualified=True,
        description=(
            "Product category of the protocluster, from its own "
            "product_category qualifier."
        ),
    ),
    PublicFieldInfo(
        name="record",
        kind="exact",
        unqualified=True,
        description="antiSMASH record ID the protocluster belongs to.",
    ),
    PublicFieldInfo(
        name="region",
        kind="numeric",
        unqualified=False,
        description=(
            "Region number of the smallest region feature containing the "
            "protocluster."
        ),
    ),
    PublicFieldInfo(
        name="protocluster",
        kind="numeric",
        unqualified=False,
        description="Protocluster number of the protocluster itself.",
    ),
    PublicFieldInfo(
        name="start",
        kind="numeric",
        unqualified=False,
        description=(
            "Lowest coordinate of the protocluster location, across every part "
            "of a compound location."
        ),
    ),
    PublicFieldInfo(
        name="end",
        kind="numeric",
        unqualified=False,
        description=(
            "Highest coordinate of the protocluster location, across every "
            "part of a compound location."
        ),
    ),
    PublicFieldInfo(
        name="output_file",
        kind="path",
        unqualified=True,
        description=(
            "Path of the antiSMASH JSON file the protocluster was indexed "
            "from, relative to the source directory that was indexed. "
            "Searched as a path: the whole value matches, and it also splits "
            "on / and ., so a directory, the file stem, or the extension "
            "each match on their own."
        ),
    ),
    PublicFieldInfo(
        name="input_file",
        kind="path",
        unqualified=True,
        description=(
            "Input sequence filename antiSMASH reported for the source JSON; "
            "empty when absent. Searched as a path: the whole value matches, "
            "and it also splits on / and ., so a directory, the file stem, "
            "or the extension each match on their own."
        ),
    ),
)


# Fields an unqualified term searches: every field except the numeric ones.
DEFAULT_SEARCH_FIELD_NAMES: tuple[str, ...] = tuple(
    info.name for info in PUBLIC_FIELDS if info.unqualified
)


# The characters a ``path`` field splits on: the directory separator and the
# extension separator. Declared here, rather than in the index module that
# builds the Tantivy tokenizer from them, so the example templates can strip
# a file extension the same way the index splits it and stay in step with it.
# Both must be safe to list inside a regex character class.
PATH_SEPARATORS = "/."
PATH_TOKENIZER_PATTERN = f"[^{PATH_SEPARATORS}]+"


def _path_components(value: str) -> list[str]:
    """The non-empty components a ``path`` field tokenizes ``value`` into."""
    return [part for part in re.split(f"[{PATH_SEPARATORS}]", value) if part]


def strip_path_extension(value: str) -> str:
    """Drop the file extension, i.e. the last separator-delimited component.

    ``nested/NC_003888.3.json`` becomes ``nested/NC_003888.3`` and
    ``Y16952.json`` becomes ``Y16952``. A value with no separator is
    returned unchanged.
    """
    for index in range(len(value) - 1, -1, -1):
        if value[index] in PATH_SEPARATORS:
            return value[:index]
    return value


# Characters Tantivy's query parser must not see inside a bare term. Mirrors
# ``ESCAPE_IN_WORD`` in tantivy-query-grammar, plus whitespace and a leading
# ``-`` (a leading hyphen is the negation operator). Everything else -- a
# mid-term ``-``, ``.``, ``/``, ``*``, ``?``, ``~`` -- is safe unquoted: the
# term text is passed through the field's analyzer, and Tantivy has no wildcard
# query (regex is gated behind ``allow_regexes``, which we disable).
_TANTIVY_ESCAPE_IN_WORD = frozenset("^`:{}\"'[]()\\")
_RESERVED_TERMS = frozenset({"OR", "AND", "NOT", "IN"})

ExampleValueFilter = Literal["any", "single_word", "multi_word", "path_prefix"]

_BARE_SAFE_PATTERN = re.compile(r"\w+", re.ASCII)


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


def _passes_value_filter(value: str, value_filter: ExampleValueFilter) -> bool:
    if value_filter == "single_word":
        return bool(_BARE_SAFE_PATTERN.fullmatch(value))
    if value_filter == "multi_word":
        return len(value.split()) >= 2
    if value_filter == "path_prefix":
        # A ``"a b"*`` prefix only parses when the quoted text tokenizes to at
        # least two terms, so the extension-stripped path must keep at least
        # two components -- a directory plus a stem, or a dotted stem.
        return len(_path_components(value)) >= 2
    return True


@dataclass(frozen=True)
class ExampleSlot:
    """One value placeholder consumed by an example template.

    ``candidates`` lists public field names in priority order; an empty tuple
    means every field that participates in unqualified search. ``value_filter``
    narrows which collected values the slot accepts, ``transform`` rewrites the
    selected value before it is filtered and rendered (used to drop a file
    extension for a path prefix), and ``quoted`` renders the value inside
    double quotes (for phrase templates) instead of the quote-when-needed
    rendering used for bare terms.
    """

    name: str
    candidates: tuple[str, ...]
    value_filter: ExampleValueFilter
    quoted: bool = False
    transform: Callable[[str], str] | None = None

    def select(self, values: Mapping[str, str]) -> tuple[str, str] | None:
        """Return the ``(field, value)`` this slot resolves to, or ``None``."""
        candidates = self.candidates or DEFAULT_SEARCH_FIELD_NAMES
        for name in candidates:
            collected = values.get(name)
            if not collected:
                continue
            value = self.transform(collected) if self.transform else collected
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


# The declared template set is rebuilt with the attributes database on every
# preprocessing run, so it carries no separate version number. The templates
# mirror the query shapes demonstrated by ``_CLI_EXAMPLES`` in
# ``bgc_viewer/search/cli.py``.
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
        template_id="path_prefix",
        # The extension is dropped from the collected path and the trailing
        # ``*`` makes the last component a prefix, so a searcher can match a
        # file by its stem without typing the (usually ``json``) extension.
        pattern='{path_field}:"{path_value}"*',
        slots=(
            ExampleSlot(
                name="path",
                candidates=("output_file", "input_file"),
                value_filter="path_prefix",
                quoted=True,
                transform=strip_path_extension,
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
    # Relative to the source root that was indexed, POSIX-style, so a file in a
    # nested directory is recorded as ``nesteddir/my.json`` rather than as a
    # machine-specific absolute path.
    output_file: str
    input_file: str
