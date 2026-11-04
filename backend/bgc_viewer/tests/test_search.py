"""
Tests for the record listing served from the SQLite record index.

Attribute search is served by the Tantivy index; see ``tests/search``.
"""

import sqlite3

from bgc_viewer.database import get_database_entries


class TestDatabaseEntries:
    """Tests for listing records from the record index."""

    def test_list_all_entries(self, processed_data_dir):
        """All records are listed with their summary fields."""
        temp_dir, result = processed_data_dir
        db_path = str(temp_dir / "attributes.db")

        results = get_database_entries(db_path, page=1, per_page=10)

        assert results["total"] == 2
        assert results["page"] == 1
        assert results["per_page"] == 10
        assert results["total_pages"] == 1

        entries = {entry["record_id"]: entry for entry in results["entries"]}
        assert entries["test_record_1"] == {
            "filename": "test_sample.json",
            "record_id": "test_record_1",
            "id": "test_sample.json:test_record_1",
            "internal_id": entries["test_record_1"]["internal_id"],
            "description": "Test record 1",
            "organism": "Streptomyces coelicolor",
            "feature_count": 6,
            "region_count": 1,
        }
        assert entries["test_record_2"]["organism"] == "Bacillus subtilis"

    def test_pagination(self, processed_data_dir):
        """Pages split the records without overlap."""
        temp_dir, result = processed_data_dir
        db_path = str(temp_dir / "attributes.db")

        page1 = get_database_entries(db_path, page=1, per_page=1)
        page2 = get_database_entries(db_path, page=2, per_page=1)

        assert page1["total_pages"] == 2
        assert len(page1["entries"]) == 1
        assert len(page2["entries"]) == 1
        assert page1["entries"][0]["record_id"] != page2["entries"][0]["record_id"]

    def test_per_page_is_capped(self, processed_data_dir):
        temp_dir, result = processed_data_dir
        db_path = str(temp_dir / "attributes.db")

        results = get_database_entries(db_path, page=1, per_page=1000)

        assert results["per_page"] == 100

    def test_database_not_found(self, temp_dir):
        """Test behavior when database doesn't exist."""
        nonexistent_db = str(temp_dir / "nonexistent.db")

        results = get_database_entries(nonexistent_db, page=1, per_page=10)

        assert "error" in results
        assert "No database found" in results["error"]

    def test_outdated_database_asks_for_preprocessing(self, temp_dir):
        """A database from before the record summary columns is reported."""
        db_path = temp_dir / "old.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT)")
        conn.execute(
            """CREATE TABLE records (id INTEGER PRIMARY KEY, file_id INTEGER,
               record_id TEXT, byte_start INTEGER, byte_end INTEGER,
               feature_count INTEGER, region_count INTEGER)"""
        )
        conn.close()

        results = get_database_entries(str(db_path), page=1, per_page=10)

        assert "run preprocessing again" in results["error"]
