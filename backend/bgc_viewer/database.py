"""
Database operations for BGC Viewer.
Handles SQLite queries for the attributes database.
The database uses SQLite FTS5 (Full-Text Search) for optimized text search performance.
"""

import sqlite3
from pathlib import Path


def sanitize_fts_query(query: str) -> str:
    """
    Sanitize user input for FTS5 MATCH queries.
    Escapes special FTS5 characters and wraps in quotes for phrase search.
    
    Args:
        query: Raw search query from user
        
    Returns:
        Sanitized query safe for FTS5 MATCH
    """
    # Escape quotes by doubling them for FTS5
    query = query.replace('"', '""')
    # Wrap in quotes for phrase search (handles special chars safely)
    return f'"{query}"'


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
            cursor = conn.execute("SELECT COUNT(DISTINCT filename) FROM records")
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


def get_file_metadata(db_path, filename):
    """Get all metadata key-value pairs for a specific file.
    
    Args:
        db_path: Path to the database file
        filename: Name of the file to get metadata for
        
    Returns:
        Dictionary with file metadata key-value pairs
    """
    if not db_path or not Path(db_path).exists():
        return {}
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get all key-value pairs for this file
        cursor = conn.execute(
            """SELECT key, value FROM files WHERE filename = ?""",
            (filename,)
        )
        
        metadata = {}
        for row in cursor.fetchall():
            key, value = row
            # Skip placeholder entries
            if key != '_placeholder':
                metadata[key] = value
        
        conn.close()
        return metadata
        
    except Exception as e:
        print(f"Failed to get file metadata: {str(e)}")
        return {}


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
        
        # Build query to get records with additional stats from attributes
        base_query = """
            SELECT 
                r.filename, 
                r.record_id,
                r.feature_count,
                COALESCE(r.organism, 'Unknown') as organism,
                COALESCE(r.product, '') as product,
                GROUP_CONCAT(DISTINCT CASE WHEN a.attribute_name LIKE '%type' OR a.attribute_name LIKE '%category' THEN a.attribute_value END) as cluster_types,
                r.id
            FROM records r
            LEFT JOIN attributes a ON r.id = a.record_ref
        """
        count_query = """
            SELECT COUNT(*) FROM records r
        """
        
        params = []
        where_conditions = []
        
        # Add search filter if provided
        if search:
            # Split search into multiple terms by space and apply AND logic
            search_terms = search.strip().split()
            
            for term in search_terms:
                # Use FTS5 for attribute search (much faster) and LIKE for metadata fields
                # FTS5 uses MATCH for efficient full-text search
                search_condition = """(r.filename LIKE ? OR r.record_id LIKE ? OR r.organism LIKE ? OR r.product LIKE ? 
                                   OR EXISTS (SELECT 1 FROM attributes_fts 
                                              WHERE attributes_fts MATCH ? 
                                              AND attributes_fts.record_ref = r.id))"""
                where_conditions.append(search_condition)
                term_param = f"%{term}%"
                # Sanitize term for FTS5 (escapes special characters)
                fts_term = sanitize_fts_query(term)
                params.extend([term_param, term_param, term_param, term_param, fts_term])
        
        # Build WHERE clause
        if where_conditions:
            where_clause = " WHERE " + " AND ".join(where_conditions)
            base_query += where_clause
            count_query += where_clause
        
        # Get total count
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Calculate pagination
        total_pages = (total + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        # Get paginated results
        query = base_query + """
            GROUP BY r.id, r.filename, r.record_id, r.feature_count, r.organism, r.product
            ORDER BY r.filename, r.record_id
            LIMIT ? OFFSET ?
        """
        
        cursor = conn.execute(query, params + [per_page, offset])
        entries = []
        
        for row in cursor.fetchall():
            filename, record_id, feature_count, organism, product, cluster_types, internal_id = row
            
            # Handle product - convert single product to list format for compatibility
            products = [product] if product and product.strip() else []
            
            entries.append({
                "filename": filename,
                "record_id": record_id,
                "feature_count": feature_count or 0,
                "organism": organism or "Unknown",
                "products": products,
                "cluster_types": cluster_types.split(',') if cluster_types else [],
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
