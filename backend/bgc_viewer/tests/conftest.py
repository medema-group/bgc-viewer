"""
Pytest configuration and shared fixtures for BGC Viewer tests.
"""

import pytest
import tempfile
import json
from pathlib import Path
from bgc_viewer.app import app


@pytest.fixture
def client():
    """Create a test client for the Flask application."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_antismash_data():
    """Sample AntiSMASH data for testing."""
    return {
        "version": "1.0",
        "input_file": "test_sample.json",
        "records": [
            {
                "id": "test_record_1",
                "description": "Test record 1",
                "annotations": {
                    "region1": {
                        "type": "biosynthetic", 
                        "product": "polyketide",
                        "description": "Type I polyketide synthase cluster"
                    }
                },
                "features": [
                    {
                        "type": "source",
                        "location": "[1:1000]",
                        "qualifiers": {
                            "organism": "Streptomyces coelicolor",
                            "strain": "A3(2)",
                            "mol_type": "genomic DNA"
                        }
                    },
                    {
                        "type": "gene",
                        "location": "[100:500]",
                        "qualifiers": {
                            "gene": "testA",
                            "product": "test protein A"
                        }
                    },
                    {
                        "type": "protocluster",
                        "location": "[100:800]",
                        "qualifiers": {
                            "protocluster_number": "1",
                            "category": "PKS",
                            "product": "polyketide",
                            "core_location": "[200:600]"
                        }
                    },
                    {
                        "type": "CDS",
                        "location": "[150:400]",
                        "qualifiers": {
                            "gene_kind": "biosynthetic",
                            "gene": "pksA",
                            "product": "polyketide synthase"
                        }
                    }
                ]
            },
            {
                "id": "test_record_2",
                "description": "Test record 2", 
                "annotations": {
                    "region1": {
                        "type": "biosynthetic",
                        "product": "NRPS",
                        "description": "Nonribosomal peptide synthetase"
                    }
                },
                "features": [
                    {
                        "type": "source",
                        "location": "[1:1500]",
                        "qualifiers": {
                            "organism": "Bacillus subtilis",
                            "strain": "168"
                        }
                    },
                    {
                        "type": "protocluster",
                        "location": "[200:1200]",
                        "qualifiers": {
                            "protocluster_number": "1",
                            "category": "NRPS",
                            "product": "NRPS",
                            "core_location": "[300:900]"
                        }
                    },
                    {
                        "type": "CDS",
                        "location": "[250:800]",
                        "qualifiers": {
                            "gene_kind": "biosynthetic",
                            "gene": "nrpsA",
                            "product": "nonribosomal peptide synthetase"
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_json_file(temp_dir, sample_antismash_data):
    """Create a sample JSON file for testing."""
    test_file = temp_dir / "test_sample.json"
    with open(test_file, 'w') as f:
        json.dump(sample_antismash_data, f, indent=2)
    return test_file


@pytest.fixture
def processed_data_dir(temp_dir, sample_json_file):
    """Create processed data directory with index."""
    from bgc_viewer.preprocessing import preprocess_antismash_files
    
    # Run preprocessing to create the index
    result = preprocess_antismash_files(str(temp_dir))
    
    return temp_dir, result
