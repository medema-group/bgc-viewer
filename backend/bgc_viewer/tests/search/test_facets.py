"""Tests for region and protocluster documents and antiSMASH module facets."""

import pytest
from bgc_viewer.search.document import KIND_FIELD, SEARCH_FIELDS_BY_NAME, SourceFile
from bgc_viewer.search.extraction import extract
from bgc_viewer.search.index import (
    build_index,
    facet_counts,
    field_values,
    parse_query,
    search_protoclusters,
    search_record,
    search_regions,
)

_SOURCE = SourceFile(
    antismash_version="8.0.2", output_file="sample.json", input_file="sample.gbk"
)


def _feature(feature_type, location, **qualifiers):
    return {
        "type": feature_type,
        "location": location,
        "qualifiers": {name: list(values) for name, values in qualifiers.items()},
    }


def _extract(record) -> dict[int, dict[str, list]]:
    """Extract one record and key its region documents by region number."""
    documents = [document.to_dict() for document in extract([record], _SOURCE)]
    return {
        document["region"][0]: document
        for document in documents
        if document["kind"] == ["region"]
    }


def _extract_protoclusters(record) -> dict[int, dict[str, list]]:
    """Extract one record and key its protocluster documents by number."""
    documents = [document.to_dict() for document in extract([record], _SOURCE)]
    return {
        document["protocluster_number"][0]: document
        for document in documents
        if document["kind"] == ["protocluster"]
    }


# Two regions: region 1 holds two overlapping protoclusters and CDS A1 and
# geneB (a CDS without a locus tag, named by its gene), region 2 holds a
# terpene protocluster and CDS C1. A1 lies in protocluster 1 only, geneB in
# both protoclusters 1 and 2.
_FEATURES = [
    _feature("source", "[0:2000](+)", organism=["Streptomyces example"]),
    _feature(
        "region",
        "[0:1000](+)",
        region_number=["1"],
        contig_edge=["True"],
        rules=["cds(Condensation and AMP-binding)"],
    ),
    _feature("region", "[1100:1500](+)", region_number=["2"]),
    _feature(
        "protocluster",
        "[100:500](+)",
        protocluster_number=["1"],
        product=["NRPS"],
        category=["NRPS"],
        detection_rule=["cds(Condensation and AMP-binding)"],
    ),
    _feature(
        "protocluster",
        "[400:900](+)",
        protocluster_number=["2"],
        product=["T2PKS"],
        category=["PKS"],
        detection_rule=["t2pks_rule"],
    ),
    _feature(
        "protocluster",
        "[1150:1450](+)",
        protocluster_number=["3"],
        product=["terpene"],
        category=["terpene"],
    ),
    _feature(
        "cand_cluster",
        "[100:900](+)",
        kind=["chemical_hybrid"],
        protoclusters=["1", "2"],
    ),
    _feature("cand_cluster", "[100:500](+)", kind=["single"], protoclusters=["1"]),
    _feature("cand_cluster", "[1150:1450](+)", kind=["single"], protoclusters=["3"]),
    _feature("CDS", "[100:300](+)", locus_tag=["A1"], gene_kind=["biosynthetic"]),
    _feature("CDS", "[300:600](-)", gene=["geneB"], gene_kind=["transport"]),
    _feature("CDS", "[1200:1300](+)", locus_tag=["C1"], gene_kind=["biosynthetic"]),
    _feature(
        "aSDomain",
        "[150:250](+)",
        domain_id=["unprefixed_domain"],
        locus_tag=["A1"],
    ),
]

_MODULES = {
    "antismash.detection.cluster_hmmer": {
        "hits": [
            {
                "location": "[150:250](+)",
                "identifier": "PF00550.27",
                "description": "Phosphopantetheine attachment site",
            },
            {
                "location": "[1200:1250](+)",
                "identifier": "PF00001.1",
                "description": "Region two domain",
            },
        ]
    },
    "antismash.detection.tigrfam": {
        "hits": [
            {
                "locus_tag": "geneB",
                "identifier": "TIGR01733",
                "description": "AA-adenyl-dom",
            },
            {
                "location": "[1200:1250](+)",
                "locus_tag": "C1",
                "identifier": "TIGR00001",
                "description": "Region two",
            },
        ]
    },
    "antismash.detection.genefunctions": {
        "tools": {
            "smcogs": {
                "best_hits": {
                    "A1": {"reference_id": "SMCOG1127", "description": "condensation"},
                    "geneB": {"reference_id": "SMCOG1288", "description": "ABC"},
                    "C1": {"reference_id": "SMCOG1000", "description": "other"},
                }
            }
        }
    },
    "antismash.detection.nrps_pks_domains": {
        "cds_results": {
            "A1": {
                "domain_hmms": [{"hit_id": "AMP-binding"}, {"hit_id": "PCP"}],
                "modules": [
                    {
                        "components": [
                            {"domain": {"hit_id": "AMP-binding"}},
                            {"domain": {"hit_id": "PCP"}},
                        ]
                    }
                ],
            },
            "C1": {
                "domain_hmms": [{"hit_id": "Condensation_LCL"}],
                "modules": [],
            },
        }
    },
    "antismash.modules.nrps_pks": {
        "consensus": {
            "nrpspksdomains_A1_AMP-binding.1": "Leu",
            "unprefixed_domain": "Ser",
            "nrpspksdomains_C1_AMP-binding.1": "Val",
        },
        "domain_predictions": {
            "nrpspksdomains_A1_AMP-binding.1": {
                "nrpys": {
                    "single_amino": {"substrates": [{"short": "Leu"}]},
                    "stachelhaus_matches": [
                        {"signature": "DAFYLGMMCK", "substrates": [{"short": "Ile"}]}
                    ],
                }
            },
            "nrpspksdomains_A1_PKS_AT.1": {
                "minowa_at": {"predictions": [["mal", 90.0], ["mmal", 10.0]]},
                "kr_stereochem": {"prediction": "B1"},
            },
            "nrpspksdomains_C1_AMP-binding.1": {
                "nrpys": {"single_amino": {"substrates": [{"short": "Val"}]}}
            },
        },
        "region_predictions": {
            "1": [{"smiles": "CC(N)C(=O)O", "polymer": "(Leu - Ser)"}],
            "2": [{"smiles": "CCO", "polymer": "(Val)"}],
        },
        "consensus_transat": {"nrpspksdomains_A1_PKS_AT.1": "mal"},
    },
    "antismash.modules.terpene": {
        "protocluster_predictions": {
            "3": {
                "products": ["squalene"],
                "cds_predictions": {"C1": [{"domain_type": "PT_phytoene_like"}]},
            }
        }
    },
    "antismash.modules.t2pks": {
        "protocluster_predictions": {
            "2": {
                "product_classes": ["angucycline"],
                "starter_units": [["acetyl-CoA", 0.0, 0.0]],
                "elongations": [["7", 743.5, 1.2e-226]],
            }
        }
    },
    "antismash.modules.lanthipeptides": {
        "motifs": {
            "A1": [
                {
                    "location": "[150:250](+)",
                    "locus_tag": "A1_lanthipeptide",
                    "peptide_class": "lanthipeptide",
                    "peptide_subclass": "Class I",
                    "core": "ASFGEG",
                    "leader": "MRTEIV",
                    "monoisotopic_mass": 2328.065,
                    "detailed_info": {
                        "RODEO_score": ["18"],
                        "number_of_bridges": ["3"],
                        "cut_mass": ["2278.06", "not a number"],
                        "macrocycle": [""],
                        "core_features": ["lanthionine"],
                    },
                }
            ],
            "C1": [
                {
                    "location": "[1200:1250](+)",
                    "peptide_class": "lanthipeptide",
                    "peptide_subclass": "Class II",
                }
            ],
        },
        "comparippson": {
            "db_results": [
                {
                    "hits": {
                        "A1_lanthipeptide": [
                            {"reference_fields": {"accession": "BGC0000500"}}
                        ]
                    }
                }
            ]
        },
    },
    "antismash.modules.tta": {"TTA codons": [{"start": 120}, {"start": 1300}]},
    "antismash.modules.pfam2go": {
        "pfams": {
            "PF00550": {"GO:0031177": "phosphopantetheine binding"},
            "PF00001": {"GO:0000001": "other"},
        }
    },
    "antismash.modules.clusterblast": {
        "knowncluster": {
            "results": [
                {
                    "region_number": 1,
                    "ranking": [
                        [
                            {"accession": "BGC0000311.6", "description": "balhimycin"},
                            {"similarity": 80},
                        ],
                        [
                            {"accession": "BGC0000455.6", "description": "vancomycin"},
                            {"similarity": 40},
                        ],
                    ],
                },
                {"region_number": 2, "ranking": []},
            ]
        },
        "general": {
            "results": [
                {"region_number": 1, "ranking": [[{"accession": "NZ_CP042324"}, {}]]}
            ]
        },
    },
    "antismash.modules.cluster_compare": {
        "db_results": {
            "MIBiG": {
                "by_region": {
                    "1": {
                        "RegionToRegion_RiQ": {
                            "scores_by_region": {
                                "BGC0000002.1: 0-100": 0.5,
                                "BGC0000003.1: 0-100": 0.9,
                            }
                        }
                    }
                }
            }
        }
    },
    "antismash.modules.tfbs_finder": {"hits_by_region": {"1": [{"name": "AbrC3"}]}},
}


@pytest.fixture
def regions():
    return _extract({"id": "rec", "features": _FEATURES, "modules": _MODULES})


def test_protoclusters_roll_up_into_multi_valued_region_fields(regions):
    first, second = regions[1], regions[2]
    assert first["product"] == ["NRPS", "T2PKS"]
    assert first["product_category"] == ["NRPS", "PKS"]
    assert first["num_protoclusters"] == [2]
    assert first["detection_rules"] == [
        "cds(Condensation and AMP-binding)",
        "t2pks_rule",
    ]
    assert first["candidate_kind"] == ["chemical_hybrid", "single"]
    assert second["product"] == ["terpene"]
    assert second["candidate_kind"] == ["single"]


def test_contig_edge_marks_a_region_incomplete(regions):
    assert regions[1]["is_complete"] == [False]
    assert regions[2]["is_complete"] == [True]


def test_counts_cds_features_and_gene_kinds_per_region(regions):
    assert regions[1]["num_cds_features"] == [2]
    assert regions[1]["n_core_biosynthetic"] == [1]
    assert regions[1]["n_transport"] == [1]
    assert regions[2]["num_cds_features"] == [1]
    assert regions[2]["n_transport"] == [0]


def test_region_without_protoclusters_takes_the_region_product():
    record = {
        "id": "rec",
        "features": [
            _feature("region", "[0:1000](+)", region_number=["1"], product=["NRPS"])
        ],
    }
    [document] = _extract(record).values()
    assert document["product"] == ["NRPS"]
    assert document["num_protoclusters"] == [0]
    assert "product_category" not in document


def test_functional_hits_are_scoped_by_location_and_cds_name(regions):
    first, second = regions[1], regions[2]
    assert first["pfam"] == ["PF00550"]
    assert first["pfam_desc"] == ["Phosphopantetheine attachment site"]
    # geneB has no locus tag; modules key it by its gene name.
    assert first["tigrfam"] == ["TIGR01733"]
    assert first["smcog"] == ["SMCOG1127", "SMCOG1288"]
    assert first["smcog_desc"] == ["condensation", "ABC"]
    assert first["antismash_domains"] == ["AMP-binding", "PCP"]
    assert first["go_terms"] == ["GO:0031177"]
    assert first["tta_codons"] == [1]
    assert second["pfam"] == ["PF00001"]
    assert second["tigrfam"] == ["TIGR00001"]
    assert second["smcog"] == ["SMCOG1000"]
    assert second["go_terms"] == ["GO:0000001"]
    assert second["tta_codons"] == [1]


def test_nrps_pks_predictions_are_scoped_to_the_region(regions):
    first, second = regions[1], regions[2]
    # The aSDomain feature places the unprefixed domain on A1.
    assert first["monomers"] == ["Leu", "Ser"]
    assert first["substrates"] == ["Leu", "Ile"]
    assert first["stachelhaus_codes"] == ["DAFYLGMMCK"]
    assert first["at_specificity"] == ["mal"]
    assert first["kr_stereochemistry"] == ["B1"]
    assert first["module_signatures"] == ["AMP-binding-PCP"]
    assert first["num_modules"] == [1]
    assert first["predicted_smiles"] == ["CC(N)C(=O)O"]
    assert first["monomer_consensus"] == ["(Leu - Ser)"]
    assert first["pks_trans_at"] == [True]
    assert second["monomers"] == ["Val"]
    assert second["substrates"] == ["Val"]
    assert second["num_modules"] == [0]
    assert second["predicted_smiles"] == ["CCO"]
    assert second["pks_trans_at"] == [False]


def test_terpene_and_type_ii_pks_follow_protocluster_numbers(regions):
    first, second = regions[1], regions[2]
    assert first["pks_t2_class"] == ["angucycline"]
    assert first["pks_t2_starter"] == ["acetyl-CoA"]
    assert first["pks_t2_elongation"] == ["7"]
    assert "terpene_products" not in first
    assert second["terpene_products"] == ["squalene"]
    assert second["terpene_domains"] == ["PT_phytoene_like"]
    assert "pks_t2_class" not in second


def test_ripp_precursors_are_scoped_by_location(regions):
    first, second = regions[1], regions[2]
    assert first["ripp_class"] == ["lanthipeptide"]
    assert first["ripp_subclass"] == ["Class I"]
    assert first["core_seq"] == ["ASFGEG"]
    assert first["leader_seq"] == ["MRTEIV"]
    assert first["ripp_mass"] == [2328.065]
    assert first["rodeo_score"] == [18]
    assert first["ripp_num_bridges"] == [3]
    # Values that are not numbers and empty annotations are dropped.
    assert first["ripp_cut_mass"] == [2278.06]
    assert first["ripp_modifications"] == ["core_features:lanthionine"]
    # A precursor name falls back to the CDS name it was derived from.
    assert first["comparippson_hits"] == ["BGC0000500"]
    assert second["ripp_subclass"] == ["Class II"]
    assert "comparippson_hits" not in second


def test_comparative_results_follow_the_region_number(regions):
    first, second = regions[1], regions[2]
    assert first["knowncluster_hits"] == ["BGC0000311.6", "BGC0000455.6"]
    assert first["knowncluster_compounds"] == ["balhimycin", "vancomycin"]
    assert first["knowncluster_top"] == ["BGC0000311.6"]
    assert first["knowncluster_top_compound"] == ["balhimycin"]
    assert first["knowncluster_top_similarity"] == [80]
    assert first["num_knowncluster_hits"] == [2]
    assert first["clusterblast_hits"] == ["NZ_CP042324"]
    assert first["mibig_comparison_top"] == ["BGC0000003.1"]
    assert first["mibig_comparison_top_score"] == [0.9]
    assert first["tfbs_regulators"] == ["AbrC3"]
    assert second["num_knowncluster_hits"] == [0]
    assert "knowncluster_top" not in second
    assert "mibig_comparison_top" not in second
    assert "tfbs_regulators" not in second


def test_fields_of_modules_that_did_not_run_are_absent(regions):
    # SubClusterBlast is the one ClusterBlast part this record lacks.
    assert "subcluster_hits" not in regions[1]
    bare = _extract({"id": "rec", "features": _FEATURES})
    module_fields = {"tigrfam", "smcog", "tta_codons", "num_modules", "monomers"}
    assert module_fields.isdisjoint(bare[1])
    assert "pks_trans_at" not in bare[1]


def test_malformed_module_content_yields_no_values():
    modules = {
        "antismash.detection.tigrfam": {"hits": "not a list"},
        "antismash.modules.nrps_pks": ["not", "an", "object"],
        "antismash.modules.clusterblast": {"knowncluster": {"results": [None, 3]}},
        "antismash.modules.tta": {"TTA codons": [{"start": "120"}, {"start": True}]},
    }
    document = _extract({"id": "rec", "features": _FEATURES, "modules": modules})[1]
    assert "tigrfam" not in document
    assert "monomers" not in document
    assert document["num_knowncluster_hits"] == [0]
    assert document["tta_codons"] == [0]


def test_catch_all_text_holds_words_but_not_sequences_or_paths(regions):
    text = regions[1]["text"]
    assert "Streptomyces example" in text
    assert "balhimycin" in text
    assert "PF00550" in text
    assert "ASFGEG" not in text
    assert "CC(N)C(=O)O" not in text
    assert "sample.json" not in text


def test_every_extracted_field_is_registered(regions):
    for document in regions.values():
        for name in document:
            assert name == KIND_FIELD or name in SEARCH_FIELDS_BY_NAME


# --- Protocluster documents --------------------------------------------------


@pytest.fixture
def protoclusters():
    return _extract_protoclusters(
        {"id": "rec", "features": _FEATURES, "modules": _MODULES}
    )


def test_each_protocluster_gets_a_document_with_its_own_identity(protoclusters):
    assert sorted(protoclusters) == [1, 2, 3]
    first, second, third = protoclusters[1], protoclusters[2], protoclusters[3]
    assert first["kind"] == ["protocluster"]
    assert (first["region"], second["region"], third["region"]) == ([1], [1], [2])
    # The protocluster's full location, not its region's.
    assert (second["start"], second["end"], second["length"]) == ([400], [900], [500])
    assert first["product"] == ["NRPS"]
    assert first["product_category"] == ["NRPS"]
    assert first["detection_rules"] == ["cds(Condensation and AMP-binding)"]
    assert second["product"] == ["T2PKS"]
    assert second["detection_rules"] == ["t2pks_rule"]
    # The region's protocluster count, so it can filter protoclusters too.
    assert first["num_protoclusters"] == [2]
    assert third["num_protoclusters"] == [1]


def test_region_documents_have_no_protocluster_number(regions):
    assert all("protocluster_number" not in region for region in regions.values())


def test_protocluster_belongs_to_the_candidates_that_list_it(protoclusters):
    assert protoclusters[1]["candidate_kind"] == ["chemical_hybrid", "single"]
    assert protoclusters[2]["candidate_kind"] == ["chemical_hybrid"]
    assert protoclusters[3]["candidate_kind"] == ["single"]


def test_protocluster_contig_edge_falls_back_to_its_region():
    features = [
        _feature("region", "[0:1000](+)", region_number=["1"], contig_edge=["True"]),
        _feature(
            "protocluster",
            "[0:400](+)",
            protocluster_number=["1"],
            product=["NRPS"],
            category=["NRPS"],
            contig_edge=["False"],
        ),
        _feature(
            "protocluster",
            "[500:1000](+)",
            protocluster_number=["2"],
            product=["PKS"],
            category=["PKS"],
        ),
    ]
    documents = _extract_protoclusters({"id": "rec", "features": features})
    assert documents[1]["is_complete"] == [True]
    assert documents[2]["is_complete"] == [False]


def test_genes_and_functional_hits_are_scoped_to_the_protocluster(protoclusters):
    first, second = protoclusters[1], protoclusters[2]
    assert first["num_cds_features"] == [2]
    assert first["n_core_biosynthetic"] == [1]
    assert second["num_cds_features"] == [1]
    assert second["n_core_biosynthetic"] == [0]
    assert second["n_transport"] == [1]
    assert first["pfam"] == ["PF00550"]
    assert "pfam" not in second
    assert first["smcog"] == ["SMCOG1127", "SMCOG1288"]
    assert second["smcog"] == ["SMCOG1288"]
    assert first["tta_codons"] == [1]
    assert second["tta_codons"] == [0]
    assert first["ripp_class"] == ["lanthipeptide"]
    assert "ripp_class" not in second


def test_nrps_pks_and_type_ii_pks_follow_the_protocluster(protoclusters):
    first, second = protoclusters[1], protoclusters[2]
    assert first["monomers"] == ["Leu", "Ser"]
    assert first["num_modules"] == [1]
    assert first["pks_trans_at"] == [True]
    assert "pks_t2_class" not in first
    assert "monomers" not in second
    assert second["num_modules"] == [0]
    assert second["pks_trans_at"] == [False]
    assert second["pks_t2_class"] == ["angucycline"]
    assert protoclusters[3]["terpene_products"] == ["squalene"]


def test_region_keyed_results_are_inherited_from_the_parent_region(protoclusters):
    for number in (1, 2):
        document = protoclusters[number]
        assert document["predicted_smiles"] == ["CC(N)C(=O)O"]
        assert document["knowncluster_top"] == ["BGC0000311.6"]
        assert document["clusterblast_hits"] == ["NZ_CP042324"]
        assert document["mibig_comparison_top"] == ["BGC0000003.1"]
        assert document["tfbs_regulators"] == ["AbrC3"]
    assert protoclusters[3]["num_knowncluster_hits"] == [0]
    assert protoclusters[3]["predicted_smiles"] == ["CCO"]


def test_every_protocluster_field_is_registered(protoclusters):
    for document in protoclusters.values():
        for name in document:
            assert name == KIND_FIELD or name in SEARCH_FIELDS_BY_NAME


# --- Searching each kind ------------------------------------------------------


@pytest.fixture
def index():
    record = {"id": "rec", "features": _FEATURES, "modules": _MODULES}
    return build_index(extract([record], _SOURCE))


def _protocluster_numbers(result):
    return sorted(hit.fields["protocluster_number"] for hit in result.hits)


def test_a_protocluster_must_match_every_condition_itself(index):
    # Region 1 holds an NRPS and an angucycline, in different protoclusters.
    across = "product:NRPS AND pks_t2_class:angucycline"
    assert [hit.fields["region"] for hit in search_regions(index, across).hits] == [1]
    assert search_protoclusters(index, across).hits == ()
    within = "product:NRPS AND substrates:Leu"
    assert _protocluster_numbers(search_protoclusters(index, within)) == [1]


def test_each_level_counts_its_own_kind(index):
    everything = "record:rec"
    regions = search_regions(index, everything)
    assert regions.total == 2
    assert all("protocluster_number" not in hit.fields for hit in regions.hits)
    assert search_record(index, everything).total == 2
    protoclusters = search_protoclusters(index, everything)
    assert protoclusters.total == 3
    assert _protocluster_numbers(protoclusters) == [1, 2, 3]


def test_facets_and_values_count_the_searched_kind(index):
    region_counts = facet_counts(index, "record:rec", ["product_category"])
    assert {b.value: b.count for b in region_counts["product_category"]} == {
        "NRPS": 1,
        "PKS": 1,
        "terpene": 1,
    }
    shared = facet_counts(index, "record:rec", ["smcog"], kind="protocluster")
    assert {b.value: b.count for b in shared["smcog"]}["SMCOG1288"] == 2
    assert {b.value: b.count for b in field_values(index, "smcog")}["SMCOG1288"] == 1
    by_protocluster = field_values(index, "smcog", kind="protocluster")
    assert {b.value: b.count for b in by_protocluster}["SMCOG1288"] == 2


def test_scores_are_not_changed_by_the_kind_restriction(index):
    [hit] = search_regions(index, "pfam:PF00001").hits
    raw = index.searcher().search(parse_query(index, "pfam:PF00001"), limit=10)
    assert hit.score in {score for score, _ in raw.hits}
