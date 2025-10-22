"""
BGC Viewer - A viewer for biosynthetic gene clusters.
"""

# Get version from package metadata
try:
    from importlib.metadata import version
    __version__ = version("bgc-viewer")
except ImportError:
    # Fallback for development/uninstalled package
    __version__ = "0.1.8-dev"

__author__ = "Your Name"
__email__ = "your.email@example.com"

# Don't import app here to avoid circular imports when running with -m
# from .app import app

__all__ = []
