"""
File system browsing and utility functions for BGC Viewer.
"""

import re


def match_location(location):
    """Match location string to extract start and end coordinates."""
    location_match = re.match(r"\[<?(\d+):>?(\d+)\]", location)
    if location_match:
        start = int(location_match.group(1))
        end = int(location_match.group(2))
        return start, end
    return None
