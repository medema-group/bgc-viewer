"""
Preprocessing module for AntiSMASH JSON files.
Extracts attributes into SQLite database.
"""

import ijson
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.1f}s"


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


def _process_records_batch(conn: sqlite3.Connection, records_batch: List[Dict], attributes_batch: List[tuple], total_attributes: int):
    """
    Process a batch of records and attributes efficiently with single transaction.
    """
    # Insert records one by one to get their IDs (but in a single transaction)
    record_ids = []
    
    for metadata in records_batch:
        cursor = conn.execute(
            """INSERT INTO records 
               (filename, record_id, byte_start, byte_end, feature_count, product, organism, description,
                protocluster_count, proto_core_count, pfam_domain_count, cds_count, cand_cluster_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (metadata['filename'], metadata['record_id'], 
             metadata['byte_start'], metadata['byte_end'],
             metadata['feature_count'], metadata['product'],
             metadata['organism'], metadata['description'],
             metadata['protocluster_count'], metadata['proto_core_count'],
             metadata['pfam_domain_count'], metadata['cds_count'],
             metadata['cand_cluster_count'])
        )
        record_ids.append(cursor.lastrowid)
    
    # Update attributes batch with correct record references
    final_attributes = []
    for record_index, origin, attr_name, attr_value in attributes_batch:
        if record_index < len(record_ids):
            actual_record_id = record_ids[record_index]
            final_attributes.append((actual_record_id, origin, attr_name, attr_value))
    
    # Insert attributes in batch
    if final_attributes:
        conn.executemany(
            """INSERT INTO attributes 
               (record_ref, origin, attribute_name, attribute_value)
               VALUES (?, ?, ?, ?)""",
            final_attributes
        )
    
    # Single commit for the entire batch
    conn.commit()


def _fallback_parse_file(f, filename: str, total_records_so_far: int) -> tuple:
    """
    Fallback parsing method for files that can't be streamed with ijson.
    Uses memory-efficient chunked reading for large files.
    """
    import json
    
    # For fallback, we'll read in chunks and try to find complete records
    # This is still better than loading everything into memory at once
    chunk_size = 1024 * 1024  # 1MB chunks
    buffer = b""
    records_batch = []
    attributes_batch = []
    in_records = False
    brace_count = 0
    record_start = None
    current_record_data = b""
    
    while True:
        chunk = f.read(chunk_size)
        if not chunk:
            break
            
        buffer += chunk
        
        # Simple state machine to find records
        i = 0
        while i < len(buffer):
            char = buffer[i:i+1]
            
            if not in_records:
                # Look for "records" array start
                if buffer[i:i+9] == b'"records"':
                    # Find opening bracket
                    bracket_pos = buffer.find(b'[', i)
                    if bracket_pos != -1:
                        in_records = True
                        i = bracket_pos + 1
                        continue
                i += 1
                continue
            
            # Inside records array
            if char == b'{':
                if brace_count == 0:
                    record_start = i
                    current_record_data = b""
                brace_count += 1
                current_record_data += char
            elif char == b'}':
                brace_count -= 1
                current_record_data += char
                if brace_count == 0 and record_start is not None:
                    # Complete record found
                    try:
                        record = json.loads(current_record_data.decode('utf-8'))
                        record_id = record.get('id', f'record_{total_records_so_far + len(records_batch)}')
                        
                        # Create metadata
                        metadata = extract_record_metadata(
                            record, filename, record_id, record_start, record_start + len(current_record_data)
                        )
                        records_batch.append(metadata)
                        
                        # Extract attributes
                        attributes = extract_attributes_from_record(record, len(records_batch) - 1)
                        for attr in attributes:
                            attributes_batch.append((len(records_batch) - 1, attr[1], attr[2], attr[3]))
                            
                    except Exception:
                        pass  # Skip malformed records
                    
                    record_start = None
                    current_record_data = b""
            elif char == b']' and brace_count == 0 and in_records:
                # End of records array
                break
            else:
                if brace_count > 0:
                    current_record_data += char
            
            i += 1
        
        # Keep only unprocessed part of buffer
        if record_start is not None:
            buffer = buffer[record_start:]
        else:
            buffer = b""
    
    return records_batch, attributes_batch


def _parse_large_file_with_byte_positions(json_file: Path, total_records_so_far: int) -> tuple:
    """
    Parse large files with precise byte position tracking using memory-efficient streaming.
    This maintains fast record loading while handling large files efficiently.
    """
    import json
    
    records_batch = []
    attributes_batch = []
    
    with open(json_file, 'rb') as f:
        # Find the records array start
        chunk_size = 8192
        buffer = b""
        records_start_pos = None
        
        # Scan for records array
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            buffer += chunk
            
            records_pos = buffer.find(b'"records"')
            if records_pos != -1:
                # Find opening bracket
                bracket_pos = buffer.find(b'[', records_pos)
                if bracket_pos != -1:
                    records_start_pos = f.tell() - len(buffer) + bracket_pos + 1
                    break
                    
            # Keep last part of buffer for potential split patterns
            if len(buffer) > 16384:  # Keep 16KB overlap
                buffer = buffer[-8192:]
        
        if records_start_pos is None:
            return records_batch, attributes_batch
        
        # Now parse records with precise byte tracking
        f.seek(records_start_pos)
        brace_count = 0
        record_start = None
        current_pos = records_start_pos
        
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
                
            for i, byte_val in enumerate(chunk):
                char = bytes([byte_val])
                
                if char == b'{':
                    if brace_count == 0:
                        record_start = current_pos + i
                    brace_count += 1
                elif char == b'}':
                    brace_count -= 1
                    if brace_count == 0 and record_start is not None:
                        record_end = current_pos + i + 1
                        
                        # Extract and parse this record
                        f.seek(record_start)
                        record_data = f.read(record_end - record_start)
                        
                        try:
                            record = json.loads(record_data.decode('utf-8'))
                            record_id = record.get('id', f'record_{total_records_so_far + len(records_batch)}')
                            
                            # Create metadata with precise byte positions
                            metadata = extract_record_metadata(
                                record, json_file.name, record_id, record_start, record_end
                            )
                            records_batch.append(metadata)
                            
                            # Extract attributes
                            attributes = extract_attributes_from_record(record, len(records_batch) - 1)
                            for attr in attributes:
                                attributes_batch.append((len(records_batch) - 1, attr[1], attr[2], attr[3]))
                                
                        except Exception:
                            pass  # Skip malformed records
                        
                        # Return to the end of current chunk for continuation
                        f.seek(current_pos + len(chunk))
                        record_start = None
                elif char == b']' and brace_count == 0:
                    # End of records array
                    return records_batch, attributes_batch
                    
            current_pos = f.tell()
    
    return records_batch, attributes_batch


def _parse_file_with_ijson_and_positions(json_file: Path, total_records_so_far: int) -> tuple:
    """
    Parse smaller files using ijson for speed while maintaining byte position accuracy.
    This is a hybrid approach for moderate-sized files.
    """
    import json
    
    records_batch = []
    attributes_batch = []
    
    # For files < 50MB, we can afford to load them for precise byte tracking
    with open(json_file, 'rb') as f:
        content = f.read()
    
    # Find records array boundaries
    records_pattern = b'"records"'
    records_pos = content.find(records_pattern)
    
    if records_pos == -1:
        return records_batch, attributes_batch
    
    # Find the opening bracket of records array
    bracket_pos = content.find(b'[', records_pos)
    
    if bracket_pos != -1:
        # Parse individual records with precise byte positions
        pos = bracket_pos + 1  # Start after opening bracket
        brace_count = 0
        record_start = None
        
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
                        record = json.loads(record_json.decode('utf-8'))
                        record_id = record.get('id', f'record_{total_records_so_far + len(records_batch)}')
                        
                        # Extract record metadata with precise byte positions
                        metadata = extract_record_metadata(
                            record, json_file.name, record_id, record_start, record_end
                        )
                        records_batch.append(metadata)
                        
                        # Extract attributes
                        attributes = extract_attributes_from_record(record, len(records_batch) - 1)
                        for attr in attributes:
                            attributes_batch.append((len(records_batch) - 1, attr[1], attr[2], attr[3]))
                            
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass  # Skip malformed records
                    
                    record_start = None
            elif char == b']' and brace_count == 0:
                # End of records array
                break
            
            pos += 1
    
    return records_batch, attributes_batch


def preprocess_antismash_files(
    input_directory: str, 
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> Dict[str, Any]:
    """
    Preprocess antiSMASH JSON files and store attributes in SQLite database.
    Optimized for large files with streaming and batched database operations.
    
    Args:
        input_directory: Directory containing JSON files to process
        progress_callback: Optional callback function called with (current_file, files_processed, total_files)
        
    Returns:
        Dict with processing statistics including timing information
    """
    # Start timing
    start_time = time.time()
    
    input_path = Path(input_directory)
    
    # Create database in the input directory
    db_path = input_path / "attributes.db"
    conn = create_attributes_database(db_path)
    
    # Process first 100 JSON files only
    json_files = list(input_path.glob("*.json"))[:100]
    total_records = 0
    total_attributes = 0
    files_processed = 0
    
    # Batch size for database operations (reduce transaction overhead)
    BATCH_SIZE = 100
    
    try:
        for json_file in json_files:
            try:
                if progress_callback:
                    progress_callback(json_file.name, files_processed, len(json_files))
                
                # Use streaming approach for large files
                records_batch = []
                attributes_batch = []
                
                # For large files, use precise byte tracking to maintain fast loading
                file_size = json_file.stat().st_size
                
                if file_size > 50 * 1024 * 1024:  # > 50MB, use chunked precise parsing
                    print(f"Large file detected ({file_size // 1024 // 1024}MB), using precise byte tracking...")
                    records_batch, attributes_batch = _parse_large_file_with_byte_positions(
                        json_file, total_records
                    )
                    total_records += len(records_batch)
                else:
                    # For smaller files, use the faster ijson approach but with accurate byte positions
                    records_batch, attributes_batch = _parse_file_with_ijson_and_positions(
                        json_file, total_records
                    )
                    total_records += len(records_batch)
                
                # Process remaining batch
                if records_batch:
                    _process_records_batch(conn, records_batch, attributes_batch, total_attributes)
                    total_attributes += len(attributes_batch)
                
                files_processed += 1
                
            except Exception as e:
                print(f"Error processing {json_file.name}: {e}")
                continue
    
    finally:
        conn.close()
    
    # Calculate timing
    end_time = time.time()
    processing_time = end_time - start_time
    
    return {
        'files_processed': files_processed,
        'total_records': total_records,
        'total_attributes': total_attributes,
        'database_path': str(db_path),
        'processing_time_seconds': round(processing_time, 2),
        'processing_time_formatted': _format_duration(processing_time)
    }
