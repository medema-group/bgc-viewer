"""
Preprocessing module for AntiSMASH JSON files.
Extracts attributes into SQLite database.
"""

import sqlite3
import ijson
import gzip
import bz2
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from .file_utils import match_location

# Try to import Rust extension for fast scanning, fall back to Python if not available
try:
    from . import bgc_scanner
    HAS_RUST_SCANNER = True
except ImportError:
    HAS_RUST_SCANNER = False


def open_file(file_path: Path, mode: str = 'rb'):
    """
    Open a file with automatic decompression support.
    Supports .gz (gzip) and .bz2 (bzip2) compressed files.
    
    Args:
        file_path: Path to the file
        mode: File open mode (default 'rb')
        
    Returns:
        File handle with appropriate decompression
    """
    if file_path.suffix == '.gz':
        return gzip.open(file_path, mode)
    elif file_path.suffix == '.bz2':
        return bz2.open(file_path, mode)
    else:
        return open(file_path, mode)


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
    
    # Create the files table to store file paths
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE
        )
    """)
    
    # Create the records table to store record metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            record_id TEXT NOT NULL,
            byte_start INTEGER NOT NULL,
            byte_end INTEGER NOT NULL,
            UNIQUE(file_id, record_id),
            FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
        )
    """)
    
    # Create the features table to store feature metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            location_start INTEGER,
            location_end INTEGER,
            direction INTEGER,
            byte_start INTEGER NOT NULL,
            byte_end INTEGER NOT NULL,
            FOREIGN KEY (record_id) REFERENCES records (id) ON DELETE CASCADE
        )
    """)
    
    # Create the attributes table for file/record/feature attributes
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,           -- 'file', 'record', or 'feature'
            ref_id INTEGER NOT NULL,      -- Foreign key to respective table
            attribute_name TEXT NOT NULL,
            attribute_value TEXT NOT NULL
        )
    """)
    
    # Create indexes for efficient querying
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files (path)")
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_file_id ON records (file_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_record_id ON records (record_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_file_record ON records (file_id, record_id)")
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_features_record_id ON features (record_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_features_type ON features (type)")
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attributes_type ON attributes (type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attributes_ref_id ON attributes (ref_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attributes_name ON attributes (attribute_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attributes_value ON attributes (attribute_value)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attributes_type_ref ON attributes (type, ref_id)")
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
    return {
        'record_id': record_id,
        'byte_start': byte_start,
        'byte_end': byte_end
    }


def extract_features_and_attributes(record: Dict[str, Any], record_db_id: int) -> tuple:
    """
    Extract features and attributes from a record.
    
    Args:
        record: The record dictionary
        record_db_id: The internal ID from the records table
    
    Returns:
        Tuple of (features_list, attributes_list)
        features_list: List of tuples (record_id, type, location_start, location_end, direction, byte_start, byte_end, feature_dict)
        attributes_list: List of tuples (type, ref_id, attribute_name, attribute_value)
    """
    features = []
    attributes = []
    
    # Extract record-level attributes from annotations
    if 'annotations' in record and isinstance(record['annotations'], dict):
        for region_id, annotation_data in record['annotations'].items():
            flattened = flatten_complex_value(annotation_data)
            for attr_name, attr_value in flattened:
                # Prepend region_id to attribute name
                full_attr_name = f"{region_id}_{attr_name}" if attr_name else region_id
                attributes.append((
                    'record',
                    record_db_id,
                    full_attr_name,
                    attr_value
                ))
    
    # Extract record-level attributes from description
    if 'description' in record and record['description']:
        attributes.append((
            'record',
            record_db_id,
            'description',
            record['description']
        ))
    
    # Extract features and feature-level attributes
    if 'features' in record and isinstance(record['features'], list):
        for feature in record['features']:
            feature_type = feature.get('type', '')
            
            # Extract location information
            location_start = None
            location_end = None
            direction = None
            
            if 'location' in feature:
                location = feature['location']
                # Location is a string like "[0:8667507](+)" or "[<0:>8667507](-)"
                if isinstance(location, str):
                    coords = match_location(location)
                    if coords:
                        location_start, location_end, direction = coords
                    if direction is None:
                        direction = 1  # Default to +1 if not specified
            
            # For now, we don't have byte positions for features, set to 0
            # These would be populated if we track feature positions in JSON
            feature_byte_start = 0
            feature_byte_end = 0
            
            # Note: We'll need the feature DB ID to add attributes, so we return
            # features with the full dict for later attribute extraction
            features.append((
                record_db_id,
                feature_type,
                location_start,
                location_end,
                direction,
                feature_byte_start,
                feature_byte_end,
                feature  # Pass the full feature dict for attribute extraction
            ))
    
    return features, attributes


def extract_feature_attributes(feature: Dict[str, Any], feature_db_id: int) -> List[tuple]:
    """
    Extract attributes from a feature.
    
    Args:
        feature: The feature dictionary
        feature_db_id: The internal ID from the features table
    
    Returns:
        List of tuples: (type, ref_id, attribute_name, attribute_value)
    """
    attributes = []
    
    # Extract qualifiers as attributes
    if 'qualifiers' in feature:
        qualifiers = feature['qualifiers']
        flattened = flatten_complex_value(qualifiers)
        for attr_name, attr_value in flattened:
            # Skip 'translation' qualifier
            if attr_name == 'translation':
                continue
            
            # Skip values longer than 100 characters
            if len(attr_value) > 100:
                continue
            
            attributes.append((
                'feature',
                feature_db_id,
                attr_name,
                attr_value
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
        # Find all JSON files (uncompressed and compressed)
        files_to_process = []
        for pattern in ["*.json", "*.json.gz", "*.json.bz2"]:
            files_to_process.extend(input_path.rglob(pattern))
    
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
                
                with open_file(json_file, 'rb') as f:
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
                # Insert file path into files table
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO files (path) VALUES (?)""",
                    (str(relative_path),)
                )
                
                # Get the file_id
                cursor = conn.execute(
                    "SELECT id FROM files WHERE path = ?",
                    (str(relative_path),)
                )
                result = cursor.fetchone()
                file_id = result[0] if result else None
                
                if file_id is None:
                    raise ValueError(f"Failed to get file_id for {relative_path}")
                
                # Insert file-level attributes
                file_attributes = []
                if version is not None:
                    file_attributes.append(('file', file_id, 'version', version))
                if input_file is not None:
                    file_attributes.append(('file', file_id, 'input_file', input_file))
                
                if file_attributes:
                    conn.executemany(
                        """INSERT INTO attributes (type, ref_id, attribute_name, attribute_value)
                           VALUES (?, ?, ?, ?)""",
                        file_attributes
                    )
                
                # Second pass: Stream records and track byte positions
                # Use Rust scanner if available (100x faster), otherwise fall back to Python
                if HAS_RUST_SCANNER and json_file.suffix not in ['.gz', '.bz2']:
                    # Fast Rust-based scanning (only for uncompressed files)
                    # Returns list of (record_start, record_end, [(feat_start, feat_end), ...])
                    records_and_features = bgc_scanner.scan_records_and_features(str(json_file))
                    # Convert to separate lists for compatibility with existing code
                    record_positions = [(r[0], r[1]) for r in records_and_features]
                    # Store feature positions indexed by record
                    feature_positions_by_record = {i: r[2] for i, r in enumerate(records_and_features)}
                else:
                    # Fallback: Python-based scanning (required for compressed files)
                    with open_file(json_file, 'rb') as f:
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
                    feature_positions_by_record = {}  # Python fallback doesn't track features yet
                    
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
                with open_file(json_file, 'rb') as f:
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
                               (file_id, record_id, byte_start, byte_end)
                               VALUES (?, ?, ?, ?)""",
                            (file_id, metadata['record_id'], 
                             metadata['byte_start'], metadata['byte_end'])
                        )
                        record_db_id = cursor.lastrowid
                        
                        if record_db_id is None:
                            continue
                        
                        # Extract features and attributes
                        features, record_attributes = extract_features_and_attributes(record, record_db_id)
                        
                        # Insert record attributes
                        if record_attributes:
                            conn.executemany(
                                """INSERT INTO attributes 
                                   (type, ref_id, attribute_name, attribute_value)
                                   VALUES (?, ?, ?, ?)""",
                                record_attributes
                            )
                            total_attributes += len(record_attributes)
                        
                        # Insert features and their attributes
                        # Get feature byte positions from scanner if available
                        feature_byte_positions = feature_positions_by_record.get(idx, [])
                        
                        for feat_idx, feature_data in enumerate(features):
                            (rec_id, feature_type, loc_start, loc_end, direction, 
                             f_byte_start, f_byte_end, feature_dict) = feature_data
                            
                            # Use scanned byte positions if available
                            if feat_idx < len(feature_byte_positions):
                                f_byte_start, f_byte_end = feature_byte_positions[feat_idx]
                            
                            # Insert feature
                            cursor = conn.execute(
                                """INSERT INTO features 
                                   (record_id, type, location_start, location_end, direction, byte_start, byte_end)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (record_db_id, feature_type, loc_start, loc_end, direction, f_byte_start, f_byte_end)
                            )
                            feature_db_id = cursor.lastrowid
                            
                            # Extract and insert feature attributes
                            if feature_db_id:
                                feature_attributes = extract_feature_attributes(feature_dict, feature_db_id)
                                if feature_attributes:
                                    conn.executemany(
                                        """INSERT INTO attributes 
                                           (type, ref_id, attribute_name, attribute_value)
                                           VALUES (?, ?, ?, ?)""",
                                        feature_attributes
                                    )
                                    total_attributes += len(feature_attributes)
                        
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
