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
import time
from pathlib import Path
from tqdm import tqdm

# Import the preprocessing function from the package
try:
    from bgc_viewer.preprocessing import preprocess_antismash_files
except ImportError:
    print("Error: Could not import bgc_viewer.preprocessing module.")
    print(
        "Make sure the bgc_viewer package is installed or you're running from the correct directory."
    )
    sys.exit(1)


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.2f}h"


def main():
    """Command-line interface for preprocessing."""
    parser = argparse.ArgumentParser(
        description="Build the SQLite record index and Tantivy search index from antiSMASH JSON files"
    )
    parser.add_argument(
        "input_directory", help="Directory containing AntiSMASH JSON files"
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="index_path",
        help="Path to the output index database file (default: <input_directory>/attributes.db)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=None,
        help=(
            "Processes extracting search documents in parallel "
            "(default: one per CPU). Each holds one decoded record in memory, "
            "so lower this for very large records on machines with little RAM."
        ),
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
        index_path = input_path / "attributes.db"

    print(f"Processing files in: {input_path}")
    print(f"Database will be created at: {index_path}")
    print("-" * 50)

    # Track timing
    start_time = time.perf_counter()

    # Create progress bar (will be initialized with total in the callback)
    pbar = None
    search_pbar = None
    search_phase = None

    # Progress callback using tqdm
    def progress_callback(current_file, files_processed, total_files):
        nonlocal pbar

        # Initialize progress bar on first call
        if pbar is None:
            pbar = tqdm(
                total=total_files,
                desc="SQLite",
                unit="file",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            )

        # Update progress bar
        if current_file:
            # Update with current file info
            pbar.set_postfix_str(
                current_file[:50]
                if len(current_file) <= 50
                else "..." + current_file[-47:]
            )
            pbar.update(1)
        else:
            # Final update
            pbar.close()

    def search_progress_callback(phase, files_done, total_files):
        nonlocal search_pbar, search_phase
        if search_pbar is None:
            search_pbar = tqdm(
                total=total_files,
                desc="Tantivy (indexing)",
                unit="file",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} files [{elapsed}<{remaining}]",
            )
        if phase != search_phase:
            search_pbar.set_description_str(f"Tantivy ({phase})", refresh=False)
            search_phase = phase
        search_pbar.update(files_done - search_pbar.n)
        if phase == "complete":
            search_pbar.close()
        elif phase != "indexing":
            search_pbar.refresh()

    try:
        # Run the preprocessing
        results = preprocess_antismash_files(
            args.input_directory,
            str(index_path),
            progress_callback,
            search_progress_callback=search_progress_callback,
            search_workers=args.jobs,
        )

        # Calculate total time
        total_time = time.perf_counter() - start_time

        # Print summary
        print("\n" + "=" * 50)
        print("PREPROCESSING SUMMARY")
        print("=" * 50)
        print(f"Files processed:     {results['files_processed']}")
        print(f"Total records:       {results['total_records']}")
        print(f"Protoclusters indexed: {results['indexed_protoclusters']}")
        print(f"SQLite time:         {format_duration(results['sqlite_seconds'])}")
        print(f"Tantivy time:        {format_duration(results['tantivy_seconds'])}")
        print(f"Total time:          {format_duration(total_time)}")
        if results["files_processed"] > 0:
            avg_time = total_time / results["files_processed"]
            print(f"Avg time per file:   {avg_time:.2f}s")
        print(f"\nDatabase saved to:   {results['database_path']}")
        print(f"Tantivy index:       {results['search_index_path']}")
        print("=" * 50)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if pbar is not None:
            pbar.close()
        if search_pbar is not None:
            search_pbar.close()


if __name__ == "__main__":
    main()
