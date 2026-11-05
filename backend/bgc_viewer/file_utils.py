"""
File system browsing and utility functions for BGC Viewer.
"""

from .search.document import Location


def match_location(location):
    """Match location string to extract start and end coordinates.

    A compound location with introns matches its entire span. A location that
    crosses the origin of a circular record has no single span and does not match.
    """
    try:
        parsed = Location.parse(location)
    except ValueError:
        return None
    if parsed.crosses_origin:
        return None
    return parsed.start, parsed.end
