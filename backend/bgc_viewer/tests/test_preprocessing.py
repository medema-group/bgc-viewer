"""
Tests for preprocessing functionality.
"""

import bz2
import gzip

import pytest
import json
import sqlite3
from pathlib import Path
from bgc_viewer.preprocessing import (
    preprocess_antismash_files,
    create_attributes_database,
)
from bgc_viewer.search.extraction import ExtractionError
from bgc_viewer.search.index import open_index, search_protoclusters


class TestDatabaseCreation:
    """Tests for database creation functionality."""

    def test_database_creation(self, temp_dir):
        """Test SQLite database creation."""
        db_path = temp_dir / "test.db"
        conn = create_attributes_database(db_path)

        # Attribute values are indexed by Tantivy only, never in SQLite
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"metadata", "files", "file_attributes", "records"} <= tables
        assert "attributes" not in tables

        # Check records table structure
        cursor = conn.execute("PRAGMA table_info(records)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = [
            "id",
            "file_id",
            "record_id",
            "byte_start",
            "byte_end",
            "description",
            "organism",
            "feature_count",
            "region_count",
        ]
        for col in expected_columns:
            assert col in columns

        conn.close()


class TestPreprocessingPipeline:
    """Tests for the complete preprocessing pipeline."""

    def test_full_pipeline(self, temp_dir):
        """Test the complete preprocessing pipeline."""
        # Create sample file
        sample_data = {
            "version": "8.0.2",
            "input_file": "test_sample.json",
            "records": [
                {
                    "id": "test_record_1",
                    "annotations": {
                        "gene1": {
                            "type": "gene",
                            "location": "[100:500]",
                            "gene": "testA",
                            "product": "test protein A",
                        }
                    },
                    "features": [
                        {
                            "type": "source",
                            "location": "[1:1000]",
                            "qualifiers": {
                                "organism": "Test organism",
                                "strain": "test_strain",
                                "mol_type": "genomic DNA",
                            },
                        }
                    ],
                },
                {
                    "id": "test_record_2",
                    "annotations": {
                        "gene2": {
                            "type": "gene",
                            "location": "[200:600]",
                            "gene": "testB",
                            "product": "test protein B",
                        }
                    },
                    "features": [
                        {
                            "type": "source",
                            "location": "[1:1500]",
                            "qualifiers": {
                                "organism": "Test organism 2",
                                "strain": "test_strain_2",
                            },
                        }
                    ],
                },
            ],
        }

        sample_file = temp_dir / "test_sample.json"
        with open(sample_file, "w") as f:
            json.dump(sample_data, f, indent=2)

        # Run preprocessing
        index_path = str(temp_dir / "attributes.db")
        results = preprocess_antismash_files(str(temp_dir), index_path)

        # Check results
        assert results["files_processed"] == 1
        assert results["total_records"] == 2

        # Check that database was created
        db_path = temp_dir / "attributes.db"
        assert db_path.exists()

        # Verify database contents
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            """SELECT record_id, organism, feature_count, region_count
               FROM records ORDER BY id"""
        ).fetchall()
        assert rows == [
            ("test_record_1", "Test organism", 1, 0),
            ("test_record_2", "Test organism 2", 1, 0),
        ]

        file_attributes = dict(
            conn.execute(
                "SELECT attribute_name, attribute_value FROM file_attributes"
            ).fetchall()
        )
        assert file_attributes == {
            "version": "8.0.2",
            "input_file": "test_sample.json",
        }

        cursor = conn.execute(
            """
            SELECT DISTINCT f.path 
            FROM records r 
            JOIN files f ON r.file_id = f.id
        """
        )
        files = [row[0] for row in cursor.fetchall()]
        assert any("test_sample.json" in str(f) for f in files)

        # Check byte positions are set in records table
        cursor = conn.execute(
            "SELECT COUNT(*) FROM records WHERE byte_start IS NOT NULL"
        )
        byte_indexed_count = cursor.fetchone()[0]
        assert byte_indexed_count > 0

        conn.close()

    def test_preprocessing_with_callback(self, temp_dir, sample_json_file):
        """Test preprocessing with progress callback."""
        progress_updates = []

        def progress_callback(current_file, files_processed, total_files):
            progress_updates.append((current_file, files_processed, total_files))

        # Run preprocessing with callback
        index_path = str(temp_dir / "attributes.db")
        results = preprocess_antismash_files(
            str(temp_dir), index_path, progress_callback
        )

        # Should have received progress updates
        assert len(progress_updates) > 0
        assert results["files_processed"] >= 1

        # Check final progress update
        final_update = progress_updates[-1]
        assert final_update[1] == final_update[2]  # files_processed == total_files


class TestSearchProgress:
    def test_search_progress_reports_files_and_phases(
        self, temp_dir, sample_json_file
    ):
        progress = []

        preprocess_antismash_files(
            str(temp_dir),
            str(temp_dir / "attributes.db"),
            search_progress_callback=lambda *args: progress.append(args),
        )

        assert progress == [
            ("indexing", 0, 1),
            ("indexing", 1, 1),
            ("committing", 1, 1),
            ("merging", 1, 1),
            ("complete", 1, 1),
        ]


class TestSearchIndexIntegration:
    """Tests for the search index built alongside the SQLite database."""

    def test_preprocessing_builds_search_index(self, sample_json_file):
        """Preprocessing builds a Tantivy index as a sibling of the database."""
        temp_dir = sample_json_file.parent
        index_path = str(temp_dir / "attributes.db")
        result = preprocess_antismash_files(str(temp_dir), index_path)

        assert "indexed_protoclusters" in result
        assert result["indexed_protoclusters"] == 2  # one protocluster per record

        search_index_dir = temp_dir / "tantivy.index"
        assert result["search_index_path"] == str(search_index_dir)
        assert search_index_dir.exists()

        # The generated index is directly usable through the search API.
        index = open_index(search_index_dir)
        hits = search_protoclusters(index, "product:polyketide")
        assert len(hits.hits) == 1
        assert hits.hits[0].fields["record"] == "test_record_1"

    @pytest.mark.parametrize(
        "suffix,compress", [("gz", gzip.compress), ("bz2", bz2.compress)]
    )
    def test_preprocessing_indexes_compressed_json(
        self, temp_dir, sample_antismash_data, suffix, compress
    ):
        filename = f"test_sample.json.{suffix}"
        (temp_dir / filename).write_bytes(
            compress(json.dumps(sample_antismash_data).encode("utf-8"))
        )

        result = preprocess_antismash_files(
            str(temp_dir), str(temp_dir / "attributes.db")
        )
        assert result["indexed_protoclusters"] == 2

        index = open_index(temp_dir / "tantivy.index")
        hits = search_protoclusters(index, "product:polyketide")
        assert len(hits.hits) == 1
        assert hits.hits[0].fields["output_file"] == filename

    def test_preprocessing_rebuild_removes_previous_index(self, sample_json_file):
        """A rebuild deletes the previous index before creating the new one."""
        temp_dir = sample_json_file.parent
        index_path = str(temp_dir / "attributes.db")
        preprocess_antismash_files(str(temp_dir), index_path)

        search_index_dir = temp_dir / "tantivy.index"
        assert search_index_dir.exists()
        marker = search_index_dir / "marker.txt"
        marker.write_text("stale")

        result = preprocess_antismash_files(str(temp_dir), index_path)
        assert not marker.exists()
        assert result["indexed_protoclusters"] == 2

    def test_preprocessing_failed_build_leaves_no_index(self, temp_dir):
        """A structurally incompatible file fails the build and leaves no index."""
        sample = {
            "version": "8.0.2",
            "input_file": "bad.gbk",
            "records": [
                {
                    "id": "bad_record",
                    "features": [
                        {
                            "type": "protocluster",
                            "location": "[100:800]",
                            "qualifiers": {
                                "protocluster_number": ["1"],
                                "category": ["PKS"],
                                "product": ["polyketide"],
                            },
                        }
                    ],
                }
            ],
        }
        (temp_dir / "bad.json").write_text(json.dumps(sample))

        index_path = str(temp_dir / "attributes.db")
        with pytest.raises(ExtractionError):
            preprocess_antismash_files(str(temp_dir), index_path)
        assert not (temp_dir / "tantivy.index").exists()
