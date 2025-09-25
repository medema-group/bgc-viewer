"""
Data loading and parsing utilities for BGC Viewer.
Handles efficient JSON parsing using ijson with fallback to standard json.
"""

import json
import ijson
from pathlib import Path


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


def load_specific_record(file_path, target_record_id):
    """Load only a specific record from a JSON file for better performance."""
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
