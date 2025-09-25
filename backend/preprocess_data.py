#!/usr/bin/env python3
"""
Standalone script to preprocess AntiSMASH JSON files and extract attributes into SQLite database.

Usage:
    python preprocess_data.py <input_directory>

Example:
    python preprocess_data.py ./data
"""

import sys
import json
import argparse
import ijson
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


def create_attributes_database(db_path: Path) -> sqlite3.Connection:
    """Create SQLite database for storing attributes. Drops existing database if it exists."""
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()
        print(f"Removed existing database: {db_path}")
    
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


def preprocess_antismash_files(input_directory: str, output_directory: str = "index") -> Dict[str, Any]:
    """
    Preprocess antiSMASH JSON files and store attributes in SQLite database.
    
    Args:
        input_directory: Directory containing JSON files to process
        output_directory: Directory for output (default: "index")
        
    Returns:
        Dict with processing statistics
    """
    input_path = Path(input_directory)
    
    # Create database in the input directory
    db_path = input_path / "attributes.db"
    conn = create_attributes_database(db_path)
    
    # Process all JSON files
    json_files = list(input_path.glob("*.json"))
    print(f"Found {len(json_files)} JSON files to process...")
    
    total_records = 0
    total_attributes = 0
    files_processed = 0
    
    try:
        for json_file in json_files:
            try:
                print(f"Processing {json_file.name}...")
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
                print(f"  -> Extracted {file_records} records with {len(file_attributes)} attributes")
                
            except Exception as e:
                print(f"Error processing {json_file.name}: {e}")
    
    finally:
        conn.close()
    
    return {
        'files_processed': files_processed,
        'total_records': total_records,
        'total_attributes': total_attributes,
        'database_path': str(db_path)
    }


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess AntiSMASH JSON files and extract attributes into SQLite database"
    )
    parser.add_argument(
        "input_directory",
        help="Directory containing AntiSMASH JSON files"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Validate input directory
    input_path = Path(args.input_directory)
    if not input_path.exists():
        print(f"Error: Input directory '{args.input_directory}' does not exist")
        sys.exit(1)
    
    if not input_path.is_dir():
        print(f"Error: '{args.input_directory}' is not a directory")
        sys.exit(1)
    
    print(f"Processing files in: {input_path}")
    print(f"Database will be created at: {input_path / 'attributes.db'}")
    print("-" * 50)
    
    try:
        results = preprocess_antismash_files(args.input_directory)
        
        # Print results
        print(f"\nProcessing completed!")
        print(f"Files processed: {results['files_processed']}")
        print(f"Total records: {results['total_records']}")
        print(f"Total attributes: {results['total_attributes']}")
        print(f"Database saved to: {results['database_path']}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
