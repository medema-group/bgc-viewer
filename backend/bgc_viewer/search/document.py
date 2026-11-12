"""Search field registry, antiSMASH location parsing, and example generation.

This module holds the single field registry (``SEARCH_FIELDS``) from which the
Tantivy schema and query config in ``index.py`` and the public help metadata
(``PUBLIC_FIELDS``) are projected, plus the location parser, the path/escaping
helpers shared with the index tokenizer, and the runnable example-query
templates.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

SEARCH_SCHEMA_VERSION = 2

# User-facing field kind reported to the help popup: whether a field matches
# exactly, as full text, as a path, as a number, or as a yes/no value. A
# ``path`` field keeps its whole value searchable while also splitting on ``/``
# and ``.``, so a file path matches by directory, stem, or extension.
FieldKind = Literal["exact", "full_text", "path", "numeric", "boolean"]

# Field type -> public field kind. ``raw`` indexes the whole value as one
# case-sensitive token, ``default`` tokenizes words with lowercase
# normalization, ``path`` is the custom path tokenizer, ``integer`` and
# ``float`` are numbers, and ``boolean`` is a yes/no value. The public kind,
# whether a bare term searches the field, and how the field is built in the
# Tantivy schema are all derived from this single name.
_TOKENIZER_KINDS: dict[str, FieldKind] = {
    "raw": "exact",
    "default": "full_text",
    "path": "path",
    "integer": "numeric",
    "float": "numeric",
    "boolean": "boolean",
}

# Field types whose values are text, as opposed to numbers and booleans.
TEXT_TOKENIZERS = frozenset({"raw", "default", "path"})

# The catch-all full-text field. Every text value of a region whose field sets
# ``in_text`` is also indexed here word by word, so a bare word matches inside
# any field, including exact fields whose whole value it does not equal. It is
# indexed only: its content is a copy of other fields.
TEXT_FIELD = "text"


@dataclass(frozen=True)
class SearchField:
    """One searchable field, declared once and projected everywhere.

    ``tokenizer`` is the field type: a Tantivy tokenizer name for text
    (``raw``, ``default``, or ``path``) or ``integer``, ``float``, or
    ``boolean``. The public ``kind`` and whether a bare term searches the field
    (``default_search``) are derived from it. ``label`` and ``group`` name the
    field and its section for display. ``multi`` reports whether a region can
    hold several values, which are then returned as a list. ``boost`` is the
    query-time relevance weight, or ``None`` when the field is not boosted.
    ``in_hits`` reports whether the stored value comes back in ordinary hits.
    ``in_text`` reports whether a text field's values are copied into the
    catch-all :data:`TEXT_FIELD`; sequences and SMILES are not, as they hold no
    words, and neither are paths, which a bare term already searches by
    component. ``stored`` is false only for that catch-all field. ``description``
    is the user-facing help text.
    """

    name: str
    tokenizer: str
    label: str
    group: str
    description: str
    multi: bool = False
    boost: float | None = None
    in_hits: bool = False
    in_text: bool = True
    stored: bool = True

    @property
    def kind(self) -> FieldKind:
        return _TOKENIZER_KINDS[self.tokenizer]

    @property
    def default_search(self) -> bool:
        return self.tokenizer in TEXT_TOKENIZERS

    @property
    def is_text(self) -> bool:
        return self.tokenizer in TEXT_TOKENIZERS


@dataclass(frozen=True)
class PublicFieldInfo:
    """One searchable field as served to searchers.

    Internal indexing details (tokenizer, boost, and in-hits status) are
    deliberately absent; this is the public projection of a :class:`SearchField`.
    ``default_search`` reports whether a bare term searches the field.
    """

    name: str
    kind: FieldKind
    label: str
    group: str
    multi: bool
    default_search: bool
    description: str


GROUP_GENERAL = "General"
GROUP_REGION = "Region"
GROUP_SOURCE = "Source"
GROUP_GENES = "Genes"
GROUP_FUNCTIONAL = "Functional hits"
GROUP_NRPS_PKS = "NRPS/PKS"
GROUP_TERPENE = "Terpene"
GROUP_RIPP = "RiPP"
GROUP_COMPARATIVE = "Comparative"
GROUP_REGULATION = "Regulation"


def _keyword(
    name: str, label: str, group: str, description: str, **options
) -> SearchField:
    """An exact, multi-valued text field, boosted like the other exact fields."""
    return SearchField(
        name=name,
        tokenizer="raw",
        label=label,
        group=group,
        description=description,
        multi=options.pop("multi", True),
        boost=options.pop("boost", 2.0),
        **options,
    )


def _sequence(name: str, label: str, group: str, description: str) -> SearchField:
    """An exact text field holding sequences or SMILES rather than words."""
    return SearchField(
        name=name,
        tokenizer="raw",
        label=label,
        group=group,
        description=description,
        multi=True,
        boost=2.0,
        in_text=False,
    )


def _number(
    name: str, label: str, group: str, description: str, **options
) -> SearchField:
    return SearchField(
        name=name,
        tokenizer=options.pop("tokenizer", "integer"),
        label=label,
        group=group,
        description=description,
        **options,
    )


# The single field registry: every searchable field, in schema and display
# order, declared in one place. The Tantivy schema and query config in
# ``index.py`` and the public help metadata below are projected from it rather
# than repeated. One document is one antiSMASH region; a field described as
# "in the region" collects every value found within the region's location.
# The extraction in ``extraction.py`` and ``facets.py`` is kept in step with it
# by the tests. Names follow the BGC Atlas facet names where both have a field.
SEARCH_FIELDS: tuple[SearchField, ...] = (
    SearchField(
        name=TEXT_FIELD,
        tokenizer="default",
        label="Any text",
        group=GROUP_GENERAL,
        description=(
            "Every text value of the region, except sequences and SMILES, "
            "searched word by word without regard to case."
        ),
        boost=1.0,
        in_text=False,
        stored=False,
    ),
    # Region
    _keyword(
        "record",
        "Record",
        GROUP_REGION,
        "antiSMASH record ID the region belongs to.",
        multi=False,
        in_hits=True,
    ),
    _number(
        "region",
        "Region number",
        GROUP_REGION,
        "Region number of the region within its record.",
        in_hits=True,
    ),
    _number(
        "start",
        "Start",
        GROUP_REGION,
        (
            "Lowest coordinate of the region location, across every part of a "
            "compound location."
        ),
        in_hits=True,
    ),
    _number(
        "end",
        "End",
        GROUP_REGION,
        (
            "Highest coordinate of the region location, across every part of "
            "a compound location."
        ),
        in_hits=True,
    ),
    _number(
        "length",
        "Length (bp)",
        GROUP_REGION,
        "Length of the region, summed over the parts of a compound location.",
    ),
    _keyword(
        "product",
        "Product",
        GROUP_REGION,
        "Product of a protocluster in the region.",
        in_hits=True,
    ),
    _keyword(
        "product_category",
        "Category",
        GROUP_REGION,
        (
            "Product category of a protocluster in the region, from its "
            "product_category qualifier."
        ),
        in_hits=True,
    ),
    _number(
        "num_protoclusters",
        "# Protoclusters",
        GROUP_REGION,
        "Number of protoclusters in the region.",
    ),
    _keyword(
        "candidate_kind",
        "Candidate cluster kind",
        GROUP_REGION,
        (
            "Kind of a candidate cluster in the region: single, "
            "chemical_hybrid, interleaved, or neighbouring."
        ),
    ),
    _keyword(
        "detection_rules",
        "Detection rule",
        GROUP_REGION,
        "Detection rule that triggered a protocluster in the region.",
    ),
    SearchField(
        name="is_complete",
        tokenizer="boolean",
        label="Complete (not on contig edge)",
        group=GROUP_REGION,
        description=(
            "Whether the region lies wholly within its record: false when "
            "antiSMASH marks it as being on a contig edge."
        ),
    ),
    # Source
    SearchField(
        name="organism",
        tokenizer="raw",
        label="Organism",
        group=GROUP_SOURCE,
        description=(
            "Organism of the parent record, from the organism qualifier of its "
            "first source feature; empty when the record declares none."
        ),
        boost=2.0,
        in_hits=True,
    ),
    SearchField(
        name="output_file",
        tokenizer="path",
        label="antiSMASH file",
        group=GROUP_SOURCE,
        description=(
            "Path of the antiSMASH JSON file the region was indexed from, "
            "relative to the source directory that was indexed. Searched as a "
            "path: the whole value matches, and it also splits on / and ., so "
            "a directory, the file stem, or the extension each match on their "
            "own."
        ),
        boost=2.0,
        in_hits=True,
        in_text=False,
    ),
    SearchField(
        name="input_file",
        tokenizer="path",
        label="Input file",
        group=GROUP_SOURCE,
        description=(
            "Input sequence filename antiSMASH reported for the source JSON; "
            "empty when absent. Searched as a path: the whole value matches, "
            "and it also splits on / and ., so a directory, the file stem, or "
            "the extension each match on their own."
        ),
        boost=2.0,
        in_hits=True,
        in_text=False,
    ),
    # Genes
    _keyword(
        "gene",
        "Gene name",
        GROUP_GENES,
        "Gene name of a gene feature overlapping the region.",
    ),
    _keyword(
        "locus",
        "Locus tag",
        GROUP_GENES,
        "Locus tag of a gene feature overlapping the region.",
    ),
    _number(
        "num_cds_features",
        "# Genes",
        GROUP_GENES,
        "Number of CDS features overlapping the region.",
    ),
    _number(
        "n_core_biosynthetic",
        "Core biosynthetic genes",
        GROUP_GENES,
        "Number of CDS features in the region whose gene kind is biosynthetic.",
    ),
    _number(
        "n_additional_biosynthetic",
        "Additional biosynthetic genes",
        GROUP_GENES,
        (
            "Number of CDS features in the region whose gene kind is "
            "biosynthetic-additional."
        ),
    ),
    _number(
        "n_transport",
        "Transport genes",
        GROUP_GENES,
        "Number of CDS features in the region whose gene kind is transport.",
    ),
    _number(
        "n_regulatory",
        "Regulatory genes",
        GROUP_GENES,
        "Number of CDS features in the region whose gene kind is regulatory.",
    ),
    _number(
        "n_resistance",
        "Resistance genes",
        GROUP_GENES,
        "Number of CDS features in the region whose gene kind is resistance.",
    ),
    # Functional hits
    _keyword(
        "pfam",
        "PFAM",
        GROUP_FUNCTIONAL,
        (
            "PFAM accession of a PFAM_domain feature or a cluster_hmmer hit "
            "overlapping the region, with the version suffix removed, so "
            "PF00512.28 is searched as PF00512."
        ),
    ),
    _keyword(
        "pfam_desc",
        "PFAM domain (name)",
        GROUP_FUNCTIONAL,
        "Description of a PFAM domain overlapping the region.",
    ),
    _keyword(
        "tigrfam",
        "TIGRFAM",
        GROUP_FUNCTIONAL,
        "TIGRFAM accession of a TIGRFAM hit in the region.",
    ),
    _keyword(
        "tigrfam_desc",
        "TIGRFAM domain (name)",
        GROUP_FUNCTIONAL,
        "Description of a TIGRFAM hit in the region.",
    ),
    _keyword(
        "smcog",
        "smCoG",
        GROUP_FUNCTIONAL,
        "smCoG of a gene in the region, from its best smCoG hit.",
    ),
    _keyword(
        "smcog_desc",
        "smCoG (name)",
        GROUP_FUNCTIONAL,
        "Description of the best smCoG hit of a gene in the region.",
    ),
    _keyword(
        "go_terms",
        "GO term",
        GROUP_FUNCTIONAL,
        "GO term mapped by pfam2go from a PFAM accession of the region.",
    ),
    _keyword(
        "antismash_domains",
        "antiSMASH domain",
        GROUP_FUNCTIONAL,
        "NRPS/PKS domain HMM hit on a gene in the region.",
    ),
    _number(
        "tta_codons",
        "# TTA codons",
        GROUP_FUNCTIONAL,
        "Number of TTA codons starting within the region.",
    ),
    # NRPS/PKS
    _keyword(
        "substrates",
        "A-domain substrate",
        GROUP_NRPS_PKS,
        "Predicted substrate of an adenylation domain in the region.",
    ),
    _keyword(
        "monomers",
        "Monomer",
        GROUP_NRPS_PKS,
        "Consensus monomer predicted for an NRPS/PKS domain in the region.",
    ),
    _keyword(
        "module_signatures",
        "Module signature",
        GROUP_NRPS_PKS,
        (
            "Domains of an NRPS/PKS module in the region, joined with -, such "
            "as Condensation_LCL-AMP-binding-PCP."
        ),
    ),
    _number(
        "num_modules",
        "# Modules",
        GROUP_NRPS_PKS,
        "Number of NRPS/PKS modules in the region.",
    ),
    _keyword(
        "stachelhaus_codes",
        "Stachelhaus code",
        GROUP_NRPS_PKS,
        "Stachelhaus signature of an adenylation domain in the region.",
    ),
    _keyword(
        "at_specificity",
        "AT specificity",
        GROUP_NRPS_PKS,
        "Top predicted substrate of an acyltransferase domain in the region.",
    ),
    _keyword(
        "kr_stereochemistry",
        "KR stereochemistry",
        GROUP_NRPS_PKS,
        "Predicted stereochemistry of a ketoreductase domain in the region.",
    ),
    SearchField(
        name="pks_trans_at",
        tokenizer="boolean",
        label="trans-AT PKS",
        group=GROUP_NRPS_PKS,
        description=(
            "Whether the region has a transAT-PKS product or a trans-AT "
            "domain; absent when the NRPS/PKS analysis did not run."
        ),
    ),
    _sequence(
        "predicted_smiles",
        "Predicted SMILES",
        GROUP_NRPS_PKS,
        "SMILES of a predicted NRPS/PKS product of the region.",
    ),
    _sequence(
        "monomer_consensus",
        "Monomer consensus",
        GROUP_NRPS_PKS,
        "Predicted NRPS/PKS polymer of the region, as a monomer sequence.",
    ),
    _keyword(
        "pks_t2_class",
        "PKS type II class",
        GROUP_NRPS_PKS,
        "Predicted product class of a type II PKS protocluster in the region.",
    ),
    _keyword(
        "pks_t2_starter",
        "PKS type II starter",
        GROUP_NRPS_PKS,
        "Predicted starter unit of a type II PKS protocluster in the region.",
    ),
    _keyword(
        "pks_t2_elongation",
        "PKS type II elongation",
        GROUP_NRPS_PKS,
        "Predicted elongation of a type II PKS protocluster in the region.",
    ),
    # Terpene
    _keyword(
        "terpene_products",
        "Terpene product",
        GROUP_TERPENE,
        "Predicted product of a terpene protocluster in the region.",
    ),
    _keyword(
        "terpene_domains",
        "Terpene domain",
        GROUP_TERPENE,
        "Domain type of a terpene enzyme in the region.",
    ),
    # RiPP
    _keyword(
        "ripp_class",
        "RiPP class",
        GROUP_RIPP,
        "Peptide class of a RiPP precursor in the region.",
    ),
    _keyword(
        "ripp_subclass",
        "RiPP subclass",
        GROUP_RIPP,
        "Peptide subclass of a RiPP precursor in the region.",
    ),
    _sequence(
        "core_seq",
        "Core peptide",
        GROUP_RIPP,
        "Core peptide sequence of a RiPP precursor in the region.",
    ),
    _sequence(
        "leader_seq",
        "Leader peptide",
        GROUP_RIPP,
        "Leader peptide sequence of a RiPP precursor in the region.",
    ),
    _number(
        "ripp_mass",
        "RiPP monoisotopic mass (Da)",
        GROUP_RIPP,
        "Monoisotopic mass of a RiPP precursor in the region.",
        tokenizer="float",
        multi=True,
    ),
    _number(
        "rodeo_score",
        "RODEO score",
        GROUP_RIPP,
        "RODEO score of a RiPP precursor in the region.",
        multi=True,
    ),
    _number(
        "ripp_cut_mass",
        "RiPP cut mass (Da)",
        GROUP_RIPP,
        "Cut mass of a RiPP precursor in the region.",
        tokenizer="float",
        multi=True,
    ),
    _number(
        "ripp_cut_weight",
        "RiPP cut weight (Da)",
        GROUP_RIPP,
        "Cut weight of a RiPP precursor in the region.",
        tokenizer="float",
        multi=True,
    ),
    _number(
        "ripp_mature_weight",
        "RiPP mature weight (Da)",
        GROUP_RIPP,
        "Mature weight of a RiPP precursor in the region.",
        tokenizer="float",
        multi=True,
    ),
    _number(
        "ripp_num_bridges",
        "# RiPP bridges",
        GROUP_RIPP,
        "Number of bridges of a RiPP precursor in the region.",
        multi=True,
    ),
    _sequence(
        "ripp_macrolactam",
        "Macrolactam sequence",
        GROUP_RIPP,
        "Macrolactam sequence of a RiPP precursor in the region.",
    ),
    _keyword(
        "ripp_modifications",
        "RiPP modification",
        GROUP_RIPP,
        (
            "Categorical annotation of a RiPP precursor in the region, as "
            "key:value, such as macrocycle:head-to-tail."
        ),
    ),
    _keyword(
        "comparippson_hits",
        "CompaRiPPson hit",
        GROUP_RIPP,
        "Accession of a CompaRiPPson hit for a RiPP precursor in the region.",
    ),
    # Comparative
    _keyword(
        "knowncluster_hits",
        "KnownClusterBlast hit (MIBiG)",
        GROUP_COMPARATIVE,
        "MIBiG accession of a KnownClusterBlast hit for the region.",
    ),
    _keyword(
        "knowncluster_compounds",
        "KnownClusterBlast compound",
        GROUP_COMPARATIVE,
        "Compound of a KnownClusterBlast hit for the region.",
    ),
    _keyword(
        "knowncluster_top",
        "Top MIBiG hit",
        GROUP_COMPARATIVE,
        "MIBiG accession of the best KnownClusterBlast hit for the region.",
        multi=False,
    ),
    _keyword(
        "knowncluster_top_compound",
        "Top MIBiG compound",
        GROUP_COMPARATIVE,
        "Compound of the best KnownClusterBlast hit for the region.",
        multi=False,
    ),
    _number(
        "knowncluster_top_similarity",
        "Top MIBiG similarity (%)",
        GROUP_COMPARATIVE,
        "Similarity of the best KnownClusterBlast hit for the region, in percent.",
    ),
    _number(
        "num_knowncluster_hits",
        "# KnownClusterBlast hits",
        GROUP_COMPARATIVE,
        "Number of KnownClusterBlast hits for the region.",
    ),
    _keyword(
        "clusterblast_hits",
        "ClusterBlast hit",
        GROUP_COMPARATIVE,
        "Accession of a ClusterBlast hit for the region.",
    ),
    _keyword(
        "subcluster_hits",
        "SubClusterBlast hit",
        GROUP_COMPARATIVE,
        "Accession of a SubClusterBlast hit for the region.",
    ),
    _keyword(
        "mibig_comparison_top",
        "ClusterCompare top MIBiG",
        GROUP_COMPARATIVE,
        "MIBiG accession of the best ClusterCompare hit for the region.",
        multi=False,
    ),
    _number(
        "mibig_comparison_top_score",
        "ClusterCompare score",
        GROUP_COMPARATIVE,
        (
            "Score of the best ClusterCompare hit for the region; higher is "
            "more similar."
        ),
        tokenizer="float",
    ),
    # Regulation
    _keyword(
        "tfbs_regulators",
        "TFBS regulator",
        GROUP_REGULATION,
        "Regulator of a transcription factor binding site in the region.",
    ),
)

SEARCH_FIELDS_BY_NAME: dict[str, SearchField] = {
    search_field.name: search_field for search_field in SEARCH_FIELDS
}


# The public field list, in registry order, projected from SEARCH_FIELDS.
PUBLIC_FIELDS: tuple[PublicFieldInfo, ...] = tuple(
    PublicFieldInfo(
        name=search_field.name,
        kind=search_field.kind,
        label=search_field.label,
        group=search_field.group,
        multi=search_field.multi,
        default_search=search_field.default_search,
        description=search_field.description,
    )
    for search_field in SEARCH_FIELDS
)


# Field names a bare term searches: every text field.
DEFAULT_SEARCH_FIELD_NAMES: tuple[str, ...] = tuple(
    search_field.name for search_field in SEARCH_FIELDS if search_field.default_search
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
    return re.findall(PATH_TOKENIZER_PATTERN, value)


def strip_path_extension(value: str) -> str:
    """Drop the file extension, i.e. the last separator-delimited component.

    ``nested/NC_003888.3.json`` becomes ``nested/NC_003888.3`` and
    ``Y16952.json`` becomes ``Y16952``. A value with no separator is
    returned unchanged.
    """
    cut = max(map(value.rfind, PATH_SEPARATORS))
    return value[:cut] if cut >= 0 else value


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
    means every field that participates in default search. ``value_filter``
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
        slots=(
            ExampleSlot(
                name="word",
                candidates=("pfam", "product", "gene", "locus", "record"),
                value_filter="single_word",
            ),
        ),
    ),
    ExampleTemplate(
        template_id="fielded_word",
        pattern="{term_field}:{term_value}",
        slots=(
            ExampleSlot(
                name="term",
                candidates=("product_category", "product"),
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
                candidates=("organism", "pfam_desc"),
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
            ExampleSlot(
                name="left", candidates=("product_category",), value_filter="any"
            ),
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

    The gaps between the parts of a compound location are introns, which belong
    to the feature, so ``overlaps`` compares the entire span. The exception is a
    location that crosses the origin of a circular record, where the gap is the
    rest of the record, and ``overlaps`` compares the parts.
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

    @property
    def crosses_origin(self) -> bool:
        """Whether the parts wrap around the origin of a circular record.

        Parts are listed in transcription order, so they normally ascend on the
        forward strand and descend on the reverse strand. Out of order parts
        wrap around the origin, which may fall inside an intron.
        """
        starts = [part.start for part in self.parts]
        return starts != sorted(
            starts, reverse="(-)" in self.serialized
        )

    @property
    def _intervals(self) -> tuple[LocationPart, ...]:
        if self.crosses_origin:
            return self.parts
        return (LocationPart(self.start, self.end),)

    def overlaps(self, other: "Location") -> bool:
        return any(
            left.start < right.end and right.start < left.end
            for left in self._intervals
            for right in other._intervals
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
