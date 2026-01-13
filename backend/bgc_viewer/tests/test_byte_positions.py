"""Test that byte positions are correctly stored and can be used to extract records."""

import pytest
import sqlite3
import json
from pathlib import Path


def test_byte_positions_accuracy(test_database):
    """Test that stored byte positions correctly extract records from JSON files."""
    db_path, data_dir = test_database
    
    conn = sqlite3.connect(db_path)
    
    # Get data_root from metadata
    cursor = conn.execute("SELECT value FROM metadata WHERE key = 'data_root'")
    result = cursor.fetchone()
    assert result is not None, "data_root not found in metadata"
    data_root = Path(result[0])
    
    # Get all records with their byte positions
    cursor = conn.execute("""
        SELECT f.path, r.record_id, r.byte_start, r.byte_end 
        FROM records r
        JOIN files f ON r.file_id = f.id
    """)
    
    records = cursor.fetchall()
    assert len(records) > 0, "No records found in database"
    
    # Test each record
    for filepath, record_id, byte_start, byte_end in records:
        file_path = data_root / filepath
        
        assert file_path.exists(), f"File not found: {file_path}"
        assert byte_start >= 0, f"Invalid byte_start: {byte_start}"
        assert byte_end > byte_start, f"Invalid byte range: {byte_start}-{byte_end}"
        
        # Read the bytes at the stored position
        with open(file_path, 'rb') as f:
            f.seek(byte_start)
            record_bytes = f.read(byte_end - byte_start)
        
        # Parse as JSON
        record_data = json.loads(record_bytes.decode('utf-8'))
        extracted_id = record_data.get('id')
        
        # Verify the extracted record ID matches
        assert extracted_id == record_id, \
            f"Record ID mismatch in {filepath}: expected '{record_id}', got '{extracted_id}'"
        
        # Verify it's a valid record structure
        assert 'features' in record_data, f"Record missing 'features' field: {record_id}"
    
    conn.close()


def test_byte_positions_coverage(test_database):
    """Test that all records have valid byte positions."""
    db_path, data_dir = test_database
    
    conn = sqlite3.connect(db_path)
    
    # Check for records with invalid byte positions
    cursor = conn.execute("""
        SELECT COUNT(*) FROM records 
        WHERE byte_start < 0 OR byte_end <= byte_start
    """)
    
    invalid_count = cursor.fetchone()[0]
    assert invalid_count == 0, f"Found {invalid_count} records with invalid byte positions"
    
    # Check that all records have non-zero byte ranges
    cursor = conn.execute("""
        SELECT COUNT(*) FROM records 
        WHERE byte_end - byte_start = 0
    """)
    
    zero_size_count = cursor.fetchone()[0]
    assert zero_size_count == 0, f"Found {zero_size_count} records with zero-size byte ranges"
    
    conn.close()
