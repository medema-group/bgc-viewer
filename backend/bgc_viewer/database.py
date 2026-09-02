"""
Database operations for BGC Viewer.
Handles SQLite queries for the attributes database.
"""

import sqlite3
from pathlib import Path

from bgc_viewer.search_index import search_record_ids


def get_database_info(db_file_path):
    """Get information about a database file including data_root and statistics.
    
    Args:
        db_file_path: Path to the database file (string or Path object)
        
    Returns:
        Dictionary with database information or error
    """
    try:
        resolved_path = Path(db_file_path).resolve()
        
        if not resolved_path.exists():
            return {"error": "Database file does not exist"}
        
        if not resolved_path.is_file() or resolved_path.suffix.lower() != '.db':
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
                "index_stats": {
                    "indexed_files": indexed_files,
                    "total_records": total_records
                }
            }
            
        except sqlite3.Error as e:
            return {"error": f"Invalid database file: {str(e)}"}
        
    except Exception as e:
        return {"error": f"Failed to read database: {str(e)}"}


def get_database_entries(db_path, page=1, per_page=50, search=""):
    """Get paginated list of all file+record entries from the database."""
    per_page = min(per_page, 100)  # Max 100 per page
    
    if not db_path or not Path(db_path).exists():
        return {
            "error": "No database found. Please select a folder and preprocess some data first.",
            "entries": [],
            "total": 0,
            "page": page,
            "per_page": per_page,
            "total_pages": 0
        }
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Build query to get records with file paths
        base_query = """
            SELECT 
                f.path as filename, 
                r.record_id,
                r.id as internal_id
            FROM records r
            JOIN files f ON r.file_id = f.id
        """
        count_query = """
            SELECT COUNT(*) FROM records r
            JOIN files f ON r.file_id = f.id
        """
        
        offset = (page - 1) * per_page

        if search.strip():
            record_ids, total = search_record_ids(db_path, search, per_page, offset)
            total_pages = (total + per_page - 1) // per_page
            if not record_ids:
                conn.close()
                return {
                    "entries": [],
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": total_pages,
                    "has_search": True,
                    "search": search,
                }

            placeholders = ",".join("?" for _ in record_ids)
            cursor = conn.execute(
                base_query + f" WHERE r.id IN ({placeholders})", record_ids
            )
            rows_by_id = {row[2]: row for row in cursor.fetchall()}
            rows = [rows_by_id[record_id] for record_id in record_ids]
        else:
            cursor = conn.execute(count_query)
            total = cursor.fetchone()[0]
            total_pages = (total + per_page - 1) // per_page
        
            query = base_query + """
                ORDER BY f.path, r.record_id
                LIMIT ? OFFSET ?
            """
            cursor = conn.execute(query, [per_page, offset])
            rows = cursor.fetchall()

        entries = []

        for row in rows:
            filename, record_id, internal_id = row
            
            entries.append({
                "filename": filename,
                "record_id": record_id,
                "id": f"{filename}:{record_id}",  # Unique identifier for frontend
                "internal_id": internal_id  # Internal database ID
            })
        
        conn.close()
        
        return {
            "entries": entries,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_search": bool(search),
            "search": search
        }
        
    except Exception as e:
        return {"error": f"Failed to query database: {str(e)}"}
