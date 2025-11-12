from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from flask_session import Session
import json
import os
import threading
from pathlib import Path
from typing import Optional
from functools import lru_cache
from waitress import serve
from dotenv import load_dotenv

# Import version from package
from . import __version__
from .preprocessing import preprocess_antismash_files
from .data_loader import load_specific_record
from .file_utils import match_location
from .database import check_database_exists, get_database_entries, get_database_info

# Load environment variables from .env file
load_dotenv()

# Configuration: Determine if running in public or local mode
# PUBLIC mode: Restricted access, no filesystem browsing, fixed data directory or index file.
# LOCAL mode (default): Full access to filesystem, preprocessing, etc.
PUBLIC_MODE = os.getenv('BGCV_PUBLIC_MODE', 'false').lower() == 'true'

# Get the directory where this module is installed
app_dir = Path(__file__).parent
# Look for frontend build directory (in development: ../../frontend/build, in package: static)
frontend_build_dir = app_dir.parent.parent.parent / 'frontend' / 'build'
if not frontend_build_dir.exists():
    # Fallback to package static directory when installed
    frontend_build_dir = app_dir / 'static'

app = Flask(__name__, 
           static_folder=str(frontend_build_dir),
           static_url_path='/static')

# Configure session management
app.config['SECRET_KEY'] = os.getenv('BGCV_SECRET_KEY', os.urandom(24))

if PUBLIC_MODE:
    # Use Redis for production multi-user deployment
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        app.config['SESSION_TYPE'] = 'redis'
        app.config['SESSION_REDIS'] = redis.from_url(redis_url)
        print(f"Using Redis session storage: {redis_url}")
    except ImportError:
        # Fallback to filesystem if redis is not available
        print("Warning: redis not available, falling back to filesystem sessions")
        from cachelib.file import FileSystemCache
        session_dir = os.getenv('SESSION_DIR', '/tmp/bgc_viewer_sessions')
        app.config['SESSION_TYPE'] = 'cachelib'
        app.config['SESSION_CACHELIB'] = FileSystemCache(cache_dir=session_dir)
else:
    # Use filesystem for local development
    from cachelib.file import FileSystemCache
    session_dir = os.getenv('SESSION_DIR', '/tmp/bgc_viewer_sessions')
    app.config['SESSION_TYPE'] = 'cachelib'
    app.config['SESSION_CACHELIB'] = FileSystemCache(cache_dir=session_dir)

app.config['SESSION_PERMANENT'] = False
app.config['SESSION_COOKIE_NAME'] = 'bgc_viewer_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Only use Secure cookies in production with HTTPS
if PUBLIC_MODE and os.getenv('HTTPS_ENABLED', 'false').lower() == 'true':
    app.config['SESSION_COOKIE_SECURE'] = True

Session(app)

# Configure CORS based on mode
if PUBLIC_MODE:
    # In public mode, restrict CORS to specific origins
    allowed_origins = os.getenv('BGCV_ALLOWED_ORIGINS', '*')
    if allowed_origins == '*':
        CORS(app, supports_credentials=True)
    else:
        origins_list = [origin.strip() for origin in allowed_origins.split(',')]
        CORS(app, resources={r"/api/*": {"origins": origins_list}}, supports_credentials=True)
else:
    # In local mode, allow all origins
    CORS(app, supports_credentials=True)

# Define the database path based on mode
# In PUBLIC mode: Fixed database path (index file) - required for multi-user deployment
# In LOCAL mode: None - each session has its own database path
PUBLIC_DATABASE_PATH: Optional[Path] = None

if PUBLIC_MODE:
    # In public mode, database path (index file) is REQUIRED
    db_path_env = os.getenv('BGCV_DATABASE_PATH', 'data/attributes.db')
    PUBLIC_DATABASE_PATH = Path(db_path_env).resolve()
    
    # Verify the database file exists
    if not PUBLIC_DATABASE_PATH.exists():
        raise RuntimeError(
            f"PUBLIC_MODE is enabled but database file does not exist: {PUBLIC_DATABASE_PATH}. "
            f"Set BGCV_DATABASE_PATH environment variable or create the database. "
            f"Use the preprocessing tool to create an index database."
        )
    
    if not PUBLIC_DATABASE_PATH.is_file():
        raise RuntimeError(
            f"PUBLIC_MODE is enabled but BGCV_DATABASE_PATH is not a file: {PUBLIC_DATABASE_PATH}"
        )

# Global variables for preprocessing status (only used in LOCAL_MODE)
PREPROCESSING_STATUS = {
    'is_running': False,
    'current_file': None,
    'files_processed': 0,
    'total_files': 0,
    'status': 'idle',  # 'idle', 'running', 'completed', 'error'
    'error_message': None,
    'folder_path': None
}

# LRU cache for loaded AntiSMASH data to support multiple users efficiently
@lru_cache(maxsize=100)
def load_cached_entry(entry_id: str, db_folder: str, data_dir: str):
    """
    Load and cache AntiSMASH entry data.
    
    Args:
        entry_id: Entry ID in format "filename:record_id"
        db_folder: Folder containing the database
        data_dir: Data directory path
    
    Returns:
        Loaded AntiSMASH data for the specified entry
    """
    filename, record_id = entry_id.split(':', 1)
    file_path = Path(db_folder) / filename
    return load_specific_record(str(file_path), record_id, data_dir)

def get_current_entry_data():
    """
    Get the currently loaded AntiSMASH data for the current session.
    
    Returns:
        Tuple of (data, db_folder, data_dir) or (None, None, None) if no data loaded
    """
    entry_id = session.get('loaded_entry_id')
    if not entry_id:
        return None, None, None
    
    # Determine database path based on mode
    if PUBLIC_MODE:
        db_path = PUBLIC_DATABASE_PATH
    else:
        # In LOCAL_MODE, get from session
        db_path = session.get('current_database_path')
        if not db_path:
            return None, None, None
        db_path = Path(db_path)
    
    # Get database folder and data directory
    db_folder = db_path.parent
    
    # Load data_root from database metadata
    try:
        db_info = get_database_info(str(db_path))
        if "error" in db_info:
            return None, None, None
        data_dir = db_info.get('data_root', str(db_folder))
    except Exception:
        # Fallback to db_folder if metadata can't be read
        data_dir = str(db_folder)
    
    # Load from cache
    try:
        data = load_cached_entry(entry_id, str(db_folder), data_dir)
        return data, db_folder, data_dir
    except Exception:
        return None, None, None



@app.route('/')
def index():
    """Serve the main Vue.js SPA."""
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except FileNotFoundError:
        return jsonify({"error": "Frontend not built or not included in package. Run 'npm run build' in the frontend directory."}), 404

@app.route('/<path:path>')
def spa_fallback(path):
    """Fallback for SPA routing - serve index.html for all non-API routes."""
    if path.startswith('api/'):
        # Let API routes be handled by their specific handlers
        return jsonify({"error": "API endpoint not found"}), 404
    
    # For all other routes, try to serve static files first
    try:
        return send_from_directory(app.static_folder, path)
    except FileNotFoundError:
        # Fallback to index.html for SPA routing
        try:
            return send_from_directory(app.static_folder, 'index.html')
        except FileNotFoundError:
            return jsonify({"error": "Frontend not found - ensure 'npm run build' was executed and static files are included in package"}), 404

@app.route('/api/status')
def get_status():
    """API endpoint to get current file and data loading status."""
    # Determine the current data directory
    current_data_dir = None
    
    if PUBLIC_MODE:
        # In public mode, read data_root from database metadata
        try:
            db_info = get_database_info(str(PUBLIC_DATABASE_PATH))
            if "error" not in db_info:
                current_data_dir = db_info.get('data_root')
        except Exception:
            pass
    else:
        # In local mode, check session database path
        db_path = session.get('current_database_path')
        if db_path:
            try:
                db_info = get_database_info(db_path)
                if "error" not in db_info:
                    current_data_dir = db_info.get('data_root')
            except Exception:
                # Fallback to parent directory
                current_data_dir = str(Path(db_path).parent)
    
    # Check if this session has loaded data
    has_loaded_data = session.get('loaded_entry_id') is not None
    
    return jsonify({
        "has_loaded_data": has_loaded_data,
        "current_data_directory": current_data_dir,
        "public_mode": PUBLIC_MODE
    })

# Filesystem browsing endpoint - only available in local mode
if not PUBLIC_MODE:
    @app.route('/api/browse')
    def browse_filesystem():
        """API endpoint to browse the server's filesystem."""
        path = request.args.get('path', '.')
        
        try:
            # Resolve the path
            resolved_path = Path(path).resolve()
            
            if not resolved_path.exists():
                return jsonify({"error": "Path does not exist"}), 404
                
            if not resolved_path.is_dir():
                return jsonify({"error": "Path is not a directory"}), 400
            
            items = []
            
            # Add parent directory option (except for filesystem root)
            if resolved_path.parent != resolved_path:  # Not at filesystem root
                items.append({
                    "name": "..",
                    "type": "directory",
                    "path": str(resolved_path.parent)
                })
            
            # List directory contents
            for item in sorted(resolved_path.iterdir()):
                try:
                    if item.is_dir():
                        items.append({
                            "name": item.name,
                            "type": "directory", 
                            "path": str(item)
                        })
                    elif item.suffix.lower() == '.json':
                        items.append({
                            "name": item.name,
                            "type": "file",
                            "path": str(item),
                            "size": item.stat().st_size
                        })
                    elif item.suffix.lower() == '.db':
                        items.append({
                            "name": item.name,
                            "type": "database",
                            "path": str(item),
                            "size": item.stat().st_size
                        })
                except (OSError, PermissionError):
                    # Skip items we can't access
                    continue
            
            return jsonify({
                "current_path": str(resolved_path),
                "items": items
            })
            
        except PermissionError:
            return jsonify({"error": "Permission denied"}), 403
        except Exception as e:
            return jsonify({"error": f"Failed to browse directory: {str(e)}"}), 500

if not PUBLIC_MODE:
    @app.route('/api/scan-folder', methods=['POST'])
    def scan_folder_for_json():
        """API endpoint to scan a folder recursively for JSON files."""
        data = request.get_json()
        folder_path = data.get('path')
        
        if not folder_path:
            return jsonify({"error": "No folder path provided"}), 400
        
        try:
            # Resolve the path
            resolved_path = Path(folder_path).resolve()
            
            if not resolved_path.exists():
                return jsonify({"error": "Folder does not exist"}), 404
                
            if not resolved_path.is_dir():
                return jsonify({"error": "Path is not a directory"}), 400
            
            # Scan recursively for JSON files
            json_files = []
            try:
                # Use rglob to recursively find all JSON files
                for json_file in resolved_path.rglob('*.json'):
                    try:
                        if json_file.is_file():
                            # Calculate relative path from the base folder for display
                            relative_path = json_file.relative_to(resolved_path)
                            json_files.append({
                                "name": json_file.name,
                                "path": str(json_file),
                                "relative_path": str(relative_path),
                                "size": json_file.stat().st_size,
                                "directory": str(json_file.parent.relative_to(resolved_path)) if json_file.parent != resolved_path else "."
                            })
                    except (OSError, PermissionError):
                        # Skip files we can't access
                        continue
            except PermissionError:
                return jsonify({"error": "Permission denied to read folder"}), 403
            
            # Sort by relative path for better organization
            json_files.sort(key=lambda x: x['relative_path'])
            
            return jsonify({
                "folder_path": str(resolved_path),
                "json_files": json_files,
                "count": len(json_files),
                "scan_type": "recursive"
            })
            
        except PermissionError:
            return jsonify({"error": "Permission denied"}), 403
        except Exception as e:
            return jsonify({"error": f"Failed to scan folder: {str(e)}"}), 500

@app.route('/api/load-entry', methods=['POST'])
def load_database_entry():
    """Load a specific file+record entry from the database."""
    data = request.get_json()
    entry_id = data.get('id')  # Format: "filename:record_id"
    
    if not entry_id:
        return jsonify({"error": "No entry ID provided"}), 400
    
    try:
        # Parse entry ID
        if ':' not in entry_id:
            return jsonify({"error": "Invalid entry ID format"}), 400
        
        filename, record_id = entry_id.split(':', 1)
        
        # Determine the database path and folders based on mode
        if PUBLIC_MODE:
            db_path = PUBLIC_DATABASE_PATH
        else:
            # In LOCAL_MODE, use session database path
            db_path_str = session.get('current_database_path')
            if db_path_str:
                db_path = Path(db_path_str)
            else:
                # Fallback to data directory
                db_path = Path("data") / "attributes.db"
        
        db_folder = db_path.parent
        file_path = db_folder / filename
        
        # Get data_root from database metadata
        try:
            db_info = get_database_info(str(db_path))
            if "error" not in db_info:
                data_dir = db_info.get('data_root', str(db_folder))
            else:
                data_dir = str(db_folder)
        except Exception:
            data_dir = str(db_folder)
        
        # In public mode, ensure file is within the database folder (security check)
        if PUBLIC_MODE:
            try:
                file_path.resolve().relative_to(db_folder.resolve())
            except ValueError:
                return jsonify({"error": "Access denied: File must be within the database folder"}), 403
        
        if not file_path.exists():
            return jsonify({"error": f"File {filename} not found in database folder"}), 404
        
        # Load the specific record
        modified_data = load_specific_record(str(file_path), record_id, data_dir)
        
        if not modified_data:
            return jsonify({"error": f"Record {record_id} not found in {filename}"}), 404
        
        # Store entry reference in session (not the full data)
        session['loaded_entry_id'] = entry_id
        session['loaded_entry_metadata'] = {
            'filename': filename,
            'record_id': record_id
        }
        
        # Pre-cache the data for this session
        load_cached_entry(entry_id, str(db_folder), data_dir)
        
        # Get the loaded record info
        loaded_record = modified_data["records"][0] if modified_data["records"] else {}
        
        return jsonify({
            "message": f"Successfully loaded {filename}:{record_id}",
            "filename": filename,
            "record_id": record_id,
            "record_info": {
                "id": loaded_record.get("id"),
                "description": loaded_record.get("description"),
                "feature_count": len(loaded_record.get("features", []))
            }
        })
        
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Invalid JSON file: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to load entry: {str(e)}"}), 500

@app.route('/api/records/<record_id>/regions')
def get_record_regions(record_id):
    """API endpoint to get all regions for a specific record."""
    # Get data from session cache
    antismash_data, db_folder, data_dir = get_current_entry_data()
    
    if not antismash_data:
        return jsonify({"error": "No data loaded. Please load an entry first."}), 404
    
    record = next((r for r in antismash_data.get("records", []) if r.get("id") == record_id), None)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    
    # Filter features to get only regions
    regions = []
    for feature in record.get("features", []):
        if feature.get("type") == "region":
            # Parse location to get start/end coordinates
            start, end = match_location(feature.get("location", "")) or (0, 0)
            
            region_info = {
                "id": f"region_{feature.get('qualifiers', {}).get('region_number', ['unknown'])[0]}",
                "region_number": feature.get('qualifiers', {}).get('region_number', ['unknown'])[0],
                "location": feature.get("location"),
                "start": start,
                "end": end,
                "product": feature.get('qualifiers', {}).get('product', ['unknown']),
                "rules": feature.get('qualifiers', {}).get('rules', [])
            }
            regions.append(region_info)
    
    return jsonify({
        "record_id": record_id,
        "regions": sorted(regions, key=lambda x: x['start'])
    })

@app.route('/api/records/<record_id>/regions/<region_id>/features')
def get_region_features(record_id, region_id):
    """API endpoint to get all features within a specific region."""
    # Get data from session cache
    antismash_data, db_folder, data_dir = get_current_entry_data()
    
    if not antismash_data:
        return jsonify({"error": "No data loaded. Please load an entry first."}), 404
    
    record = next((r for r in antismash_data.get("records", []) if r.get("id") == record_id), None)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    
    # Find the region to get its boundaries
    region_feature = None
    for feature in record.get("features", []):
        if (feature.get("type") == "region" and 
            f"region_{feature.get('qualifiers', {}).get('region_number', [''])[0]}" == region_id):
            region_feature = feature
            break
    
    if not region_feature:
        return jsonify({"error": "Region not found"}), 404
    
    # Parse region boundaries
    region_location = region_feature.get("location", "")
    region_start, region_end = match_location(region_location) or (None, None)
    if region_start is None or region_end is None:
        return jsonify({"error": "Invalid region location format"}), 400
    
    # Get optional query parameters
    feature_type = request.args.get('type')
    
    # Filter features that fall within the region boundaries
    region_features = []
    for feature in record.get("features", []):
        # Skip the region feature itself
        if feature.get("type") == "region":
            continue
            
        # Parse feature location
        feature_location = feature.get("location", "")
        feature_start, feature_end = match_location(feature_location) or (None, None)
        if feature_start is None or feature_end is None:
            continue

        # Check if feature overlaps with region (allow partial overlaps)
        if not (feature_end < region_start or feature_start > region_end):
            # Apply type filter if specified
            if feature_type and feature.get("type") != feature_type:
                continue
            region_features.append(feature)
    
    return jsonify({
        "record_id": record_id,
        "region_id": region_id,
        "region_location": region_location,
        "region_boundaries": {"start": region_start, "end": region_end},
        "feature_type": feature_type or "all",
        "count": len(region_features),
        "features": region_features
    })

@app.route('/api/records/<record_id>/features')
def get_record_features(record_id):
    """API endpoint to get all features for a specific record."""
    # Get data from session cache
    antismash_data, db_folder, data_dir = get_current_entry_data()
    
    if not antismash_data:
        return jsonify({"error": "No data loaded. Please load an entry first."}), 404
    
    # Get optional query parameters
    feature_type = request.args.get('type')
    limit = request.args.get('limit', type=int)
    
    record = next((r for r in antismash_data.get("records", []) if r.get("id") == record_id), None)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    
    features = record.get("features", [])
    
    # Filter by type if specified
    if feature_type:
        features = [f for f in features if f.get("type") == feature_type]
    
    # Limit results if specified
    if limit:
        features = features[:limit]
    
    return jsonify({
        "record_id": record_id,
        "feature_type": feature_type or "all",
        "count": len(features),
        "features": features
    })

@app.route('/api/version')
def get_version():
    """API endpoint to get the application version."""
    return jsonify({
        "version": __version__,
        "name": "BGC Viewer"
    })

# Database management endpoints - only available in local mode
if not PUBLIC_MODE:
    @app.route('/api/check-index', methods=['POST'])
    def check_index_status():
        """Check if an SQLite index exists for the given folder."""
        data = request.get_json()
        folder_path = data.get('path')
        
        if not folder_path:
            return jsonify({"error": "No folder path provided"}), 400
        
        try:
            has_index, db_path, result = check_database_exists(folder_path)
            return jsonify(result)
            
        except Exception as e:
            return jsonify({"error": f"Failed to check index status: {str(e)}"}), 500

if not PUBLIC_MODE:
    @app.route('/api/select-database', methods=['POST'])
    def select_database():
        """Select a database file and extract its data_root from metadata."""
        data = request.get_json()
        db_file_path = data.get('path')
        
        if not db_file_path:
            return jsonify({"error": "No database file path provided"}), 400
        
        # Use the database module function to get database info
        result = get_database_info(db_file_path)
        
        if "error" in result:
            status_code = 404 if "does not exist" in result["error"] else 400
            return jsonify(result), status_code
        
        # Store database path in session
        session['current_database_path'] = result["database_path"]
        
        return jsonify({
            "message": "Database selected successfully",
            "database_path": result["database_path"],
            "data_root": result["data_root"],
            "index_stats": result["index_stats"]
        })

if not PUBLIC_MODE:
    @app.route('/api/set-data-root', methods=['POST'])
    def set_data_root():
        """Set the data root path and corresponding database for queries."""
        data = request.get_json()
        folder_path = data.get('path')
        
        if not folder_path:
            return jsonify({"error": "No folder path provided"}), 400
        
        try:
            resolved_path = Path(folder_path).resolve()
            
            if not resolved_path.exists() or not resolved_path.is_dir():
                return jsonify({"error": "Invalid folder path"}), 400
            
            # Check for attributes.db file
            db_path = resolved_path / "attributes.db"
            
            if not db_path.exists():
                return jsonify({"error": "No database found in the specified folder"}), 404
            
            # Store database path in session
            session['current_database_path'] = str(db_path)
            
            return jsonify({
                "message": "Data root set successfully",
                "database_path": str(db_path)
            })
            
        except Exception as e:
            return jsonify({"error": f"Failed to set data root: {str(e)}"}), 500

@app.route('/api/database-entries')
def get_database_entries_endpoint():
    """Get paginated list of all file+record entries from the current database."""
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)  # Max 100 per page
    search = request.args.get('search', '').strip()
    
    # Determine database path based on mode
    if PUBLIC_MODE:
        # In PUBLIC_MODE, use fixed database
        db_path = str(PUBLIC_DATABASE_PATH)
    else:
        # In LOCAL_MODE, get from session
        db_path = session.get('current_database_path')
        if not db_path or not Path(db_path).exists():
            # Fallback: Look for attributes.db in the data directory
            data_dir = Path("data")
            fallback_db_path = data_dir / "attributes.db"
            if fallback_db_path.exists():
                db_path = str(fallback_db_path)
                session['current_database_path'] = db_path
    
    # Use the database module function
    result = get_database_entries(db_path, page, per_page, search)
    
    if "error" in result:
        return jsonify(result), 404 if "No database found" in result["error"] else 500
    
    return jsonify(result)

# Drop database endpoint - only available in local mode
if not PUBLIC_MODE:
    @app.route('/api/drop-database', methods=['POST'])
    def drop_database():
        """Drop/delete the database file for the given folder."""
        data = request.get_json()
        folder_path = data.get('path')
        
        if not folder_path:
            return jsonify({"error": "No folder path provided"}), 400
        
        try:
            resolved_path = Path(folder_path).resolve()
            
            if not resolved_path.exists() or not resolved_path.is_dir():
                return jsonify({"error": "Invalid folder path"}), 400
            
            # Check for attributes.db file
            db_path = resolved_path / "attributes.db"
            
            if db_path.exists():
                # Delete the database file
                db_path.unlink()
                return jsonify({
                    "message": "Database dropped successfully",
                    "database_path": str(db_path)
                })
            else:
                return jsonify({"error": "No database found in the specified folder"}), 404
            
        except Exception as e:
            return jsonify({"error": f"Failed to drop database: {str(e)}"}), 500

# Preprocessing endpoint - only available in local mode
if not PUBLIC_MODE:
    @app.route('/api/preprocess-folder', methods=['POST'])
    def start_preprocessing():
        """Start preprocessing a folder in a background thread."""
        global PREPROCESSING_STATUS
        
        if PREPROCESSING_STATUS['is_running']:
            return jsonify({"error": "Preprocessing is already running"}), 409
        
        data = request.get_json()
        folder_path = data.get('path')
        selected_files = data.get('files')  # Optional list of file paths
        index_path = data.get('index_path')  # Optional custom index file path
        
        if not folder_path:
            return jsonify({"error": "No folder path provided"}), 400
        
        try:
            resolved_path = Path(folder_path).resolve()
            
            if not resolved_path.exists() or not resolved_path.is_dir():
                return jsonify({"error": "Invalid folder path"}), 400
            
            # Validate index path if provided
            resolved_index_path = None
            if index_path:
                resolved_index_path = Path(index_path).resolve()
                # Ensure parent directory exists
                if not resolved_index_path.parent.exists():
                    try:
                        resolved_index_path.parent.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        return jsonify({"error": f"Failed to create index directory: {str(e)}"}), 400
            
            # Determine which files to process
            json_files_to_process = None
            
            if selected_files and len(selected_files) > 0:
                # Use the selected files
                json_files_to_process = [Path(f) for f in selected_files if Path(f).suffix == '.json' and Path(f).exists()]
                if not json_files_to_process:
                    return jsonify({"error": "None of the selected files are valid JSON files"}), 400
                total_count = len(json_files_to_process)
            else:
                # Fallback to all JSON files in the folder (recursive scan)
                all_json_files = list(resolved_path.rglob("*.json"))[:5000]
                if not all_json_files:
                    return jsonify({"error": "No JSON files found in the folder"}), 400
                json_files_to_process = all_json_files
                total_count = len(all_json_files)
            
            # Reset status
            PREPROCESSING_STATUS.update({
                'is_running': True,
                'current_file': None,
                'files_processed': 0,
                'total_files': total_count,
                'status': 'running',
                'error_message': None,
                'folder_path': str(resolved_path)
            })
            
            # Start preprocessing in background thread
            thread = threading.Thread(
                target=run_preprocessing, 
                args=(str(resolved_path), json_files_to_process, str(resolved_index_path) if resolved_index_path else None)
            )
            thread.daemon = True
            thread.start()
            
            return jsonify({
                "message": "Preprocessing started",
                "total_files": total_count,
                "folder_path": str(resolved_path)
            })
            
        except Exception as e:
            PREPROCESSING_STATUS['is_running'] = False
            return jsonify({"error": f"Failed to start preprocessing: {str(e)}"}), 500

@app.route('/api/preprocessing-status')
def get_preprocessing_status():
    """Get the current preprocessing status."""
    return jsonify(PREPROCESSING_STATUS)

def run_preprocessing(folder_path, json_files=None, index_path=None):
    """Run the preprocessing function in a background thread.
    
    Args:
        folder_path: Path to the folder to preprocess
        json_files: Optional list of specific JSON file paths to process
        index_path: Optional full path to the index database file
    """
    global PREPROCESSING_STATUS
    
    def progress_callback(current_file, files_processed, total_files):
        """Update preprocessing status with progress information."""
        PREPROCESSING_STATUS.update({
            'current_file': current_file,
            'files_processed': files_processed,
            'total_files': total_files
        })
    
    try:
        # Run the preprocessing function
        results = preprocess_antismash_files(
            folder_path, 
            progress_callback, 
            json_files,
            index_path
        )
        
        # Update status on completion
        PREPROCESSING_STATUS.update({
            'is_running': False,
            'status': 'completed',
            'current_file': None,
            'files_processed': results['files_processed'],
            'total_files': results['files_processed']  # Final count
        })
            
    except Exception as e:
        PREPROCESSING_STATUS.update({
            'is_running': False,
            'status': 'error',
            'error_message': str(e)
        })

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500

def main():
    """Main entry point for the application."""

    print(f"Starting BGC Viewer version {__version__}")
    print(f"Running in {'PUBLIC' if PUBLIC_MODE else 'LOCAL'} mode")
    
    # Display session configuration
    session_type = app.config.get('SESSION_TYPE', 'unknown')
    print(f"Session storage: {session_type}")
    
    if PUBLIC_MODE:
        print(f"Database path: {PUBLIC_DATABASE_PATH}")
        # Read and display data_root from database metadata
        try:
            db_info = get_database_info(str(PUBLIC_DATABASE_PATH))
            if "error" not in db_info:
                print(f"Data root (from database metadata): {db_info.get('data_root')}")
        except Exception:
            pass
        print("Restricted endpoints: /api/browse, /api/scan-folder, /api/preprocess-folder, /api/check-index, /api/set-data-root")
        print("Multi-user session support: ENABLED")
    else:
        print("Session-based database management: ENABLED")

    host = os.environ.get('BGCV_HOST', 'localhost')
    port = int(os.environ.get('BGCV_PORT', 5005))
    debug_mode = os.getenv('BGCV_DEBUG_MODE', 'False').lower() == 'true'

    if debug_mode:
        print(f"Running in debug mode on http://{host}:{port}")
        app.run(host=host, port=port, debug=True)
    else:
        print(f"Running server on http://{host}:{port}")
        serve(app, host=host, port=port, threads=4)

if __name__ == '__main__':
    main()
