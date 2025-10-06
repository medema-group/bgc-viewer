"""
File system browsing and utility functions for BGC Viewer.
"""

import re
from pathlib import Path


def get_available_files(data_dir="data"):
    """Get list of available JSON files in the data directory."""
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return []
    
    json_files = []
    for file_path in data_dir.glob("*.json"):
        json_files.append(file_path.name)
    
    return sorted(json_files)


def match_location(location):
    """Match location string to extract start and end coordinates."""
    location_match = re.match(r"\[<?(\d+):>?(\d+)\]", location)
    if location_match:
        start = int(location_match.group(1))
        end = int(location_match.group(2))
        return start, end
    return None
