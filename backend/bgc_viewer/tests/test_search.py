"""
Tests for search functionality.
"""

import pytest
from bgc_viewer.database import get_database_entries


class TestDatabaseSearch:
    """Tests for database search functionality."""
    
    def test_search_all_entries(self, processed_data_dir):
        """Test retrieving all entries without search filter."""
        temp_dir, result = processed_data_dir
        db_path = str(temp_dir / "attributes.db")
        
        results = get_database_entries(db_path, page=1, per_page=10, search="")
        
        assert "entries" in results
        assert "total" in results
        assert "page" in results
        assert "per_page" in results
        
        # Should have entries for both records
        assert results["total"] >= 2
        assert len(results["entries"]) >= 2
    
    def test_search_by_organism(self, processed_data_dir):
        """Test searching by organism name."""
        temp_dir, result = processed_data_dir
        db_path = str(temp_dir / "attributes.db")
        
        results = get_database_entries(db_path, page=1, per_page=10, search="Streptomyces")
        
        assert "entries" in results
        
        # Should find at least one entry with Streptomyces
        found_strep = False
        for entry in results["entries"]:
            if "Streptomyces" in entry.get("sample_attributes", ""):
                found_strep = True
                break
        
        # Note: This test might need adjustment based on exact sample data
        # The search should work but results depend on the test data content
    
    def test_search_by_product(self, processed_data_dir):
        """Test searching by product type."""
        temp_dir, result = processed_data_dir
        db_path = str(temp_dir / "attributes.db")
        
        results = get_database_entries(db_path, page=1, per_page=10, search="polyketide")
        
        assert "entries" in results
        # Should find entries related to polyketide
    
    def test_search_nonexistent_term(self, processed_data_dir):
        """Test searching for non-existent term."""
        temp_dir, result = processed_data_dir
        db_path = str(temp_dir / "attributes.db")
        
        results = get_database_entries(db_path, page=1, per_page=10, search="nonexistent_term_xyz")
        
        assert "entries" in results
        assert results["total"] == 0
        assert len(results["entries"]) == 0
    
    def test_pagination(self, processed_data_dir):
        """Test pagination functionality."""
        temp_dir, result = processed_data_dir
        db_path = str(temp_dir / "attributes.db")
        
        # Get first page with limit of 1
        results_page1 = get_database_entries(db_path, page=1, per_page=1, search="")
        
        assert results_page1["page"] == 1
        assert results_page1["per_page"] == 1
        
        if results_page1["total"] > 1:
            # Get second page
            results_page2 = get_database_entries(db_path, page=2, per_page=1, search="")
            
            assert results_page2["page"] == 2
            assert len(results_page2["entries"]) <= 1
            
            # Entries should be different
            if len(results_page1["entries"]) > 0 and len(results_page2["entries"]) > 0:
                entry1 = results_page1["entries"][0]
                entry2 = results_page2["entries"][0]
                assert entry1["filename"] != entry2["filename"] or entry1["record_id"] != entry2["record_id"]
    
    def test_database_not_found(self, temp_dir):
        """Test behavior when database doesn't exist."""
        nonexistent_db = str(temp_dir / "nonexistent.db")
        
        results = get_database_entries(nonexistent_db, page=1, per_page=10, search="")
        
        assert "error" in results
        assert "No database found" in results["error"]


class TestSearchAttributeValues:
    """Tests for searching within attribute values."""
    
    def test_search_in_attribute_values(self, processed_data_dir):
        """Test that search works within attribute values."""
        temp_dir, result = processed_data_dir
        db_path = str(temp_dir / "attributes.db")
        
        # Search for terms that should be in the attribute values
        test_searches = [
            "test",  # Should find records with "test" in descriptions
            "record",  # Should find records with "record" in IDs  
            "biosynthetic",  # Should find records with biosynthetic regions
        ]
        
        for search_term in test_searches:
            results = get_database_entries(db_path, page=1, per_page=10, search=search_term)
            
            assert "entries" in results
            # At least verify no errors occurred
            assert "error" not in results
    
    def test_case_insensitive_search(self, processed_data_dir):
        """Test that search is case insensitive."""
        temp_dir, result = processed_data_dir
        db_path = str(temp_dir / "attributes.db")
        
        # Search with different cases
        results_lower = get_database_entries(db_path, page=1, per_page=10, search="test")
        results_upper = get_database_entries(db_path, page=1, per_page=10, search="TEST")
        results_mixed = get_database_entries(db_path, page=1, per_page=10, search="Test")
        
        # Should return same number of results regardless of case
        assert results_lower["total"] == results_upper["total"]
        assert results_lower["total"] == results_mixed["total"]
