"""
Database operations for BGC Viewer.
Handles SQLite queries for the attributes database.
"""

import sqlite3
from pathlib import Path


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
                # If no data_root in metadata, use the database's parent directory
                data_root = str(resolved_path.parent)
            
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
                # Each term must match at least one field
                search_condition = """(r.filename LIKE ? OR r.record_id LIKE ? OR r.organism LIKE ? OR r.product LIKE ? 
                                   OR EXISTS (SELECT 1 FROM attributes a2 WHERE a2.record_ref = r.id AND a2.attribute_value LIKE ?))"""
                where_conditions.append(search_condition)
                term_param = f"%{term}%"
                params.extend([term_param, term_param, term_param, term_param, term_param])
        
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
