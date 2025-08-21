"""
BGC Viewer - A viewer for biosynthetic gene clusters.
"""

# Get version from package metadata
try:
    from importlib.metadata import version
    __version__ = version("bgc-viewer")
except ImportError:
    # Fallback for development/uninstalled package
    __version__ = "0.1.1-dev"

__author__ = "Your Name"
__email__ = "your.email@example.com"

from .app import app

__all__ = ["app"]
