"""Region facets derived from the antiSMASH analysis modules of a record.

The record-level ``modules`` object holds the results of the optional
antiSMASH analyses (NRPS/PKS predictions, RiPP motifs, ClusterBlast, and so
on). Each function here picks out the part that belongs to one region and
returns it as ``{field name: values}`` for fields of the registry in
``document.py``.

The field set and the module paths follow the antiSMASH facet adapter of the
BGC Atlas (``scripts/populator/adapters/antismash_facets.py`` in
ziemertlab/bgc-atlas-web-v2). Unlike that adapter, results are scoped to a
region with the full antiSMASH location (compound locations, origin-crossing
regions) and by the antiSMASH CDS name, which falls back from the locus tag to
the gene name and protein ID, as the modules key their results by that name.

Module content is optional and its schema varies between antiSMASH versions,
so it is read leniently: a missing or differently shaped part yields no values
rather than failing the file. A field whose module did not run is left out, so
it is absent rather than zero.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from .document import Location

FacetValues = dict[str, list[Any]]


@dataclass(frozen=True)
class RegionScope:
    """What decides whether a module result belongs to a region.

    ``cds_names`` are the antiSMASH names of the CDS features overlapping the
    region, ``protocluster_numbers`` the numbers of its protoclusters, as the
    strings the modules key them by, and ``domain_cds`` maps an NRPS/PKS domain
    ID to the CDS it lies on, from the ``aSDomain`` features of the record.
    """

    location: Location
    number: int
    products: tuple[str, ...]
    cds_names: frozenset[str]
    protocluster_numbers: frozenset[str]
    domain_cds: Mapping[str, str]

    def overlaps(self, location: object) -> bool:
        """Whether a serialized antiSMASH ``location`` overlaps the region."""
        parsed = parse_location(location)
        return parsed is not None and self.location.overlaps(parsed)

    def contains_position(self, position: object) -> bool:
        """Whether a 0-based sequence ``position`` lies within the region."""
        if not isinstance(position, int) or isinstance(position, bool):
            return False
        if position < 0:
            return False
        return self.location.overlaps(Location(f"[{position}:{position + 1}]"))

    def has_cds(self, name: object) -> bool:
        return isinstance(name, str) and name in self.cds_names

    def has_domain(self, domain_id: str) -> bool:
        """Whether an NRPS/PKS domain lies on a CDS of the region.

        Domains without an ``aSDomain`` feature fall back to their ID, which
        antiSMASH builds as ``nrpspksdomains_<CDS name>_<domain>.<n>``.
        """
        cds = self.domain_cds.get(domain_id)
        if cds is not None:
            return cds in self.cds_names
        return any(
            domain_id.startswith(f"nrpspksdomains_{name}_") for name in self.cds_names
        )


def parse_location(value: object) -> Location | None:
    if not isinstance(value, str):
        return None
    try:
        return Location.parse(value)
    except ValueError:
        return None


def normalize_pfam(accession: str) -> str:
    """Remove a numeric version from a standard PFAM accession.

    For example, ``PF00512.28`` becomes ``PF00512``. Non-standard database
    cross-references and unversioned accessions are retained unchanged.
    """
    match = re.fullmatch(r"(PF\d{5})\.\d+", accession)
    return match.group(1) if match else accession


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _module(modules: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    module = modules.get(name)
    return module if isinstance(module, dict) else None


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _texts(values: Iterable[object]) -> list[str]:
    """The distinct non-empty strings among ``values``, in first-seen order."""
    return list(dict.fromkeys(text for text in map(_text, values) if text))


def _numbers(values: Iterable[object], cast: type) -> list[Any]:
    """The distinct ``values`` that convert with ``cast``, in first-seen order.

    antiSMASH stores some numbers as strings (``"2278.06"``), so strings are
    converted too; booleans and values that do not convert are dropped.
    """
    result: list[Any] = []
    for value in values:
        if isinstance(value, bool):
            continue
        try:
            number = cast(value)
        except (TypeError, ValueError):
            continue
        if number not in result:
            result.append(number)
    return result


def _scalar(value: Any) -> list[Any]:
    return [] if value is None else [value]


def functional_hits(
    modules: Mapping[str, Any], scope: RegionScope
) -> tuple[FacetValues, list[str], list[str]]:
    """TIGRFAM, smCoG, antiSMASH domain, and TTA facets, plus extra PFAM hits.

    The PFAM accessions and descriptions of the ``cluster_hmmer`` hits are
    returned separately, for the caller to merge with the PFAM_domain features
    before deriving GO terms with :func:`go_terms`.
    """
    facets: FacetValues = {}

    cluster_hmmer = _module(modules, "antismash.detection.cluster_hmmer")
    pfam_hits = [
        hit
        for hit in map(_mapping, _items((cluster_hmmer or {}).get("hits")))
        if _text(hit.get("identifier")) and scope.overlaps(hit.get("location"))
    ]
    pfams = _texts(normalize_pfam(hit["identifier"].strip()) for hit in pfam_hits)
    pfam_descriptions = _texts(hit.get("description") for hit in pfam_hits)

    tigrfam = _module(modules, "antismash.detection.tigrfam")
    if tigrfam is not None:
        hits = [
            hit
            for hit in map(_mapping, _items(tigrfam.get("hits")))
            if _text(hit.get("identifier"))
            and (
                scope.overlaps(hit.get("location"))
                or scope.has_cds(hit.get("locus_tag"))
            )
        ]
        facets["tigrfam"] = _texts(hit.get("identifier") for hit in hits)
        facets["tigrfam_desc"] = _texts(hit.get("description") for hit in hits)

    genefunctions = _module(modules, "antismash.detection.genefunctions")
    if genefunctions is not None:
        best_hits = _mapping(
            _mapping(_mapping(genefunctions.get("tools")).get("smcogs")).get(
                "best_hits"
            )
        )
        hits = [_mapping(hit) for name, hit in best_hits.items() if scope.has_cds(name)]
        facets["smcog"] = _texts(hit.get("reference_id") for hit in hits)
        facets["smcog_desc"] = _texts(
            hit.get("description") for hit in hits if _text(hit.get("reference_id"))
        )

    domains = _module(modules, "antismash.detection.nrps_pks_domains")
    if domains is not None:
        cds_results = _mapping(domains.get("cds_results"))
        facets["antismash_domains"] = _texts(
            _mapping(domain_hmm).get("hit_id")
            for name, result in cds_results.items()
            if scope.has_cds(name)
            for domain_hmm in _items(_mapping(result).get("domain_hmms"))
        )

    tta = _module(modules, "antismash.modules.tta")
    if tta is not None:
        facets["tta_codons"] = [
            sum(
                1
                for codon in _items(tta.get("TTA codons"))
                if scope.contains_position(_mapping(codon).get("start"))
            )
        ]

    return facets, pfams, pfam_descriptions


def go_terms(modules: Mapping[str, Any], pfams: Iterable[str]) -> FacetValues:
    """GO terms that pfam2go maps the region's PFAM accessions to."""
    pfam2go = _module(modules, "antismash.modules.pfam2go")
    if pfam2go is None:
        return {}
    wanted = set(pfams)
    return {
        "go_terms": _texts(
            term
            for accession, terms in _mapping(pfam2go.get("pfams")).items()
            if normalize_pfam(accession) in wanted
            for term in _mapping(terms)
        )
    }


def nrps_pks(modules: Mapping[str, Any], scope: RegionScope) -> FacetValues:
    """NRPS/PKS substrate, monomer, module, and product predictions."""
    facets: FacetValues = {}

    domains = _module(modules, "antismash.detection.nrps_pks_domains")
    if domains is not None:
        signatures: list[str] = []
        module_count = 0
        for name, result in _mapping(domains.get("cds_results")).items():
            if not scope.has_cds(name):
                continue
            for module in map(_mapping, _items(_mapping(result).get("modules"))):
                module_count += 1
                signature = "-".join(
                    _text(_mapping(_mapping(component).get("domain")).get("hit_id"))
                    or ""
                    for component in _items(module.get("components"))
                )
                if signature.strip("-"):
                    signatures.append(signature)
        facets["module_signatures"] = _texts(signatures)
        facets["num_modules"] = [module_count]

    predictions = _module(modules, "antismash.modules.nrps_pks")
    if predictions is None:
        return facets

    facets["monomers"] = _texts(
        monomer
        for domain_id, monomer in _mapping(predictions.get("consensus")).items()
        if scope.has_domain(domain_id)
    )

    substrates: list[object] = []
    stachelhaus: list[object] = []
    at_specificity: list[object] = []
    kr_stereochemistry: list[object] = []
    for domain_id, raw_prediction in _mapping(
        predictions.get("domain_predictions")
    ).items():
        if not scope.has_domain(domain_id):
            continue
        prediction = _mapping(raw_prediction)
        nrpys = _mapping(prediction.get("nrpys"))
        single_amino = _mapping(nrpys.get("single_amino"))
        substrates.extend(
            _mapping(substrate).get("short")
            for substrate in _items(single_amino.get("substrates"))
        )
        for match in map(_mapping, _items(nrpys.get("stachelhaus_matches"))):
            stachelhaus.append(match.get("signature"))
            substrates.extend(
                _mapping(substrate).get("short")
                for substrate in _items(match.get("substrates"))
            )
        minowa = _items(_mapping(prediction.get("minowa_at")).get("predictions"))
        if minowa and _items(minowa[0]):
            # The predictions are ranked; the first is the top-scoring substrate.
            at_specificity.append(minowa[0][0])
        kr_stereochemistry.append(
            _mapping(prediction.get("kr_stereochem")).get("prediction")
        )
    facets["substrates"] = _texts(substrates)
    facets["stachelhaus_codes"] = _texts(stachelhaus)
    facets["at_specificity"] = _texts(at_specificity)
    facets["kr_stereochemistry"] = _texts(kr_stereochemistry)

    region_predictions = _items(
        _mapping(predictions.get("region_predictions")).get(str(scope.number))
    )
    facets["predicted_smiles"] = _texts(
        _mapping(prediction).get("smiles") for prediction in region_predictions
    )
    facets["monomer_consensus"] = _texts(
        _mapping(prediction).get("polymer") for prediction in region_predictions
    )

    facets["pks_trans_at"] = [
        "transAT-PKS" in scope.products
        or any(
            scope.has_domain(domain_id)
            for domain_id in _mapping(predictions.get("consensus_transat"))
        )
    ]
    return facets


def _t2pks_name(value: object) -> object:
    """A type II PKS prediction is a name, a ``[name, score, ...]`` list, or a dict."""
    if isinstance(value, list):
        return value[0] if value else None
    if isinstance(value, dict):
        return value.get("name") or value.get("class")
    return value


def terpene_t2pks(modules: Mapping[str, Any], scope: RegionScope) -> FacetValues:
    """Terpene and type II PKS predictions of the region's protoclusters."""
    facets: FacetValues = {}

    terpene = _module(modules, "antismash.modules.terpene")
    if terpene is not None:
        products: list[object] = []
        domain_types: list[object] = []
        for number, raw_prediction in _mapping(
            terpene.get("protocluster_predictions")
        ).items():
            if number not in scope.protocluster_numbers:
                continue
            prediction = _mapping(raw_prediction)
            products.extend(_items(prediction.get("products")))
            for cds_predictions in _mapping(prediction.get("cds_predictions")).values():
                domain_types.extend(
                    _mapping(domain).get("domain_type")
                    for domain in _items(cds_predictions)
                )
        facets["terpene_products"] = _texts(products)
        facets["terpene_domains"] = _texts(domain_types)

    t2pks = _module(modules, "antismash.modules.t2pks")
    if t2pks is not None:
        classes: list[object] = []
        starters: list[object] = []
        elongations: list[object] = []
        for number, raw_prediction in _mapping(
            t2pks.get("protocluster_predictions")
        ).items():
            if number not in scope.protocluster_numbers:
                continue
            prediction = _mapping(raw_prediction)
            classes.extend(map(_t2pks_name, _items(prediction.get("product_classes"))))
            starters.extend(map(_t2pks_name, _items(prediction.get("starter_units"))))
            elongations.extend(map(_t2pks_name, _items(prediction.get("elongations"))))
        facets["pks_t2_class"] = _texts(classes)
        facets["pks_t2_starter"] = _texts(starters)
        facets["pks_t2_elongation"] = _texts(elongations)

    return facets


_RIPP_MODULES = (
    "antismash.modules.lanthipeptides",
    "antismash.modules.lassopeptides",
    "antismash.modules.sactipeptides",
    "antismash.modules.thiopeptides",
)

# ``detailed_info`` mixes categorical annotations with numbers and sequences.
# Only these keys become ``ripp_modifications``, so a new numeric key cannot
# pollute the categorical field; a new categorical annotation must be added
# here before it becomes searchable.
_RIPP_MODIFICATION_KEYS = (
    "predicted_additional_modifications",
    "macrocycle",
    "core_features",
    "tail_reaction",
)


def _ripp_motifs(module: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    """Motifs are keyed by CDS (lanthi-, lasso-, sactipeptides) or a list (thio)."""
    motifs = module.get("motifs")
    groups = motifs.values() if isinstance(motifs, dict) else [motifs]
    for group in groups:
        yield from map(_mapping, _items(group))


def _ripp_cds_in_scope(name: object, scope: RegionScope) -> bool:
    """RiPP precursors have ``<CDS name>_<RiPP type>`` names; try the CDS name too."""
    if not isinstance(name, str):
        return False
    return scope.has_cds(name) or scope.has_cds(name.rsplit("_", 1)[0])


def ripp(modules: Mapping[str, Any], scope: RegionScope) -> FacetValues:
    """RiPP precursor classes, sequences, masses, and annotations."""
    present = [
        module
        for module in (_module(modules, name) for name in _RIPP_MODULES)
        if module is not None
    ]
    if not present:
        return {}

    values: dict[str, list[object]] = {
        name: []
        for name in (
            "ripp_class",
            "ripp_subclass",
            "core_seq",
            "leader_seq",
            "ripp_mass",
            "rodeo_score",
            "ripp_cut_mass",
            "ripp_cut_weight",
            "ripp_mature_weight",
            "ripp_num_bridges",
            "ripp_macrolactam",
            "ripp_modifications",
            "comparippson_hits",
        )
    }
    detail_fields = {
        "RODEO_score": "rodeo_score",
        "cut_mass": "ripp_cut_mass",
        "cut_weight": "ripp_cut_weight",
        "mature_weights": "ripp_mature_weight",
        "number_of_bridges": "ripp_num_bridges",
        "macrolactam": "ripp_macrolactam",
    }
    for module in present:
        for motif in _ripp_motifs(module):
            # Precursor names are synthetic, so prefer the motif's location.
            if motif.get("location") is not None:
                if not scope.overlaps(motif["location"]):
                    continue
            elif not _ripp_cds_in_scope(motif.get("locus_tag"), scope):
                continue
            values["ripp_class"].append(motif.get("peptide_class"))
            values["ripp_subclass"].append(motif.get("peptide_subclass"))
            values["core_seq"].append(motif.get("core"))
            values["leader_seq"].append(motif.get("leader"))
            values["ripp_mass"].append(motif.get("monoisotopic_mass"))
            for key, raw in _mapping(motif.get("detailed_info")).items():
                details = raw if isinstance(raw, list) else [raw]
                if key in detail_fields:
                    values[detail_fields[key]].extend(details)
                elif key in _RIPP_MODIFICATION_KEYS:
                    # An empty value (``macrocycle:``) carries no signal.
                    values["ripp_modifications"].extend(
                        f"{key}:{detail}" for detail in details if str(detail).strip()
                    )
        # The key differs between the RiPP modules.
        for key in ("comparippson", "comparippson_results"):
            for result in map(
                _mapping, _items(_mapping(module.get(key)).get("db_results"))
            ):
                for name, hits in _mapping(result.get("hits")).items():
                    if not _ripp_cds_in_scope(name, scope):
                        continue
                    values["comparippson_hits"].extend(
                        _mapping(_mapping(hit).get("reference_fields")).get("accession")
                        for hit in _items(hits)
                    )

    floats = {"ripp_mass", "ripp_cut_mass", "ripp_cut_weight", "ripp_mature_weight"}
    integers = {"rodeo_score", "ripp_num_bridges"}
    return {
        name: (
            _numbers(raw, float)
            if name in floats
            else _numbers(raw, int) if name in integers else _texts(raw)
        )
        for name, raw in values.items()
    }


def _ranking(clusterblast: Mapping[str, Any], kind: str, number: int) -> list[Any]:
    for result in map(
        _mapping, _items(_mapping(clusterblast.get(kind)).get("results"))
    ):
        if result.get("region_number") == number:
            return _items(result.get("ranking"))
    return []


def _reference(entry: object) -> Mapping[str, Any]:
    """The reference cluster of a ``[reference, score]`` ranking entry."""
    return _mapping(entry[0]) if isinstance(entry, list) and entry else {}


def comparative(modules: Mapping[str, Any], scope: RegionScope) -> FacetValues:
    """KnownClusterBlast, ClusterBlast, ClusterCompare, and TFBS results."""
    facets: FacetValues = {}

    clusterblast = _module(modules, "antismash.modules.clusterblast")
    if clusterblast is not None:
        if "knowncluster" in clusterblast:
            known = _ranking(clusterblast, "knowncluster", scope.number)
            facets["knowncluster_hits"] = _texts(
                _reference(entry).get("accession") for entry in known
            )
            facets["knowncluster_compounds"] = _texts(
                _reference(entry).get("description") for entry in known
            )
            facets["num_knowncluster_hits"] = [len(known)]
            if known:
                top = known[0]
                facets["knowncluster_top"] = _texts([_reference(top).get("accession")])
                facets["knowncluster_top_compound"] = _texts(
                    [_reference(top).get("description")]
                )
                score = (
                    _mapping(top[1]) if isinstance(top, list) and len(top) > 1 else {}
                )
                facets["knowncluster_top_similarity"] = _numbers(
                    [score.get("similarity")], int
                )
        for kind, name in (
            ("general", "clusterblast_hits"),
            ("subcluster", "subcluster_hits"),
        ):
            if kind in clusterblast:
                facets[name] = _texts(
                    _reference(entry).get("accession")
                    for entry in _ranking(clusterblast, kind, scope.number)
                )

    cluster_compare = _module(modules, "antismash.modules.cluster_compare")
    if cluster_compare is not None:
        by_region = _mapping(
            _mapping(
                _mapping(_mapping(cluster_compare.get("db_results")).get("MIBiG")).get(
                    "by_region"
                )
            ).get(str(scope.number))
        )
        top_accession: str | None = None
        top_score: float | None = None
        for method in map(_mapping, by_region.values()):
            for reference, score in _mapping(method.get("scores_by_region")).items():
                if isinstance(score, bool) or not isinstance(score, (int, float)):
                    continue
                if top_score is None or score > top_score:
                    # Keyed as "ACCESSION: start-end".
                    top_score = float(score)
                    top_accession = reference.split(":")[0].strip()
        facets["mibig_comparison_top"] = _scalar(_text(top_accession))
        facets["mibig_comparison_top_score"] = _scalar(top_score)

    tfbs = _module(modules, "antismash.modules.tfbs_finder")
    if tfbs is not None:
        facets["tfbs_regulators"] = _texts(
            _mapping(hit).get("name")
            for hit in _items(
                _mapping(tfbs.get("hits_by_region")).get(str(scope.number))
            )
        )

    return facets
