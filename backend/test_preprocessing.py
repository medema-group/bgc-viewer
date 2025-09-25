"""
Test script for the preprocessing functionality.
"""

import json
import tempfile
import sqlite3
from pathlib import Path
from preprocess_data import (
    preprocess_antismash_files,
    flatten_complex_value,
    extract_attributes_from_record,
    create_attributes_database
)

def create_sample_antismash_file():
    """Create a sample AntiSMASH JSON file for testing."""
    sample_data = {
        "records": [
            {
                "id": "test_record_1",
                "annotations": {
                    "gene1": {
                        "type": "gene",
                        "location": "[100:500]",
                        "gene": "testA",
                        "product": "test protein A"
                    },
                    "cds1": {
                        "type": "CDS",
                        "location": "[100:500]", 
                        "gene": "testA",
                        "translation": "MTEST..."
                    }
                },
                "features": [
                    {
                        "type": "source",
                        "location": "[1:1000]",
                        "qualifiers": {
                            "organism": "Test organism",
                            "strain": "test_strain",
                            "mol_type": "genomic DNA"
                        }
                    },
                    {
                        "type": "gene",
                        "location": "[100:500]",
                        "qualifiers": {
                            "gene": "testA"
                        }
                    }
                ]
            },
            {
                "id": "test_record_2", 
                "annotations": {
                    "gene2": {
                        "type": "gene",
                        "location": "[200:600]",
                        "gene": "testB",
                        "product": "test protein B"
                    }
                },
                "features": [
                    {
                        "type": "source",
                        "location": "[1:1500]",
                        "qualifiers": {
                            "organism": "Test organism 2",
                            "strain": "test_strain_2"
                        }
                    }
                ]
            }
        ]
    }
    return sample_data

def test_flatten_complex_value():
    """Test the flatten_complex_value function."""
    print("Testing flatten_complex_value...")
    
    # Test simple values
    result = flatten_complex_value("simple_string")
    assert result == [("", "simple_string")]
    
    # Test with prefix
    result = flatten_complex_value("value", "prefix")
    assert result == [("prefix", "value")]
    
    # Test dict
    test_dict = {
        "gene": "testA",
        "location": {"start": 100, "end": 500}
    }
    result = flatten_complex_value(test_dict)
    expected = [
        ("gene", "testA"),
        ("location_start", "100"),
        ("location_end", "500")
    ]
    assert sorted(result) == sorted(expected)
    
    # Test array
    test_array = ["value1", "value2"]
    result = flatten_complex_value(test_array, "array_attr")
    expected = [("array_attr", "value1"), ("array_attr", "value2")]
    assert sorted(result) == sorted(expected)
    
    print("  ✓ All flattening tests passed")


def test_extract_attributes_from_record():
    """Test the extract_attributes_from_record function."""
    print("Testing extract_attributes_from_record...")
    
    sample_record = {
        "id": "test_record",
        "annotations": {
            "gene1": {
                "type": "gene",
                "location": "[100:500]",
                "gene": "testA"
            }
        },
        "features": [
            {
                "type": "source",
                "qualifiers": {
                    "organism": "Test organism",
                    "mol_type": "genomic DNA"
                }
            }
        ]
    }
    
    attributes = extract_attributes_from_record(sample_record, "test.json", "record1")
    
    # Should have attributes from both annotations and source features
    assert len(attributes) > 0
    
    # Check structure - each should be (filename, record_id, origin, attr_name, attr_value)
    for attr in attributes:
        assert len(attr) == 5
        assert attr[0] == "test.json"  # filename
        assert attr[1] == "record1"    # record_id
        assert attr[2] in ["annotations", "source"]  # origin
    
    print(f"  ✓ Extracted {len(attributes)} attributes")


def test_database_creation():
    """Test SQLite database creation."""
    print("Testing database creation...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        conn = create_attributes_database(db_path)
        
        # Check that table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attributes'")
        assert cursor.fetchone() is not None
        
        # Check table structure
        cursor = conn.execute("PRAGMA table_info(attributes)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = ['id', 'filename', 'record_id', 'origin', 'attribute_name', 'attribute_value']
        for col in expected_columns:
            assert col in columns
        
        conn.close()
        print("  ✓ Database creation test passed")


def test_full_pipeline():
    """Test the complete preprocessing pipeline with SQLite output."""
    print("Testing full preprocessing pipeline...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        input_dir = Path(temp_dir) / "input"
        input_dir.mkdir()
        
        # Create sample file
        sample_data = create_sample_antismash_file()
        sample_file = input_dir / "test_sample.json"
        
        with open(sample_file, 'w') as f:
            json.dump(sample_data, f, indent=2)
        
        print(f"Created sample file: {sample_file}")
        
        # Test directory processing
        print("\nTesting directory processing...")
        results = preprocess_antismash_files(str(input_dir))
        
        print("Results:", json.dumps(results, indent=2))
        
        # Check that database was created
        db_path = input_dir / "attributes.db"
        assert db_path.exists(), "Database file should be created"
        
        # Connect and inspect database contents
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM attributes")
        total_attributes = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT DISTINCT origin FROM attributes")
        origins = [row[0] for row in cursor.fetchall()]
        
        cursor = conn.execute("SELECT DISTINCT filename FROM attributes")
        files = [row[0] for row in cursor.fetchall()]
        
        print(f"Database contains {total_attributes} attributes")
        print(f"Origins: {origins}")
        print(f"Files: {files}")
        
        # Check some sample attributes
        cursor = conn.execute("SELECT attribute_name, attribute_value, origin FROM attributes LIMIT 10")
        sample_attrs = cursor.fetchall()
        print("Sample attributes:")
        for attr_name, attr_value, origin in sample_attrs:
            print(f"  {origin}: {attr_name} = {attr_value}")
        
        conn.close()
        print("\nTest completed successfully!")


if __name__ == "__main__":
    test_flatten_complex_value()
    test_extract_attributes_from_record()
    test_database_creation()
    test_full_pipeline()
