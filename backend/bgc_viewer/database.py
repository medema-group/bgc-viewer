"""
Database operations for BGC Viewer.
Handles SQLite queries for the record index database.
"""

import sqlite3
from pathlib import Path


def get_database_info(db_file_path):
    """Get information about a database file including data_root and statistics.

    Args:
        db_file_path: Path to the database file (string or Path object)

    Returns:
        Dictionary with database information or error. ``build_id`` is the
        preprocessing timestamp of this database and changes whenever the file
        is rebuilt, which makes it usable as a generation token for caches of
        data derived from it.
    """
    try:
        resolved_path = Path(db_file_path).resolve()

        if not resolved_path.exists():
            return {"error": "Database file does not exist"}

        if not resolved_path.is_file() or resolved_path.suffix.lower() != ".db":
            return {"error": "Path is not a database file"}

        # Try to read information from the database
        try:
            conn = sqlite3.connect(resolved_path)

            # Get data_root from metadata table
            cursor = conn.execute("SELECT value FROM metadata WHERE key = 'data_root'")
            row = cursor.fetchone()

            if row:
                data_root = row[0]
            else:
                # data_root is required in metadata
                conn.close()
                return {"error": "Database metadata missing required 'data_root' field"}

            # Get version from metadata table
            cursor = conn.execute("SELECT value FROM metadata WHERE key = 'version'")
            version_row = cursor.fetchone()
            db_version = version_row[0] if version_row else None

            # Build generation token: rewritten by every preprocessing run, so a
            # rebuild at the same path is distinguishable from the build it
            # replaced. Callers use it to key caches of derived data.
            build_id = None
            for key in ("modified_date", "creation_date"):
                cursor = conn.execute(
                    "SELECT value FROM metadata WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                if row:
                    build_id = row[0]
                    break
            if not build_id:
                # A database predating the timestamp metadata still changes
                # identity when rebuilt in place, so fall back to the file.
                build_id = str(resolved_path.stat().st_mtime_ns)

            # Get index stats
            cursor = conn.execute("SELECT COUNT(*) FROM files")
            indexed_files = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM records")
            total_records = cursor.fetchone()[0]

            conn.close()

            return {
                "database_path": str(resolved_path),
                "data_root": data_root,
                "version": db_version,
                "build_id": build_id,
                "index_stats": {
                    "indexed_files": indexed_files,
                    "total_records": total_records,
                },
            }

        except sqlite3.Error as e:
            return {"error": f"Invalid database file: {str(e)}"}

    except Exception as e:
        return {"error": f"Failed to read database: {str(e)}"}


def get_database_entries(db_path, page=1, per_page=50):
    """Get paginated list of all file+record entries from the database.

    This is a plain listing of the record index. Searching by attribute values
    goes through the Tantivy search index (``/api/search/*``) instead.
    """
    per_page = min(per_page, 100)  # Max 100 per page

    if not db_path or not Path(db_path).exists():
        return {
            "error": "No database found. Please select a folder and preprocess some data first.",
            "entries": [],
            "total": 0,
            "page": page,
            "per_page": per_page,
            "total_pages": 0,
        }

    try:
        conn = sqlite3.connect(db_path)
        try:
            record_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(records)")
            }
            if not {"description", "organism"} <= record_columns:
                return {
                    "error": "This database was created by an older version of "
                    "BGC Viewer. Please run preprocessing again."
                }

            total = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            total_pages = (total + per_page - 1) // per_page
            offset = (page - 1) * per_page

            rows = conn.execute(
                """
                SELECT f.path, r.record_id, r.id, r.description, r.organism,
                       r.feature_count, r.region_count
                FROM records r
                JOIN files f ON r.file_id = f.id
                ORDER BY f.path, r.record_id
                LIMIT ? OFFSET ?
                """,
                (per_page, offset),
            ).fetchall()
        finally:
            conn.close()

        entries = [
            {
                "filename": filename,
                "record_id": record_id,
                "id": f"{filename}:{record_id}",  # Unique identifier for frontend
                "internal_id": internal_id,  # Internal database ID
                "description": description or "",
                "organism": organism or "",
                "feature_count": feature_count or 0,
                "region_count": region_count or 0,
            }
            for (
                filename,
                record_id,
                internal_id,
                description,
                organism,
                feature_count,
                region_count,
            ) in rows
        ]

        return {
            "entries": entries,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    except Exception as e:
        return {"error": f"Failed to query database: {str(e)}"}
