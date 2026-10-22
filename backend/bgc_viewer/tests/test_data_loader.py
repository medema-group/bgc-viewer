"""
Tests for data loading functionality including random access.
"""

import bz2
import gzip
import pytest
import json
from pathlib import Path
from bgc_viewer import data_loader
from bgc_viewer.preprocessing import preprocess_antismash_files
from bgc_viewer.data_loader import (
    load_specific_record,
    load_record_by_index,
    load_specific_record_fallback,
    list_available_records,
    get_record_metadata_from_index,
    load_json_file,
)


class TestRandomAccess:
    """Tests for random access functionality."""

    def test_load_specific_record_with_index(
        self, processed_data_dir, sample_json_file
    ):
        """Test loading a specific record using byte position index."""
        temp_dir, result = processed_data_dir

        # Test loading first record
        loaded_data = load_specific_record(
            str(sample_json_file), "test_record_1", str(temp_dir)
        )

        assert loaded_data is not None
        assert "records" in loaded_data
        assert len(loaded_data["records"]) == 1
        assert loaded_data["records"][0]["id"] == "test_record_1"
        assert loaded_data["records"][0]["description"] == "Test record 1"

    def test_load_specific_record_fallback(self, sample_json_file):
        """Test loading a specific record using fallback method."""
        loaded_data = load_specific_record_fallback(
            str(sample_json_file), "test_record_1"
        )

        assert loaded_data is not None
        assert "records" in loaded_data
        assert len(loaded_data["records"]) == 1
        assert loaded_data["records"][0]["id"] == "test_record_1"

    def test_load_nonexistent_record(self, processed_data_dir, sample_json_file):
        """Test loading a record that doesn't exist."""
        temp_dir, result = processed_data_dir

        loaded_data = load_specific_record(
            str(sample_json_file), "nonexistent_record", str(temp_dir)
        )
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

        metadata = get_record_metadata_from_index(
            "test_sample.json", "test_record_1", str(temp_dir)
        )

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


class TestIndexLocation:
    """The byte index is used wherever the selected database is stored."""

    @pytest.fixture
    def no_fallback(self, monkeypatch):
        def fail(*args):
            raise AssertionError("fell back to parsing the whole file")

        monkeypatch.setattr(data_loader, "load_specific_record_fallback", fail)

    @pytest.mark.parametrize("name", ["data.json", "data.json.gz", "data.json.bz2"])
    def test_database_outside_data_folder(
        self, temp_dir, sample_antismash_data, no_fallback, name
    ):
        data_dir = temp_dir / "data"
        data_dir.mkdir()
        raw = json.dumps(sample_antismash_data).encode()
        compress = {".gz": gzip.compress, ".bz2": bz2.compress}.get(
            Path(name).suffix, lambda data: data
        )
        (data_dir / name).write_bytes(compress(raw))
        db_path = temp_dir / "indexes" / "custom.db"
        preprocess_antismash_files(str(data_dir), str(db_path))

        loaded = load_specific_record(
            str(data_dir / name), "test_record_2", str(data_dir), str(db_path)
        )

        assert loaded["records"] == [sample_antismash_data["records"][1]]
        assert loaded["file_attributes"]["version"] == "1.0"

    def test_stale_index_falls_back_to_full_parse(
        self, processed_data_dir, sample_json_file, sample_antismash_data
    ):
        """If the file changed after indexing, the byte range is not trusted."""
        temp_dir, _ = processed_data_dir
        sample_antismash_data["records"].reverse()
        sample_json_file.write_text(json.dumps(sample_antismash_data))

        loaded = load_specific_record(
            str(sample_json_file), "test_record_1", str(temp_dir)
        )

        assert loaded["records"][0]["id"] == "test_record_1"


class TestPerformanceComparison:
    """Tests comparing performance between different loading methods."""

    def test_random_access_vs_fallback_consistency(
        self, processed_data_dir, sample_json_file
    ):
        """Test that random access and fallback methods return consistent results."""
        temp_dir, result = processed_data_dir

        # Load using random access
        indexed_result = load_record_by_index(
            str(sample_json_file), "test_record_1", str(temp_dir)
        )

        # Load using fallback
        fallback_result = load_specific_record_fallback(
            str(sample_json_file), "test_record_1"
        )

        # Both should succeed
        assert indexed_result is not None
        assert fallback_result is not None

        # Records should be identical
        indexed_record = indexed_result["records"][0]
        fallback_record = fallback_result["records"][0]

        assert indexed_record["id"] == fallback_record["id"]
        assert indexed_record["description"] == fallback_record["description"]
        assert len(indexed_record["features"]) == len(fallback_record["features"])
