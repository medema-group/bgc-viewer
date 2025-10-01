"""
Tests for data loading functionality including random access.
"""

import pytest
import json
from pathlib import Path
from bgc_viewer.data_loader import (
    load_specific_record,
    load_record_by_index,
    load_specific_record_fallback,
    list_available_records,
    get_record_metadata_from_index,
    load_antismash_data,
    load_json_file
)


class TestRandomAccess:
    """Tests for random access functionality."""
    
    def test_load_specific_record_with_index(self, processed_data_dir, sample_json_file):
        """Test loading a specific record using byte position index."""
        temp_dir, result = processed_data_dir
        
        # Test loading first record
        loaded_data = load_specific_record(str(sample_json_file), "test_record_1", str(temp_dir))
        
        assert loaded_data is not None
        assert "records" in loaded_data
        assert len(loaded_data["records"]) == 1
        assert loaded_data["records"][0]["id"] == "test_record_1"
        assert loaded_data["records"][0]["description"] == "Test record 1"
    
    def test_load_specific_record_fallback(self, sample_json_file):
        """Test loading a specific record using fallback method."""
        loaded_data = load_specific_record_fallback(str(sample_json_file), "test_record_1")
        
        assert loaded_data is not None
        assert "records" in loaded_data
        assert len(loaded_data["records"]) == 1
        assert loaded_data["records"][0]["id"] == "test_record_1"
    
    def test_load_nonexistent_record(self, processed_data_dir, sample_json_file):
        """Test loading a record that doesn't exist."""
        temp_dir, result = processed_data_dir
        
        loaded_data = load_specific_record(str(sample_json_file), "nonexistent_record", str(temp_dir))
        assert loaded_data is None
    
    def test_list_available_records(self, processed_data_dir):
        """Test listing available records from index."""
        temp_dir, result = processed_data_dir
        
        records_info = list_available_records("test_sample.json", str(temp_dir))
        
        assert "records" in records_info
        assert len(records_info["records"]) == 2
        
        record_ids = [r["id"] for r in records_info["records"]]
        assert "test_record_1" in record_ids
        assert "test_record_2" in record_ids
    
    def test_get_record_metadata_from_index(self, processed_data_dir):
        """Test getting record metadata from index."""
        temp_dir, result = processed_data_dir
        
        metadata = get_record_metadata_from_index("test_sample.json", "test_record_1", str(temp_dir))
        
        assert metadata is not None
        assert metadata["filename"] == "test_sample.json"
        assert metadata["record_id"] == "test_record_1"
        assert "byte_start" in metadata
        assert "byte_end" in metadata
        assert "size_bytes" in metadata
        assert metadata["byte_start"] < metadata["byte_end"]


class TestDataLoading:
    """Tests for general data loading functionality."""
    
    def test_load_json_file(self, sample_json_file):
        """Test loading a JSON file."""
        data = load_json_file(sample_json_file)
        
        assert data is not None
        assert "records" in data
        assert len(data["records"]) == 2
        assert data["version"] == "1.0"
    
    def test_load_antismash_data_existing_file(self, sample_json_file):
        """Test loading AntiSMASH data from existing file."""
        # Copy file to expected location for this test
        data_dir = sample_json_file.parent
        
        data = load_antismash_data("test_sample.json", str(data_dir))
        
        assert data is not None
        assert "records" in data
        assert len(data["records"]) == 2
    
    def test_load_antismash_data_nonexistent_file(self, temp_dir):
        """Test loading AntiSMASH data from non-existent file."""
        data = load_antismash_data("nonexistent.json", str(temp_dir))
        assert data is None


class TestPerformanceComparison:
    """Tests comparing performance between different loading methods."""
    
    def test_random_access_vs_fallback_consistency(self, processed_data_dir, sample_json_file):
        """Test that random access and fallback methods return consistent results."""
        temp_dir, result = processed_data_dir
        
        # Load using random access
        indexed_result = load_record_by_index(str(sample_json_file), "test_record_1", str(temp_dir))
        
        # Load using fallback
        fallback_result = load_specific_record_fallback(str(sample_json_file), "test_record_1")
        
        # Both should succeed
        assert indexed_result is not None
        assert fallback_result is not None
        
        # Records should be identical
        indexed_record = indexed_result["records"][0]
        fallback_record = fallback_result["records"][0]
        
        assert indexed_record["id"] == fallback_record["id"]
        assert indexed_record["description"] == fallback_record["description"]
        assert len(indexed_record["features"]) == len(fallback_record["features"])
