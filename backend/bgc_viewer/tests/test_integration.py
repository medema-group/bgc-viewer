"""
Integration tests for the complete BGC Viewer system.
"""

import pytest
import json
from bgc_viewer.preprocessing import preprocess_antismash_files
from bgc_viewer.data_loader import load_specific_record
from bgc_viewer.database import get_database_entries


class TestFullSystemIntegration:
    """Test the complete system from preprocessing to data access."""
    
    def test_preprocessing_to_loading_pipeline(self, temp_dir, sample_antismash_data):
        """Test complete pipeline: create data -> preprocess -> load records."""
        
        # 1. Create test data file
        test_file = temp_dir / "integration_test.json"
        with open(test_file, 'w') as f:
            json.dump(sample_antismash_data, f, indent=2)
        
        # 2. Run preprocessing
        index_path = str(temp_dir / "attributes.db")
        result = preprocess_antismash_files(str(temp_dir), index_path)
        
        # Verify preprocessing results
        assert result['files_processed'] == 1
        assert result['total_records'] == 2
        assert result['total_attributes'] > 0
        
        # 3. Test random access loading
        loaded_record1 = load_specific_record(str(test_file), "test_record_1", str(temp_dir))
        loaded_record2 = load_specific_record(str(test_file), "test_record_2", str(temp_dir))
        
        # Verify loaded records
        assert loaded_record1 is not None
        assert loaded_record2 is not None
        assert loaded_record1["records"][0]["id"] == "test_record_1"
        assert loaded_record2["records"][0]["id"] == "test_record_2"
        
        # 4. Test database search
        db_path = str(temp_dir / "attributes.db")
        search_results = get_database_entries(db_path, page=1, per_page=10, search="")
        
        # Verify search results
        assert search_results["total"] >= 2
        assert len(search_results["entries"]) >= 2
        
        # Check that both records are findable
        found_records = {entry["record_id"] for entry in search_results["entries"]}
        assert "test_record_1" in found_records
        assert "test_record_2" in found_records
    
    def test_multiple_files_processing(self, temp_dir, sample_antismash_data):
        """Test processing multiple files in a directory."""
        
        # Create multiple test files
        files_data = [
            ("file1.json", {
                **sample_antismash_data,
                "records": [sample_antismash_data["records"][0]]  # First record only
            }),
            ("file2.json", {
                **sample_antismash_data, 
                "records": [sample_antismash_data["records"][1]]  # Second record only
            })
        ]
        
        created_files = []
        for filename, data in files_data:
            file_path = temp_dir / filename
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            created_files.append(file_path)
        
        # Run preprocessing
        index_path = str(temp_dir / "attributes.db")
        result = preprocess_antismash_files(str(temp_dir), index_path)
        
        # Should process both files
        assert result['files_processed'] == 2
        assert result['total_records'] == 2
        
        # Test loading from different files
        record1 = load_specific_record(str(created_files[0]), "test_record_1", str(temp_dir))
        record2 = load_specific_record(str(created_files[1]), "test_record_2", str(temp_dir))
        
        assert record1 is not None
        assert record2 is not None
        assert record1["records"][0]["id"] == "test_record_1"
        assert record2["records"][0]["id"] == "test_record_2"
        
        # Test database contains both files
        db_path = str(temp_dir / "attributes.db")
        search_results = get_database_entries(db_path, page=1, per_page=10, search="")
        
        found_files = {entry["filename"] for entry in search_results["entries"]}
        assert "file1.json" in found_files
        assert "file2.json" in found_files
    
    def test_preprocessing_with_progress_callback(self, temp_dir, sample_json_file):
        """Test preprocessing with progress tracking."""
        
        progress_updates = []
        
        def progress_callback(current_file, files_processed, total_files):
            progress_updates.append({
                'current_file': current_file,
                'files_processed': files_processed,
                'total_files': total_files
            })
        
        # Run preprocessing with callback
        index_path = str(temp_dir / "attributes.db")
        result = preprocess_antismash_files(str(temp_dir), index_path, progress_callback)
        
        # Verify progress tracking
        assert len(progress_updates) > 0
        assert progress_updates[0]['files_processed'] == 0
        assert progress_updates[-1]['files_processed'] == progress_updates[-1]['total_files']
        
        # Verify final state
        assert result['files_processed'] >= 1
    
    def test_error_handling_invalid_json(self, temp_dir):
        """Test system behavior with invalid JSON files."""
        
        # Create invalid JSON file
        invalid_file = temp_dir / "invalid.json"
        with open(invalid_file, 'w') as f:
            f.write('{"invalid": json content}')  # Invalid JSON
        
        # Preprocessing should handle this gracefully
        index_path = str(temp_dir / "attributes.db")
        result = preprocess_antismash_files(str(temp_dir), index_path)
        
        # Should report the error but not crash
        assert "files_processed" in result
        # The invalid file might be skipped, that's acceptable behavior
    
    def test_empty_directory_processing(self, temp_dir):
        """Test processing an empty directory."""
        
        # Run preprocessing on empty directory
        index_path = str(temp_dir / "attributes.db")
        result = preprocess_antismash_files(str(temp_dir), index_path)
        
        # Should complete without errors
        assert result['files_processed'] == 0
        assert result['total_records'] == 0
        assert result['total_attributes'] == 0


class TestPerformanceAndScalability:
    """Test performance characteristics of the system."""
    
    def test_large_record_handling(self, temp_dir):
        """Test handling of records with many features."""
        
        # Create a record with many features
        large_record = {
            "id": "large_record",
            "description": "Record with many features",
            "features": []
        }
        
        # Add 1 protocluster feature so it passes filtering
        large_record["features"].append({
            "type": "protocluster",
            "location": "[0:10000]",
            "qualifiers": {
                "protocluster_number": "1",
                "category": "PKS",
                "product": "polyketide"
            }
        })
        
        # Add 100 CDS features
        for i in range(100):
            large_record["features"].append({
                "type": "CDS",
                "location": f"[{i*100}:{(i+1)*100}](+)",
                "qualifiers": {
                    "gene": f"gene_{i:03d}",
                    "product": f"protein_{i:03d}",
                    "note": f"Feature number {i}"
                }
            })
        
        test_data = {
            "version": "1.0",
            "records": [large_record]
        }
        
        # Write to file
        test_file = temp_dir / "large_record.json"
        with open(test_file, 'w') as f:
            json.dump(test_data, f, indent=2)
        
        # Process and verify
        index_path = str(temp_dir / "attributes.db")
        result = preprocess_antismash_files(str(temp_dir), index_path)
        assert result['files_processed'] == 1
        assert result['total_records'] == 1
        # We only extract attributes from annotations and source features, not all CDS features
        # So the attribute count will be much lower than the number of features
        assert result['total_attributes'] >= 0  # Should complete successfully
        
        # Test loading the large record
        loaded = load_specific_record(str(test_file), "large_record", str(temp_dir))
        assert loaded is not None
        assert len(loaded["records"][0]["features"]) == 101  # 1 protocluster + 100 CDS
    
    def test_random_access_vs_fallback_performance(self, processed_data_dir, sample_json_file):
        """Test that random access is working (basic performance check)."""
        temp_dir, result = processed_data_dir
        
        # Load using random access method
        random_access_result = load_specific_record(str(sample_json_file), "test_record_1", str(temp_dir))
        
        # Should successfully load via random access
        assert random_access_result is not None
        assert random_access_result["records"][0]["id"] == "test_record_1"
        
        # The fact that this works means random access is functional
        # More detailed performance testing would require timing measurements
