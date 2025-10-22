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
        
        # Count JSON files in the folder (recursively in subdirectories)
        json_files = list(resolved_path.glob("**/*.json"))
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
                
                # Count distinct files and total records from records table
                cursor = conn.execute("SELECT COUNT(DISTINCT filename) FROM records")
                indexed_files = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM records")
                total_records = cursor.fetchone()[0]
                
                conn.close()
                
                result["index_stats"] = {
                    "indexed_files": indexed_files,
                    "total_records": total_records
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
            # Search in filename, record_id, organism, product, and attribute values
            search_condition = """(r.filename LIKE ? OR r.record_id LIKE ? OR r.organism LIKE ? OR r.product LIKE ? 
                               OR EXISTS (SELECT 1 FROM attributes a2 WHERE a2.record_ref = r.id AND a2.attribute_value LIKE ?))"""
            where_conditions.append(search_condition)
            search_param = f"%{search}%"
            params = [search_param, search_param, search_param, search_param, search_param]
        
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
