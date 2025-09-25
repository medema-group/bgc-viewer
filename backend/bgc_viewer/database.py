"""
Database operations for BGC Viewer.
Handles SQLite queries for the attributes database.
"""

import sqlite3
from pathlib import Path


def check_database_exists(folder_path):
    """Check if an SQLite database exists in the given folder."""
    try:
        resolved_path = Path(folder_path).resolve()
        
        if not resolved_path.exists() or not resolved_path.is_dir():
            return False, None, {}
        
        # Check for attributes.db file
        db_path = resolved_path / "attributes.db"
        has_index = db_path.exists()
        
        # Count JSON files in the folder
        json_files = list(resolved_path.glob("*.json"))
        json_count = len(json_files)
        
        result = {
            "folder_path": str(resolved_path),
            "has_index": has_index,
            "database_path": str(db_path) if has_index else None,
            "json_files_count": json_count,
            "can_preprocess": json_count > 0
        }
        
        # If index exists, get some basic stats
        if has_index:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.execute("SELECT COUNT(*) FROM attributes")
                total_attributes = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(DISTINCT filename) FROM attributes")
                indexed_files = cursor.fetchone()[0]
                
                conn.close()
                
                result["index_stats"] = {
                    "total_attributes": total_attributes,
                    "indexed_files": indexed_files
                }
            except Exception:
                result["index_stats"] = None
        
        return has_index, str(db_path) if has_index else None, result
        
    except Exception:
        return False, None, {}


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
        
        # Build query to get distinct file+record combinations
        base_query = """
            SELECT DISTINCT filename, record_id, 
                   COUNT(*) as attribute_count
            FROM attributes 
        """
        count_query = """
            SELECT COUNT(*) FROM (
                SELECT DISTINCT filename, record_id FROM attributes
        """
        
        params = []
        where_clause = ""
        
        # Add search filter if provided
        if search:
            where_clause = " WHERE (filename LIKE ? OR record_id LIKE ?)"
            search_param = f"%{search}%"
            params = [search_param, search_param]
            base_query += where_clause
            count_query += where_clause
        
        # Complete the count query
        count_query += ")"
        
        # Get total count
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Calculate pagination
        total_pages = (total + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        # Get paginated results
        query = base_query + """
            GROUP BY filename, record_id
            ORDER BY filename, record_id
            LIMIT ? OFFSET ?
        """
        
        cursor = conn.execute(query, params + [per_page, offset])
        entries = []
        
        for row in cursor.fetchall():
            filename, record_id, attr_count = row
            entries.append({
                "filename": filename,
                "record_id": record_id,
                "attribute_count": attr_count,
                "id": f"{filename}:{record_id}"  # Unique identifier for frontend
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
