"""
Preprocessing module for AntiSMASH JSON files.
Extracts attributes into SQLite database.
"""

import ijson
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable


def create_attributes_database(db_path: Path) -> sqlite3.Connection:
    """Create SQLite database for storing attributes and record index. Drops existing database if it exists."""
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()
    
    conn = sqlite3.connect(db_path)
    
    # Create the records table to store record metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            record_id TEXT NOT NULL,
            byte_start INTEGER NOT NULL,
            byte_end INTEGER NOT NULL,
            feature_count INTEGER DEFAULT 0,
            product TEXT,
            organism TEXT,
            description TEXT,
            protocluster_count INTEGER DEFAULT 0,
            proto_core_count INTEGER DEFAULT 0,
            pfam_domain_count INTEGER DEFAULT 0,
            cds_count INTEGER DEFAULT 0,
            cand_cluster_count INTEGER DEFAULT 0,
            UNIQUE(filename, record_id)
        )
    """)
    
    # Create the attributes table with reference to records
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_ref INTEGER NOT NULL,  -- Foreign key to records.id
            origin TEXT NOT NULL,         -- 'annotations' or 'source'
            attribute_name TEXT NOT NULL,
            attribute_value TEXT NOT NULL,
            FOREIGN KEY (record_ref) REFERENCES records (id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes for efficient querying
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_filename ON records (filename)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_record_id ON records (record_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_filename_record_id ON records (filename, record_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_product ON records (product)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_organism ON records (organism)")
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attributes_record_ref ON attributes (record_ref)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attributes_origin ON attributes (origin)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attributes_name ON attributes (attribute_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attributes_value ON attributes (attribute_value)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attributes_name_value ON attributes (attribute_name, attribute_value)")
    
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


def extract_record_metadata(record: Dict[str, Any], filename: str, record_id: str, byte_start: int, byte_end: int) -> Dict[str, Any]:
    """
    Extract metadata from a record for the records table.
    
    Returns:
        Dictionary with record metadata
    """
    metadata = {
        'filename': filename,
        'record_id': record_id,
        'byte_start': byte_start,
        'byte_end': byte_end,
        'feature_count': 0,
        'product': None,
        'organism': None,
        'description': record.get('description', None),
        'protocluster_count': 0,
        'proto_core_count': 0,
        'pfam_domain_count': 0,
        'cds_count': 0,
        'cand_cluster_count': 0
    }
    
    # Count features by type
    if 'features' in record and isinstance(record['features'], list):
        metadata['feature_count'] = len(record['features'])
        
        # Count specific feature types
        for feature in record['features']:
            feature_type = feature.get('type', '').lower()
            if feature_type == 'protocluster':
                metadata['protocluster_count'] += 1
            elif feature_type == 'proto_core':
                metadata['proto_core_count'] += 1
            elif feature_type == 'pfam_domain':
                metadata['pfam_domain_count'] += 1
            elif feature_type == 'cds':
                metadata['cds_count'] += 1
            elif feature_type == 'cand_cluster':
                metadata['cand_cluster_count'] += 1
    
    # Extract organism from source features
    if 'features' in record and isinstance(record['features'], list):
        for feature in record['features']:
            if feature.get('type') == 'source' and 'qualifiers' in feature:
                qualifiers = feature['qualifiers']
                if 'organism' in qualifiers:
                    metadata['organism'] = qualifiers['organism'][0] if isinstance(qualifiers['organism'], list) else qualifiers['organism']
                    break
    
    # Extract product from annotations (look for biosynthetic products)
    if 'annotations' in record and isinstance(record['annotations'], dict):
        for region_id, annotation_data in record['annotations'].items():
            if isinstance(annotation_data, dict) and 'product' in annotation_data:
                metadata['product'] = annotation_data['product']
                break
    
    return metadata


def extract_attributes_from_record(record: Dict[str, Any], record_ref_id: int) -> List[tuple]:
    """
    Extract all attributes from a record for the attributes table.
    
    Args:
        record: The record dictionary
        record_ref_id: The internal ID from the records table
    
    Returns:
        List of tuples: (record_ref, origin, attribute_name, attribute_value)
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
                    record_ref_id,
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
                        record_ref_id,
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
    
    # Process first 100 JSON files only
    json_files = list(input_path.glob("*.json"))[:100]
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
                
                # Parse file to extract both attributes and byte positions
                with open(json_file, 'rb') as f:
                    # Read entire file content to track byte positions
                    content = f.read()
                    
                    # Find the records array boundaries
                    records_start_pattern = b'"records"'
                    records_pos = content.find(records_start_pattern)
                    
                    if records_pos != -1:
                        # Find the opening bracket of records array
                        bracket_pos = content.find(b'[', records_pos)
                        
                        if bracket_pos != -1:
                            # Parse individual records and track their byte positions
                            pos = bracket_pos + 1  # Start after opening bracket
                            brace_count = 0
                            record_start = None
                            
                            file_record_data = []
                            
                            while pos < len(content):
                                char = content[pos:pos+1]
                                
                                if char == b'{':
                                    if brace_count == 0:
                                        record_start = pos
                                    brace_count += 1
                                elif char == b'}':
                                    brace_count -= 1
                                    if brace_count == 0 and record_start is not None:
                                        # Found complete record
                                        record_end = pos + 1
                                        
                                        # Parse the record JSON
                                        record_json = content[record_start:record_end]
                                        try:
                                            import json
                                            record = json.loads(record_json.decode('utf-8'))
                                            record_id = record.get('id', f'record_{total_records}')
                                            
                                            # Extract record metadata
                                            metadata = extract_record_metadata(
                                                record, json_file.name, record_id, record_start, record_end
                                            )
                                            file_record_data.append(metadata)
                                            
                                            file_records += 1
                                            total_records += 1
                                            
                                        except (json.JSONDecodeError, UnicodeDecodeError):
                                            # Skip malformed records
                                            pass
                                        
                                        record_start = None
                                elif char == b']' and brace_count == 0:
                                    # End of records array
                                    break
                                
                                pos += 1
                
                # Insert records and then attributes
                if file_record_data:
                    # Insert records first
                    for record_metadata in file_record_data:
                        cursor = conn.execute(
                            """INSERT INTO records 
                               (filename, record_id, byte_start, byte_end, feature_count, product, organism, description,
                                protocluster_count, proto_core_count, pfam_domain_count, cds_count, cand_cluster_count)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (record_metadata['filename'], record_metadata['record_id'], 
                             record_metadata['byte_start'], record_metadata['byte_end'],
                             record_metadata['feature_count'], record_metadata['product'],
                             record_metadata['organism'], record_metadata['description'],
                             record_metadata['protocluster_count'], record_metadata['proto_core_count'],
                             record_metadata['pfam_domain_count'], record_metadata['cds_count'],
                             record_metadata['cand_cluster_count'])
                        )
                        record_internal_id = cursor.lastrowid
                        
                        # Now parse the record again to extract attributes
                        record_start = record_metadata['byte_start']
                        record_end = record_metadata['byte_end']
                        record_json = content[record_start:record_end]
                        
                        try:
                            import json
                            record = json.loads(record_json.decode('utf-8'))
                            
                            # Extract attributes using the internal record ID
                            attributes = extract_attributes_from_record(record, record_internal_id)
                            
                            # Insert attributes for this record
                            if attributes:
                                conn.executemany(
                                    """INSERT INTO attributes 
                                       (record_ref, origin, attribute_name, attribute_value)
                                       VALUES (?, ?, ?, ?)""",
                                    attributes
                                )
                                total_attributes += len(attributes)
                        
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            # Skip malformed records
                            pass
                    
                    conn.commit()
                
                files_processed += 1
                
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
