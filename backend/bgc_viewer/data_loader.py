"""
Data loading and parsing utilities for BGC Viewer.
Handles efficient JSON parsing using ijson with fallback to standard json.
Supports fast random access using byte position indexing.
"""

import json
import ijson
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any


def load_antismash_data(filename=None, data_dir="data"):
    """Load AntiSMASH JSON data from file using ijson for better performance."""
    if filename is None:
        # Default to Y16952.json if no file specified
        filename = "Y16952.json"
    
    data_file = Path(data_dir) / filename
    if data_file.exists():
        try:
            # Use ijson for efficient parsing
            with open(data_file, 'rb') as f:
                # Parse the entire structure efficiently
                parser = ijson.parse(f)
                data = _build_data_structure(parser)
                return data
        except Exception as e:
            # Fallback to regular json if ijson fails
            print(f"ijson parsing failed for {filename}, falling back to json: {e}")
            with open(data_file, 'r') as f:
                return json.load(f)
    return None


def load_json_file(file_path):
    """Load a JSON file using ijson with fallback to standard json."""
    try:
        # Use ijson for efficient parsing
        with open(file_path, 'rb') as f:
            parser = ijson.parse(f)
            data = _build_data_structure(parser)
            return data
    except Exception as e:
        # Fallback to regular json if ijson fails
        print(f"ijson parsing failed for {file_path}, falling back to json: {e}")
        with open(file_path, 'r') as f:
            return json.load(f)


def get_record_index(file_path: str, data_dir: str = "data") -> Optional[sqlite3.Connection]:
    """Get database connection for record index."""
    data_path = Path(data_dir)
    db_path = data_path / "attributes.db"
    
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            return conn
        except sqlite3.Error:
            return None
    return None


def load_record_by_index(file_path: str, target_record_id: str, data_dir: str = "data") -> Optional[Dict[str, Any]]:
    """
    Load a specific record using byte position index for fast random access.
    
    Args:
        file_path: Path to the JSON file
        target_record_id: ID of the record to load
        data_dir: Directory containing the index database
        
    Returns:
        Dictionary containing file metadata and the target record
    """
    conn = get_record_index(file_path, data_dir)
    if not conn:
        return load_specific_record_fallback(file_path, target_record_id)
    
    try:
        # Query the records table for byte positions
        cursor = conn.execute(
            """SELECT byte_start, byte_end FROM records 
               WHERE filename = ? AND record_id = ?""",
            (Path(file_path).name, target_record_id)
        )
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return None
        
        byte_start, byte_end = result['byte_start'], result['byte_end']
        
        # Load the specific record using byte positions (skip metadata for performance)
        with open(file_path, 'rb') as f:
            f.seek(byte_start)
            record_bytes = f.read(byte_end - byte_start)
            
            try:
                record_data = json.loads(record_bytes.decode('utf-8'))
                conn.close()
                
                return {
                    "records": [record_data]
                }
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                conn.close()
                return load_specific_record_fallback(file_path, target_record_id)
    
    except Exception as e:
        if conn:
            conn.close()
        return load_specific_record_fallback(file_path, target_record_id)


def load_specific_record(file_path, target_record_id, data_dir="data"):
    """Load only a specific record from a JSON file for better performance."""
    # Try index-based loading first
    result = load_record_by_index(file_path, target_record_id, data_dir)
    if result:
        return result

    # Fallback to original method
    return load_specific_record_fallback(file_path, target_record_id)
def load_specific_record_fallback(file_path, target_record_id):
    """Fallback method for loading specific record without index."""
    try:
        with open(file_path, 'rb') as f:
            # Use ijson to parse and extract only the needed record
            # First pass: get metadata
            metadata = {}
            for key, value in ijson.kvitems(f, ''):
                if key != 'records':
                    metadata[key] = value
            
            # Second pass: find the target record
            f.seek(0)
            records = ijson.items(f, 'records.item')
            target_record = None
            
            for record in records:
                if record.get('id') == target_record_id:
                    target_record = record
                    break
            
            if target_record:
                return {
                    **metadata,
                    "records": [target_record]
                }
            else:
                return None
                
    except Exception as e:
        print(f"Optimized record loading failed: {e}, falling back to full file load")
        # Fallback to loading the full file
        try:
            with open(file_path, 'r') as f:
                full_data = json.load(f)
            
            # Find the specific record
            for record in full_data.get("records", []):
                if record.get("id") == target_record_id:
                    return {
                        **full_data,
                        "records": [record]
                    }
            return None
        except Exception as fallback_error:
            print(f"Fallback loading also failed: {fallback_error}")
            return None


def list_available_records(filename: Optional[str] = None, data_dir: str = "data") -> Dict[str, Any]:
    """
    List all available records from the index database.
    
    Args:
        filename: Optional specific filename to filter by
        data_dir: Directory containing the index database
        
    Returns:
        Dictionary with file information and available records
    """
    conn = get_record_index("", data_dir)
    if not conn:
        return {"error": "No index database found. Run preprocessing first."}
    
    try:
        if filename:
            # Get records for specific file
            cursor = conn.execute(
                """SELECT record_id FROM records 
                   WHERE filename = ? ORDER BY record_id""",
                (filename,)
            )
        else:
            # Get all records grouped by file
            cursor = conn.execute(
                """SELECT filename, record_id FROM records 
                   ORDER BY filename, record_id"""
            )
        
        results = cursor.fetchall()
        conn.close()
        
        if filename:
            # Return records for specific file
            return {
                "filename": filename,
                "records": [{"id": row[0]} for row in results]
            }
        else:
            # Group by filename
            files: Dict[str, list] = {}
            for row in results:
                file_name = row[0]  # filename
                record_id = row[1]  # record_id
                if file_name not in files:
                    files[file_name] = []
                files[file_name].append({"id": record_id})
            return {"files": files}
    
    except Exception as e:
        if conn:
            conn.close()
        return {"error": f"Failed to query index: {e}"}


def get_record_metadata_from_index(filename: str, record_id: str, data_dir: str = "data") -> Optional[Dict[str, Any]]:
    """
    Get record metadata from index without loading the full record.
    
    Args:
        filename: Name of the file containing the record
        record_id: ID of the record
        data_dir: Directory containing the index database
        
    Returns:
        Dictionary with record metadata or None if not found
    """
    conn = get_record_index("", data_dir)
    if not conn:
        return None
    
    try:
        cursor = conn.execute(
            """SELECT filename, record_id, byte_start, byte_end FROM records 
               WHERE filename = ? AND record_id = ? LIMIT 1""",
            (filename, record_id)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                "filename": result[0],
                "record_id": result[1], 
                "byte_start": result[2],
                "byte_end": result[3],
                "size_bytes": result[3] - result[2]
            }
        return None
    
    except Exception as e:
        if conn:
            conn.close()
        return None


def _build_data_structure(parser):
    """Build data structure from ijson parser events."""
    data = {}
    stack = [data]
    path_stack = []
    
    for prefix, event, value in parser:
        if event == 'start_map':
            if prefix:
                # Navigate to the correct location in the structure
                current = _navigate_to_path(data, prefix.split('.'))
                new_dict = {}
                if isinstance(current, list):
                    current.append(new_dict)
                else:
                    key = prefix.split('.')[-1]
                    current[key] = new_dict
                stack.append(new_dict)
            else:
                stack.append(data)
        elif event == 'end_map':
            if stack:
                stack.pop()
        elif event == 'start_array':
            if prefix:
                current = _navigate_to_path(data, prefix.split('.')[:-1])
                key = prefix.split('.')[-1]
                current[key] = []
                stack.append(current[key])
        elif event == 'end_array':
            if stack:
                stack.pop()
        elif event in ('string', 'number', 'boolean', 'null'):
            if prefix:
                path_parts = prefix.split('.')
                if path_parts[-1].isdigit():  # Array index
                    # Handle array elements
                    parent_path = path_parts[:-1]
                    parent = _navigate_to_path(data, parent_path)
                    if isinstance(parent, list):
                        # Extend list if necessary
                        index = int(path_parts[-1])
                        while len(parent) <= index:
                            parent.append(None)
                        parent[index] = value
                else:
                    # Handle object properties
                    parent_path = path_parts[:-1]
                    key = path_parts[-1]
                    parent = _navigate_to_path(data, parent_path)
                    if isinstance(parent, dict):
                        parent[key] = value
            else:
                # Root level value
                return value
    
    return data


def _navigate_to_path(data, path_parts):
    """Navigate to a specific path in the data structure."""
    current = data
    for part in path_parts:
        if part == '':
            continue
        if part.isdigit():
            # Array index
            index = int(part)
            if isinstance(current, list):
                while len(current) <= index:
                    current.append({})
                current = current[index]
        else:
            # Object key
            if isinstance(current, dict):
                if part not in current:
                    current[part] = {}
                current = current[part]
    return current
