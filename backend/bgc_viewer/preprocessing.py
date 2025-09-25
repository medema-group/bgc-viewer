"""
Preprocessing module for AntiSMASH JSON files.
Extracts attributes into SQLite database.
"""

import json
import ijson
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable


def create_attributes_database(db_path: Path) -> sqlite3.Connection:
    """Create SQLite database for storing attributes. Drops existing database if it exists."""
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()
    
    conn = sqlite3.connect(db_path)
    
    # Create the attributes table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            record_id TEXT NOT NULL,
            origin TEXT NOT NULL,  -- 'annotations' or 'source'
            attribute_name TEXT NOT NULL,
            attribute_value TEXT NOT NULL
        )
    """)
    
    # Create indexes for efficient querying
    conn.execute("CREATE INDEX IF NOT EXISTS idx_filename ON attributes (filename)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_record_id ON attributes (record_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_origin ON attributes (origin)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attribute_name ON attributes (attribute_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attribute_value ON attributes (attribute_value)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_name_value ON attributes (attribute_name, attribute_value)")
    
    conn.commit()
    return conn


def flatten_complex_value(value: Any, prefix: str = "") -> List[tuple]:
    """
    Flatten complex values into attribute name-value pairs.
    
    Args:
        value: The value to flatten
        prefix: Current prefix for nested attributes
        
    Returns:
        List of (attribute_name, attribute_value) tuples
    """
    results = []
    
    if isinstance(value, dict):
        for key, val in value.items():
            new_prefix = f"{prefix}_{key}" if prefix else key
            results.extend(flatten_complex_value(val, new_prefix))
    
    elif isinstance(value, list):
        # Flatten arrays into multiple entries
        for item in value:
            if isinstance(item, (dict, list)):
                results.extend(flatten_complex_value(item, prefix))
            else:
                results.append((prefix, str(item)))
    
    else:
        # Simple value (string, number, boolean, etc.)
        results.append((prefix, str(value)))
    
    return results


def extract_attributes_from_record(record: Dict[str, Any], filename: str, record_id: str) -> List[tuple]:
    """
    Extract all attributes from a record for database storage.
    
    Returns:
        List of tuples: (filename, record_id, origin, attribute_name, attribute_value)
    """
    attributes = []
    
    # Extract from annotations
    if 'annotations' in record and isinstance(record['annotations'], dict):
        for region_id, annotation_data in record['annotations'].items():
            flattened = flatten_complex_value(annotation_data)
            for attr_name, attr_value in flattened:
                # Prepend region_id to attribute name
                full_attr_name = f"{region_id}_{attr_name}" if attr_name else region_id
                attributes.append((
                    filename,
                    record_id,
                    'annotations',
                    full_attr_name,
                    attr_value
                ))
    
    # Extract from source features
    if 'features' in record and isinstance(record['features'], list):
        for feature in record['features']:
            if feature.get('type') == 'source' and 'qualifiers' in feature:
                flattened = flatten_complex_value(feature['qualifiers'])
                for attr_name, attr_value in flattened:
                    attributes.append((
                        filename,
                        record_id,
                        'source',
                        attr_name,
                        attr_value
                    ))
    
    return attributes


def preprocess_antismash_files(
    input_directory: str, 
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> Dict[str, Any]:
    """
    Preprocess antiSMASH JSON files and store attributes in SQLite database.
    
    Args:
        input_directory: Directory containing JSON files to process
        progress_callback: Optional callback function called with (current_file, files_processed, total_files)
        
    Returns:
        Dict with processing statistics
    """
    input_path = Path(input_directory)
    
    # Create database in the input directory
    db_path = input_path / "attributes.db"
    conn = create_attributes_database(db_path)
    
    # Process all JSON files
    json_files = list(input_path.glob("*.json"))
    total_records = 0
    total_attributes = 0
    files_processed = 0
    
    try:
        for json_file in json_files:
            try:
                if progress_callback:
                    progress_callback(json_file.name, files_processed, len(json_files))
                
                file_attributes = []
                file_records = 0
                
                with open(json_file, 'rb') as f:
                    # Parse records array
                    parser = ijson.items(f, 'records.item')
                    
                    for record in parser:
                        record_id = record.get('id', f'record_{total_records}')  
                        
                        # Extract attributes from this record
                        attributes = extract_attributes_from_record(
                            record, json_file.name, record_id
                        )
                        file_attributes.extend(attributes)
                        file_records += 1
                        total_records += 1
                
                # Batch insert attributes for this file
                if file_attributes:
                    conn.executemany(
                        """INSERT INTO attributes 
                           (filename, record_id, origin, attribute_name, attribute_value)
                           VALUES (?, ?, ?, ?, ?)""",
                        file_attributes
                    )
                    conn.commit()
                
                files_processed += 1
                total_attributes += len(file_attributes)
                
            except Exception as e:
                # Log error but continue with other files
                print(f"Error processing {json_file.name}: {e}")
    
    finally:
        conn.close()
    
    return {
        'files_processed': files_processed,
        'total_records': total_records,
        'total_attributes': total_attributes,
        'database_path': str(db_path)
    }
