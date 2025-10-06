"""
Tests for preprocessing functionality.
"""

import pytest
import json
import sqlite3
from pathlib import Path
from bgc_viewer.preprocessing import (
    preprocess_antismash_files,
    flatten_complex_value,
    extract_attributes_from_record,
    create_attributes_database
)


class TestFlattenComplexValue:
    """Tests for the flatten_complex_value function."""
    
    def test_simple_string(self):
        """Test flattening a simple string."""
        result = flatten_complex_value("simple_string")
        assert result == [("", "simple_string")]
    
    def test_string_with_prefix(self):
        """Test flattening a string with prefix."""
        result = flatten_complex_value("value", "prefix")
        assert result == [("prefix", "value")]
    
    def test_dict_flattening(self):
        """Test flattening a dictionary."""
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
    
    def test_array_flattening(self):
        """Test flattening an array."""
        test_array = ["value1", "value2"]
        result = flatten_complex_value(test_array, "array_attr")
        expected = [("array_attr", "value1"), ("array_attr", "value2")]
        assert sorted(result) == sorted(expected)


class TestExtractAttributesFromRecord:
    """Tests for the extract_attributes_from_record function."""
    
    def test_basic_extraction(self):
        """Test basic attribute extraction from a record."""
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
        
        attributes = extract_attributes_from_record(sample_record, 1)  # record_ref_id = 1
        
        # Should have attributes from both annotations and source features
        assert len(attributes) > 0
        
        # Check structure - each should be (record_ref, origin, attr_name, attr_value)
        for attr in attributes:
            assert len(attr) == 4
            assert attr[0] == 1  # record_ref
            assert attr[1] in ["annotations", "source"]  # origin
            assert isinstance(attr[2], str)  # attr_name
            assert isinstance(attr[3], str)  # attr_value


class TestDatabaseCreation:
    """Tests for database creation functionality."""
    
    def test_database_creation(self, temp_dir):
        """Test SQLite database creation."""
        db_path = temp_dir / "test.db"
        conn = create_attributes_database(db_path)
        
        # Check that table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attributes'")
        assert cursor.fetchone() is not None
        
        # Check table structure
        cursor = conn.execute("PRAGMA table_info(attributes)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = ['id', 'record_ref', 'origin', 'attribute_name', 'attribute_value']
        for col in expected_columns:
            assert col in columns
        
        # Check records table structure  
        cursor = conn.execute("PRAGMA table_info(records)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = ['id', 'filename', 'record_id', 'byte_start', 'byte_end']
        for col in expected_columns:
            assert col in columns
        
        conn.close()


class TestPreprocessingPipeline:
    """Tests for the complete preprocessing pipeline."""
    
    def test_full_pipeline(self, temp_dir):
        """Test the complete preprocessing pipeline."""
        # Create sample file
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
        
        sample_file = temp_dir / "test_sample.json"
        with open(sample_file, 'w') as f:
            json.dump(sample_data, f, indent=2)
        
        # Run preprocessing
        results = preprocess_antismash_files(str(temp_dir))
        
        # Check results
        assert results['files_processed'] == 1
        assert results['total_records'] == 2
        assert results['total_attributes'] > 0
        
        # Check that database was created
        db_path = temp_dir / "attributes.db"
        assert db_path.exists()
        
        # Verify database contents
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM attributes")
        total_attributes = cursor.fetchone()[0]
        assert total_attributes > 0
        
        cursor = conn.execute("SELECT DISTINCT origin FROM attributes")
        origins = [row[0] for row in cursor.fetchall()]
        assert "annotations" in origins
        assert "source" in origins
        
        cursor = conn.execute("SELECT DISTINCT filename FROM records")
        files = [row[0] for row in cursor.fetchall()]
        assert "test_sample.json" in files
        
        # Check byte positions are set in records table
        cursor = conn.execute("SELECT COUNT(*) FROM records WHERE byte_start IS NOT NULL")
        byte_indexed_count = cursor.fetchone()[0]
        assert byte_indexed_count > 0
        
        conn.close()
    
    def test_preprocessing_with_callback(self, temp_dir, sample_json_file):
        """Test preprocessing with progress callback."""
        progress_updates = []
        
        def progress_callback(current_file, files_processed, total_files):
            progress_updates.append((current_file, files_processed, total_files))
        
        # Run preprocessing with callback
        results = preprocess_antismash_files(str(temp_dir), progress_callback)
        
        # Should have received progress updates
        assert len(progress_updates) > 0
        assert results['files_processed'] >= 1
        
        # Check final progress update
        final_update = progress_updates[-1]
        assert final_update[1] == final_update[2]  # files_processed == total_files
