"""
Preprocessing module for AntiSMASH JSON files.

Builds the SQLite record index (file paths and record byte ranges, scanned by
the Rust ``bgc_scanner`` extension) and the sibling Tantivy search index, which
is the only place attribute values are indexed.
"""

import os
import shutil
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional

from . import bgc_scanner
from .search.build_state import building
from .search.document import generate_example_queries
from .search.extraction import extract_documents
from .search.index import build_index, collect_first_values

# Files scanned concurrently. The scanner releases the GIL, so threads scale
# with cores until the disk becomes the bottleneck.
SCAN_WORKERS = min(8, os.cpu_count() or 1)


def create_attributes_database(db_path: Path) -> sqlite3.Connection:
    """Create the SQLite record index database. Drops existing database if it exists."""
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)

    # Create the metadata table for storing preprocessing metadata
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """
    )

    # Create the files table to store file paths
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE
        )
    """
    )

    # Create the file_attributes table for file-level attributes
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS file_attributes (
            file_id INTEGER NOT NULL,
            attribute_name TEXT NOT NULL,
            attribute_value TEXT NOT NULL,
            UNIQUE(file_id, attribute_name, attribute_value),
            FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
        )
    """
    )

    # Create the records table to store record metadata
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            record_id TEXT NOT NULL,
            byte_start INTEGER NOT NULL,
            byte_end INTEGER NOT NULL,
            description TEXT,
            organism TEXT,
            feature_count INTEGER DEFAULT 0,
            region_count INTEGER DEFAULT 0,
            FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
        )
    """
    )

    # Create the search_examples table for generated runnable example queries.
    # It is rebuilt with the rest of the database on every preprocessing run,
    # so the stored examples always belong to the database they are served with.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS search_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template TEXT NOT NULL,
            query TEXT NOT NULL
        )
    """
    )

    # Create indexes for efficient querying
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files (path)")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_attributes_file_id ON file_attributes (file_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_attributes_name ON file_attributes (attribute_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_attributes_value ON file_attributes (attribute_value)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_attributes_name_value ON file_attributes (attribute_name, attribute_value)"
    )

    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_file_id ON records (file_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_record_id ON records (record_id)"
    )

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

    metadata_entries.append(("version", package_version))

    # Store the absolute path of the data root directory
    metadata_entries.append(("data_root", data_root))

    # Store creation and modification timestamps
    current_timestamp = datetime.now().isoformat()
    metadata_entries.append(("creation_date", current_timestamp))
    metadata_entries.append(("modified_date", current_timestamp))

    # Insert metadata entries
    conn.executemany(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", metadata_entries
    )
    conn.commit()


def _insert_file_scan(
    conn: sqlite3.Connection,
    relative_path: str,
    scan: bgc_scanner.FileScan,
    records_before: int,
) -> int:
    """Insert one scanned file and its records; returns the number of records."""
    cursor = conn.execute("INSERT INTO files (path) VALUES (?)", (relative_path,))
    file_id = cursor.lastrowid

    file_attributes = [
        (file_id, name, value)
        for name, value in (("version", scan.version), ("input_file", scan.input_file))
        if value is not None
    ]
    conn.executemany(
        """INSERT INTO file_attributes (file_id, attribute_name, attribute_value)
           VALUES (?, ?, ?)""",
        file_attributes,
    )

    records = scan.records
    conn.executemany(
        """INSERT INTO records
           (file_id, record_id, byte_start, byte_end, description, organism,
            feature_count, region_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                file_id,
                record.record_id or f"record_{records_before + position}",
                record.byte_start,
                record.byte_end,
                record.description,
                record.organism,
                record.feature_count,
                record.region_count,
            )
            for position, record in enumerate(records)
        ],
    )
    return len(records)


def preprocess_antismash_files(
    input_directory: str,
    index_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    json_files: Optional[List[Path]] = None,
    *,
    search_progress_callback: Optional[Callable[[str, int], None]] = None,
) -> Dict[str, Any]:
    """
    Preprocess antiSMASH JSON files into the record index and search index.

    The whole run happens inside a :func:`~bgc_viewer.search.build_state.building`
    block, so the output directory is marked as building before the destructive
    delete inside ``create_attributes_database()`` and stays marked until the
    database and its sibling search index are both complete. A run that raises,
    and a run killed outright, both leave the marker behind so readers report
    the half-built pair as interrupted rather than as never preprocessed.

    Args:
        input_directory: Directory containing JSON files to process
        index_path: Full path to the index database file
        progress_callback: Optional callback function called with (current_file, files_processed, total_files)
        json_files: Optional list of specific JSON file paths to process. If None, all files in directory are processed.
        search_progress_callback: Optional callback receiving Tantivy phase and submitted document count.

    Returns:
        Dict with processing statistics
    """
    # Set up database path
    db_path = Path(index_path)
    # Ensure the directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure .db extension
    if not db_path.suffix == ".db":
        db_path = db_path.with_suffix(".db")

    # The block must close only once the pair is fully built. When step 6 lands,
    # keep it closing after the generated search examples are written so a
    # present sentinel always means the pair is not yet trustworthy.
    with building(db_path.parent):
        return _build_pair(
            input_directory,
            db_path,
            progress_callback,
            json_files,
            search_progress_callback=search_progress_callback,
        )


def _build_pair(
    input_directory: str,
    db_path: Path,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    json_files: Optional[List[Path]] = None,
    *,
    search_progress_callback: Optional[Callable[[str, int], None]] = None,
) -> Dict[str, Any]:
    """Build the SQLite database and its sibling search index at ``db_path``.

    The caller owns the build sentinel; this performs the destructive work.
    """
    sqlite_started = perf_counter()
    input_path = Path(input_directory)

    # Create database at the specified path
    conn = create_attributes_database(db_path)

    # The search index is a fixed sibling of the database; its meta.json must
    # never be treated as a source file when scanning the input directory.
    search_index_dir = db_path.parent / "tantivy.index"
    resolved_index_dir = search_index_dir.resolve()

    def is_index_artifact(path: Path) -> bool:
        return path.resolve().is_relative_to(resolved_index_dir)

    # Populate metadata table with the data root (input directory)
    data_root = str(input_path.absolute())
    populate_metadata_table(conn, data_root)

    # Determine which files to process
    if json_files is not None:
        # Use the provided list of files
        files_to_process = [f for f in json_files if not is_index_artifact(f)]
    else:
        # Find all JSON files (uncompressed and compressed)
        files_to_process = []
        for pattern in ["*.json", "*.json.gz", "*.json.bz2"]:
            files_to_process.extend(
                candidate
                for candidate in input_path.rglob(pattern)
                if not is_index_artifact(candidate)
            )

    total_records = 0
    files_processed = 0

    try:
        with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as executor:
            # Scan in parallel but insert in input order, so file and record
            # ids are deterministic.
            scans = [
                executor.submit(bgc_scanner.scan_file, json_file)
                for json_file in files_to_process
            ]
            for json_file, scan_future in zip(files_to_process, scans):
                try:
                    relative_path = json_file.relative_to(input_path)
                    if progress_callback:
                        progress_callback(
                            str(relative_path), files_processed, len(files_to_process)
                        )
                    total_records += _insert_file_scan(
                        conn, str(relative_path), scan_future.result(), total_records
                    )
                    conn.commit()
                    files_processed += 1
                except Exception as e:
                    # Log error but continue with other files
                    conn.rollback()
                    print(f"Error processing {json_file.name}: {e}")
    finally:
        # Final progress callback
        if progress_callback:
            progress_callback("", files_processed, len(files_to_process))
        conn.close()

    sqlite_seconds = perf_counter() - sqlite_started
    tantivy_started = perf_counter()

    # Build the protocluster search index as a fixed sibling of the database.
    # The source files are the same explicit set used for the SQLite build,
    # resolved to paths relative to the input directory.
    search_files = []
    for json_file in files_to_process:
        resolved = json_file.resolve()
        try:
            relative = resolved.relative_to(input_path.resolve())
        except ValueError:
            # Path outside the source root; the SQLite pass skips it too.
            continue
        if relative.name.endswith((".json", ".json.gz", ".json.bz2")):
            search_files.append(relative)

    # Remove any existing index before rebuilding so a stale index is never
    # paired with a freshly rebuilt database.
    if search_index_dir.exists():
        shutil.rmtree(search_index_dir)

    try:
        index = build_index(
            extract_documents(search_files, input_path),
            search_index_dir,
            progress_callback=search_progress_callback,
        )
    except Exception:
        # A failed build must not leave a partial index artifact.
        if search_index_dir.exists():
            shutil.rmtree(search_index_dir, ignore_errors=True)
        raise

    indexed = index.searcher().num_docs

    # Generate runnable example queries from the freshly built index and store
    # them in the attributes database so the schema endpoint can serve them.
    # This runs inside the caller's build sentinel, which is cleared only after
    # the block returns, so a present sentinel keeps meaning the pair is not yet
    # trustworthy and a failed build leaves no examples behind.
    example_rows = generate_example_queries(collect_first_values(index))
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO search_examples (template, query) VALUES (?, ?)",
            example_rows,
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "sqlite_seconds": sqlite_seconds,
        "tantivy_seconds": perf_counter() - tantivy_started,
        "files_processed": files_processed,
        "total_records": total_records,
        "database_path": str(db_path),
        "indexed_protoclusters": indexed,
        "search_index_path": str(search_index_dir),
        "search_examples": len(example_rows),
    }
