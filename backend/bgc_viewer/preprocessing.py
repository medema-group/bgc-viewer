"""
Preprocessing module for AntiSMASH JSON files.
Extracts attributes into SQLite database.
"""

import sqlite3
import ijson
import io
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable

# Try to import Rust extension for fast scanning, fall back to Python if not available
try:
    import bgc_scanner
    HAS_RUST_SCANNER = True
except ImportError:
    HAS_RUST_SCANNER = False


def create_attributes_database(db_path: Path) -> sqlite3.Connection:
    """Create SQLite database for storing attributes and record index. Drops existing database if it exists."""
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()
    
    conn = sqlite3.connect(db_path)
    
    # Create the metadata table for storing preprocessing metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    
    # Create the files table to store file-level metadata (key-value pairs per file)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            UNIQUE(filename, key)
        )
    """)
    
    # Create the records table to store record metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_ref INTEGER NOT NULL,
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
            UNIQUE(filename, record_id),
            FOREIGN KEY (file_ref) REFERENCES files (id) ON DELETE CASCADE
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_filename ON files (filename)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_key ON files (key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_filename_key ON files (filename, key)")
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_file_ref ON records (file_ref)")
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


def populate_metadata_table(conn: sqlite3.Connection, data_root: str) -> None:
    """
    Populate the metadata table with preprocessing information.
    
    Args:
        conn: SQLite database connection
        data_root: Absolute path to the data root directory
    """
    metadata_entries = []
    
    # Get package version
    try:
        from importlib.metadata import version
        package_version = version("bgc-viewer")
    except ImportError:
        package_version = "unknown"
    
    metadata_entries.append(('version', package_version))
    
    # Store the absolute path of the data root directory
    metadata_entries.append(('data_root', data_root))
    
    # Insert metadata entries
    conn.executemany(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        metadata_entries
    )
    conn.commit()


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


def extract_record_metadata(record: Dict[str, Any], record_id: str, byte_start: int, byte_end: int) -> Dict[str, Any]:
    """
    Extract metadata from a record for the records table.
    
    Returns:
        Dictionary with record metadata
    """
    metadata: Dict[str, Any] = {
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
    
    # Extract PFAM domains (avoid duplicates)
    if 'features' in record and isinstance(record['features'], list):
        pfam_domains = set()  # Use set to avoid duplicates
        
        for feature in record['features']:
            if feature.get('type') == 'PFAM_domain' and 'qualifiers' in feature:
                qualifiers = feature['qualifiers']
                if 'db_xref' in qualifiers:
                    db_xrefs = qualifiers['db_xref']
                    # Handle both list and single value
                    if not isinstance(db_xrefs, list):
                        db_xrefs = [db_xrefs]
                    
                    for db_xref in db_xrefs:
                        # Only process if it looks like a PFAM identifier (starts with 'PF')
                        db_xref_str = str(db_xref)
                        if db_xref_str.startswith('PF'):
                            # Extract part before the period (e.g., "PF00457.13" -> "PF00457")
                            pfam_id = db_xref_str.split('.')[0]
                            pfam_domains.add(pfam_id)
                if 'description' in qualifiers:
                    description = qualifiers['description']
                    if isinstance(description, list):
                        description = description[0]
                    pfam_domains.add(description)

        # Add unique PFAM domains as attributes
        for pfam_id in pfam_domains:
            attributes.append((
                record_ref_id,
                'pfam',
                'pfam',
                pfam_id
            ))
    
    return attributes


def preprocess_antismash_files(
    input_directory: str,
    index_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    json_files: Optional[List[Path]] = None
) -> Dict[str, Any]:
    """
    Preprocess antiSMASH JSON files and store attributes in SQLite database.
    
    Args:
        input_directory: Directory containing JSON files to process
        index_path: Full path to the index database file
        progress_callback: Optional callback function called with (current_file, files_processed, total_files)
        json_files: Optional list of specific JSON file paths to process. If None, all files in directory are processed.
        
    Returns:
        Dict with processing statistics
    """
    input_path = Path(input_directory)
    
    # Set up database path
    db_path = Path(index_path)
    # Ensure the directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure .db extension
    if not db_path.suffix == '.db':
        db_path = db_path.with_suffix('.db')
    
    # Create database at the specified path
    conn = create_attributes_database(db_path)
    
    # Populate metadata table with the data root (input directory)
    data_root = str(input_path.absolute())
    populate_metadata_table(conn, data_root)
    
    # Determine which files to process
    if json_files is not None:
        # Use the provided list of files
        files_to_process = json_files
    else:
        files_to_process = list(input_path.rglob("*.json"))
    
    total_records = 0
    total_attributes = 0
    files_processed = 0
    
    try:
        for json_file in files_to_process:
            try:
                if progress_callback:
                    relative_path = json_file.relative_to(input_path)
                    progress_callback(str(relative_path), files_processed, len(files_to_process))
                
                file_records = 0
                relative_path = json_file.relative_to(input_path)
                
                # First pass: Use ijson to extract file-level metadata
                version = None
                input_file = None
                
                with open(json_file, 'rb') as f:
                    try:
                        parser = ijson.parse(f)
                        for prefix, event, value in parser:
                            if prefix == 'version' and event == 'string':
                                version = value
                            elif prefix == 'input_file' and event == 'string':
                                input_file = value
                            elif prefix == 'records' and event == 'start_array':
                                # Found records array, stop parsing metadata
                                break
                    except ijson.JSONError:
                        pass
                
                # Insert file-level metadata
                file_metadata = []
                if version is not None:
                    file_metadata.append((str(relative_path), 'version', version))
                if input_file is not None:
                    file_metadata.append((str(relative_path), 'input_file', input_file))
                
                if file_metadata:
                    conn.executemany(
                        """INSERT OR REPLACE INTO files (filename, key, value)
                           VALUES (?, ?, ?)""",
                        file_metadata
                    )
                
                # Get or create a file_ref for the records table
                cursor = conn.execute(
                    "SELECT MIN(id) FROM files WHERE filename = ?",
                    (str(relative_path),)
                )
                result = cursor.fetchone()
                file_ref = result[0] if result and result[0] is not None else None
                
                # If no file metadata was inserted, create a placeholder
                if file_ref is None:
                    cursor = conn.execute(
                        """INSERT INTO files (filename, key, value)
                           VALUES (?, ?, ?)""",
                        (str(relative_path), '_placeholder', '')
                    )
                    file_ref = cursor.lastrowid
                
                # Second pass: Stream records and track byte positions
                # Use Rust scanner if available (100x faster), otherwise fall back to Python
                if HAS_RUST_SCANNER:
                    # Fast Rust-based scanning
                    record_positions = bgc_scanner.scan_records(str(json_file))
                else:
                    # Fallback: Python-based scanning
                    with open(json_file, 'rb') as f:
                        file_content = f.read()
                    
                    # Find where "records" array starts in the file
                    records_key_pos = file_content.find(b'"records"')
                    if records_key_pos == -1:
                        files_processed += 1
                        continue
                    
                    # Find the opening bracket of the records array
                    records_array_start = file_content.find(b'[', records_key_pos)
                    if records_array_start == -1:
                        files_processed += 1
                        continue
                    
                    # Manually track byte positions by scanning the file content
                    pos = records_array_start + 1  # Start after '['
                    brace_depth = 0
                    record_start = None
                    in_string = False
                    escape_next = False
                    
                    record_positions = []
                    
                    for i in range(pos, len(file_content)):
                        byte = file_content[i:i+1]
                        
                        # Handle string boundaries (to avoid counting braces inside strings)
                        if escape_next:
                            escape_next = False
                            continue
                        
                        if byte == b'\\':
                            escape_next = True
                            continue
                        
                        if byte == b'"':
                            in_string = not in_string
                            continue
                        
                        if in_string:
                            continue
                        
                        # Track brace depth
                        if byte == b'{':
                            if brace_depth == 0:
                                record_start = i
                            brace_depth += 1
                        elif byte == b'}':
                            brace_depth -= 1
                            if brace_depth == 0 and record_start is not None:
                                record_end = i + 1
                                record_positions.append((record_start, record_end))
                                record_start = None
                        elif byte == b']' and brace_depth == 0:
                            break
                
                # Now parse records with ijson using the tracked positions
                with open(json_file, 'rb') as f:
                    records_iter = ijson.items(f, 'records.item')
                    
                    for idx, record in enumerate(records_iter):
                        if idx >= len(record_positions):
                            # More records from ijson than positions found - this is an error
                            raise ValueError(
                                f"Mismatch in {json_file.name}: ijson found more records than byte positions. "
                                f"Expected at most {len(record_positions)} records but found at least {idx + 1}."
                            )
                        
                        record_start, record_end = record_positions[idx]
                        record_id = record.get('id', f'record_{total_records}')
                        
                        # Extract record metadata
                        metadata = extract_record_metadata(
                            record, record_id, record_start, record_end
                        )
                        
                        # Insert record
                        cursor = conn.execute(
                            """INSERT INTO records 
                               (file_ref, filename, record_id, byte_start, byte_end, feature_count, product, organism, description,
                                protocluster_count, proto_core_count, pfam_domain_count, cds_count, cand_cluster_count)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (file_ref, str(relative_path), metadata['record_id'], 
                             metadata['byte_start'], metadata['byte_end'],
                             metadata['feature_count'], metadata['product'],
                             metadata['organism'], metadata['description'],
                             metadata['protocluster_count'], metadata['proto_core_count'],
                             metadata['pfam_domain_count'], metadata['cds_count'],
                             metadata['cand_cluster_count'])
                        )
                        record_internal_id = cursor.lastrowid
                        
                        if record_internal_id is None:
                            continue
                        
                        # Extract and insert attributes
                        attributes = extract_attributes_from_record(record, record_internal_id)
                        
                        if attributes:
                            conn.executemany(
                                """INSERT INTO attributes 
                                   (record_ref, origin, attribute_name, attribute_value)
                                   VALUES (?, ?, ?, ?)""",
                                attributes
                            )
                            total_attributes += len(attributes)
                        
                        file_records += 1
                        total_records += 1
                    
                    # Verify counts match exactly
                    actual_record_count = idx + 1 if 'idx' in locals() else 0
                    if len(record_positions) != actual_record_count:
                        raise ValueError(
                            f"Record count mismatch in {json_file.name}: "
                            f"found {len(record_positions)} byte positions but ijson parsed {actual_record_count} records"
                        )
                    
                    conn.commit()
                
                files_processed += 1
                
            except Exception as e:
                # Log error but continue with other files
                print(f"Error processing {json_file.name}: {e}")
    
    finally:
        # Final progress callback
        if progress_callback:
            progress_callback("", files_processed, len(files_to_process))
        conn.close()
    
    return {
        'files_processed': files_processed,
        'total_records': total_records,
        'total_attributes': total_attributes,
        'database_path': str(db_path)
    }
