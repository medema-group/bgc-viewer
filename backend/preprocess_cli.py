#!/usr/bin/env python3
"""
Command-line wrapper for the BGC Viewer preprocessing functionality.

Usage:
    python preprocess_cli.py <input_directory>

Example:
    python preprocess_cli.py ./data
"""

import sys
import argparse
from pathlib import Path

# Import the preprocessing function from the package
try:
    from bgc_viewer.preprocessing import preprocess_antismash_files
except ImportError:
    print("Error: Could not import bgc_viewer.preprocessing module.")
    print("Make sure the bgc_viewer package is installed or you're running from the correct directory.")
    sys.exit(1)


def main():
    """Command-line interface for preprocessing."""
    parser = argparse.ArgumentParser(
        description="Preprocess AntiSMASH JSON files and extract attributes into SQLite database"
    )
    parser.add_argument(
        "input_directory",
        help="Directory containing AntiSMASH JSON files"
    )
    parser.add_argument(
        "-o", "--output",
        dest="index_path",
        help="Path to the output index database file (default: <input_directory>/attributes.db)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Validate input directory
    input_path = Path(args.input_directory)
    if not input_path.exists():
        print(f"Error: Input directory '{args.input_directory}' does not exist")
        sys.exit(1)
    
    if not input_path.is_dir():
        print(f"Error: '{args.input_directory}' is not a directory")
        sys.exit(1)
    
    # Determine index path
    if args.index_path:
        index_path = Path(args.index_path)
    else:
        index_path = input_path / 'attributes.db'
    
    print(f"Processing files in: {input_path}")
    print(f"Database will be created at: {index_path}")
    print("-" * 50)
    
    # Progress callback for verbose output
    def progress_callback(current_file, files_processed, total_files):
        if args.verbose:
            print(f"Processing {current_file}... ({files_processed + 1}/{total_files})")
        else:
            print(f"Processing {current_file}...")
    
    try:
        # Run the preprocessing
        results = preprocess_antismash_files(
            args.input_directory,
            str(index_path),
            progress_callback
        )
        
        # Print results
        print(f"\nProcessing completed!")
        print(f"Files processed: {results['files_processed']}")
        print(f"Total records: {results['total_records']}")
        print(f"Total attributes: {results['total_attributes']}")
        print(f"Database saved to: {results['database_path']}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
