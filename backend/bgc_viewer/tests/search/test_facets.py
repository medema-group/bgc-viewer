"""Tests for region documents: protocluster roll-up and antiSMASH module facets."""

import pytest
from bgc_viewer.search.document import SEARCH_FIELDS_BY_NAME, SourceFile
from bgc_viewer.search.extraction import extract

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
    return {document["region"][0]: document for document in documents}


# Two regions: region 1 holds two protoclusters and CDS A1 and geneB (a CDS
# without a locus tag, named by its gene), region 2 holds a terpene
# protocluster and CDS C1.
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
    _feature("cand_cluster", "[100:900](+)", kind=["chemical_hybrid"]),
    _feature("cand_cluster", "[100:500](+)", kind=["single"]),
    _feature("cand_cluster", "[1150:1450](+)", kind=["single"]),
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
            assert name in SEARCH_FIELDS_BY_NAME
