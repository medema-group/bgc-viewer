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
from .database import get_database_entries, get_database_info

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
if PUBLIC_MODE:
    secret_key = os.getenv('BGCV_SECRET_KEY')
    if not secret_key:
        raise RuntimeError("BGCV_SECRET_KEY environment variable must be set in PUBLIC_MODE.")
    app.config['SECRET_KEY'] = secret_key
else:
    app.config['SECRET_KEY'] = os.getenv('BGCV_SECRET_KEY', os.urandom(24))

# Track whether we attempted Redis and fell back to filesystem
REDIS_FALLBACK = False

if PUBLIC_MODE:
    # Use Redis for production multi-user deployment
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        app.config['SESSION_TYPE'] = 'redis'
        app.config['SESSION_REDIS'] = redis.from_url(redis_url)
    except ImportError:
        # Fallback to filesystem if redis is not available
        REDIS_FALLBACK = True
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

# Define hardcoded paths for PUBLIC mode
# In PUBLIC mode: Fixed paths (mounted in Docker container)
# In LOCAL mode: Paths come from session/environment
PUBLIC_INDEX_DIR = "/index"
PUBLIC_DATA_ROOT = "/data_root"

def get_public_database_path():
    """Get the full path to the database file in PUBLIC mode."""
    filename = os.getenv('BGCV_INDEX_FILENAME', 'attributes.db')
    return str(Path(PUBLIC_INDEX_DIR) / filename)

# Preprocessing status tracking (only used in LOCAL_MODE)
if not PUBLIC_MODE:
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
def load_cached_entry(entry_id: str, db_path: str, data_dir: str):
    """
    Load and cache AntiSMASH entry data.
    
    Args:
        entry_id: Entry ID in format "filename:record_id"
        db_path: Full path to the database file (used as cache key)
        data_dir: Data directory path (where the JSON files are located)
    
    Returns:
        Loaded AntiSMASH data for the specified entry
    
    Note:
        The cache key includes db_path to ensure cache invalidation when
        the database changes (important for LOCAL_MODE where users can
        switch between different databases).
    """
    filename, record_id = entry_id.split(':', 1)
    file_path = Path(data_dir) / filename
    return load_specific_record(str(file_path), record_id, data_dir)


def get_current_entry_data():
    """
    Get the currently loaded AntiSMASH data for the current session.
    
    Returns:
        Tuple of (data, data_root) or (None, None) if no data loaded
    """
    entry_id = session.get('loaded_entry_id')
    if not entry_id:
        return None, None
    
    # Determine database path and data root based on mode
    if PUBLIC_MODE:
        db_path = get_public_database_path()
        data_root = PUBLIC_DATA_ROOT
    else:
        # In LOCAL_MODE, get from session
        db_path = session.get('current_database_path')
        if not db_path:
            return None, None
        
        # Load data_root from database metadata
        try:
            db_info = get_database_info(db_path)
            if "error" in db_info:
                return None, None
            data_root = db_info.get('data_root')
            if not data_root:
                # data_root is required
                return None, None
        except Exception:
            # If we can't read metadata, we can't proceed
            return None, None
    
    # Load from cache (using db_path as part of cache key)
    try:
        data = load_cached_entry(entry_id, db_path, data_root)
        return data, data_root
    except Exception:
        return None, None



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
    current_data_root = None
    
    if PUBLIC_MODE:
        # In public mode, use hardcoded data root
        current_data_root = PUBLIC_DATA_ROOT
    else:
        # In local mode, check session database path
        db_path = session.get('current_database_path')
        if db_path:
            db_info = get_database_info(db_path)
            if "error" not in db_info:
                current_data_root = db_info.get('data_root')
    
    # Check if this session has loaded data
    has_loaded_data = session.get('loaded_entry_id') is not None
    
    return jsonify({
        "has_loaded_data": has_loaded_data,
        "current_data_directory": current_data_root,
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
        
        # Determine the database path and data root based on mode
        if PUBLIC_MODE:
            db_path = get_public_database_path()
            data_root = PUBLIC_DATA_ROOT
        else:
            # In LOCAL_MODE, use session database path
            db_path_str = session.get('current_database_path')
            if not db_path_str:
                return jsonify({"error": "No database selected. Please select a database first."}), 400
            db_path = db_path_str
            if not Path(db_path).exists():
                return jsonify({"error": f"Database file does not exist: {db_path_str}"}), 404
            
            # Get data_root from database metadata
            try:
                db_info = get_database_info(db_path)
                if "error" not in db_info:
                    data_root = db_info.get('data_root')
                    if not data_root:
                        return jsonify({"error": "Database metadata missing data_root"}), 500
                else:
                    return jsonify({"error": f"Failed to read database metadata: {db_info.get('error')}"}), 500
            except Exception as e:
                return jsonify({"error": f"Invalid data_root in database metadata: {str(e)}"}), 500
        
        file_path = Path(data_root) / filename
        
        # In public mode, ensure file is within the data root folder (security check)
        if PUBLIC_MODE:
            try:
                file_path.resolve().relative_to(Path(data_root).resolve())
            except ValueError:
                return jsonify({"error": "Access denied: File must be within the data root folder"}), 403
        
        if not file_path.exists():
            return jsonify({"error": f"File {filename} not found in database folder"}), 404
        
        # Load the specific record
        modified_data = load_specific_record(str(file_path), record_id, data_root)
        
        if not modified_data:
            return jsonify({"error": f"Record {record_id} not found in {filename}"}), 404
        
        # Store entry reference in session (not the full data)
        try:
            session['loaded_entry_id'] = entry_id
            session['loaded_entry_metadata'] = {
                'filename': filename,
                'record_id': record_id
            }
        except Exception as e:
            return jsonify({
                "error": f"Failed to save session data: {str(e)}. Session storage may be unavailable."
            }), 503
        
        # Pre-cache the data for this session (using db_path as part of cache key)
        load_cached_entry(entry_id, db_path, data_root)
        
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
    antismash_data, data_root = get_current_entry_data()
    
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
    antismash_data, data_root = get_current_entry_data()
    
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
    antismash_data, data_root = get_current_entry_data()
    
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

@app.route('/api/records/<record_id>/mibig-entries/<locus_tag>')
def get_mibig_entries(record_id, locus_tag):
    """API endpoint to get MiBIG entries for a specific locus_tag.
    
    Returns MiBIG database matches for the specified BGC/locus_tag.
    Data structure: records[i].modules["antismash.modules.clusterblast"]["knowncluster"].mibig_entries["1"][locus_tag]
    """
    # Get data from session cache
    antismash_data, data_root = get_current_entry_data()
    
    if not antismash_data:
        return jsonify({"error": "No data loaded. Please load an entry first."}), 404
    
    # Find the specified record
    record = next((r for r in antismash_data.get("records", []) if r.get("id") == record_id), None)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    
    # Navigate to MiBIG entries: modules -> antismash.modules.clusterblast -> knowncluster -> mibig_entries -> "1" -> locus_tag
    modules = record.get("modules", {})
    print(f"DEBUG: Available modules: {list(modules.keys())}")
    
    clusterblast = modules.get("antismash.modules.clusterblast", {})
    print(f"DEBUG: clusterblast keys: {list(clusterblast.keys())}")
    
    knowncluster = clusterblast.get("knowncluster", {})
    print(f"DEBUG: knowncluster keys: {list(knowncluster.keys())}")
    
    mibig_entries = knowncluster.get("mibig_entries", {})
    print(f"DEBUG: mibig_entries keys: {list(mibig_entries.keys())}")
    
    # Check if "1" key exists (not sure what it refers to yet)
    if "1" not in mibig_entries:
        print(f"DEBUG: '1' key not found in mibig_entries")
        return jsonify({"error": "No MiBIG entries available for this record"}), 404
    
    # Get entries for the specific locus_tag
    print(f"DEBUG: Available locus tags in mibig_entries['1']: {list(mibig_entries['1'].keys())}")
    print(f"DEBUG: Looking for locus_tag: '{locus_tag}'")
    locus_entries = mibig_entries["1"].get(locus_tag, [])
    
    if not locus_entries:
        print(f"DEBUG: No entries found for locus_tag '{locus_tag}'")
        return jsonify({"error": f"No MiBIG entries found for locus_tag '{locus_tag}'"}), 404
    
    print(f"DEBUG: Found {len(locus_entries)} MiBIG entries for '{locus_tag}'")
    
    # Format the entries with proper field names
    # Array format: [MIBiG Protein, Description, MIBiG Cluster, unknown integer, MiBiG Product, % ID, BLAST Score, % Coverage, E-value]
    formatted_entries = []
    for entry in locus_entries:
        if len(entry) >= 9:
            formatted_entries.append({
                "mibig_protein": entry[0],
                "description": entry[1],
                "mibig_cluster": entry[2],
                "rank": entry[3],  # unknown integer - possibly rank/order
                "mibig_product": entry[4],
                "percent_identity": entry[5],
                "blast_score": entry[6],
                "percent_coverage": entry[7],
                "evalue": entry[8]
            })
    
    print(f"DEBUG: Successfully formatted {len(formatted_entries)} entries")
    
    return jsonify({
        "record_id": record_id,
        "locus_tag": locus_tag,
        "count": len(formatted_entries),
        "entries": formatted_entries
    })

# Database management endpoints - only available in local mode
if not PUBLIC_MODE:
    @app.route('/api/select-database', methods=['POST'])
    def select_database():
        """Select a database file and extract its data_root from metadata.
        
        This endpoint sets the database path in the session and returns metadata
        including data_root, index statistics, and version information.
        """
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
        try:
            session['current_database_path'] = result["database_path"]
        except Exception as e:
            return jsonify({
                "error": f"Failed to save session data: {str(e)}. Session storage may be unavailable."
            }), 503
        
        return jsonify({
            "message": "Database selected successfully",
            "database_path": result["database_path"],
            "data_root": result["data_root"],
            "index_stats": result["index_stats"],
            "version": result.get("version", "")
        })

if not PUBLIC_MODE:
    @app.route('/api/check_file_exists', methods=['POST'])
    def check_file_exists():
        """Check if a file exists at the given path.
        
        This is used to warn users if they're about to overwrite an existing index file.
        """
        data = request.get_json()
        file_path = data.get('path')
        
        if not file_path:
            return jsonify({"error": "No file path provided"}), 400
        
        # Check if the file exists
        exists = os.path.exists(file_path) and os.path.isfile(file_path)
        
        return jsonify({"exists": exists})

@app.route('/api/database-entries')
def get_database_entries_endpoint():
    """Get paginated list of all file+record entries from the current database."""
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)  # Max 100 per page
    search = request.args.get('search', '').strip()
    
    # Determine database path based on mode
    if PUBLIC_MODE:
        # In PUBLIC_MODE, use hardcoded database path
        db_path = get_public_database_path()
    else:
        # In LOCAL_MODE, get from session
        db_path = session.get('current_database_path')
        if not db_path:
            return jsonify({"error": "No database selected. Please select a database first."}), 400
        if not Path(db_path).exists():
            return jsonify({"error": f"Database file does not exist: {db_path}"}), 404
    
    # Use the database module function
    result = get_database_entries(db_path, page, per_page, search)
    
    if "error" in result:
        return jsonify(result), 404 if "No database found" in result["error"] else 500
    
    return jsonify(result)

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
        index_path = data.get('index_path')  # Required index file path
        
        if not folder_path:
            return jsonify({"error": "No folder path provided"}), 400
        
        if not index_path:
            return jsonify({"error": "No index path provided"}), 400
        
        try:
            resolved_path = Path(folder_path).resolve()
            
            if not resolved_path.exists() or not resolved_path.is_dir():
                return jsonify({"error": "Invalid folder path"}), 400
            
            # Validate and prepare index path
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
                args=(str(resolved_path), str(resolved_index_path), json_files_to_process)
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

def run_preprocessing(folder_path, index_path, json_files=None):
    """Run the preprocessing function in a background thread.
    
    Args:
        folder_path: Path to the folder to preprocess
        index_path: Full path to the index database file
        json_files: Optional list of specific JSON file paths to process
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
            index_path,
            progress_callback,
            json_files
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
    
    # Validate PUBLIC_MODE configuration
    if PUBLIC_MODE:
        # Verify the index directory exists
        if not Path(PUBLIC_INDEX_DIR).exists():
            raise RuntimeError(
                f"PUBLIC_MODE is enabled but index directory does not exist: {PUBLIC_INDEX_DIR}. "
                f"Ensure the index directory is mounted at this location in your Docker container."
            )
        
        if not Path(PUBLIC_INDEX_DIR).is_dir():
            raise RuntimeError(
                f"PUBLIC_MODE is enabled but index path is not a directory: {PUBLIC_INDEX_DIR}"
            )
        
        # Verify the database file exists
        db_path = get_public_database_path()
        if not Path(db_path).exists():
            raise RuntimeError(
                f"PUBLIC_MODE is enabled but database file does not exist: {db_path}. "
                f"Ensure the database file is present in the mounted index directory."
            )
        
        if not Path(db_path).is_file():
            raise RuntimeError(
                f"PUBLIC_MODE is enabled but database path is not a file: {db_path}"
            )
        
        # Verify the data root exists
        if not Path(PUBLIC_DATA_ROOT).exists():
            raise RuntimeError(
                f"PUBLIC_MODE is enabled but data root does not exist: {PUBLIC_DATA_ROOT}. "
                f"Ensure the data directory is mounted at this location in your Docker container."
            )
        
        if not Path(PUBLIC_DATA_ROOT).is_dir():
            raise RuntimeError(
                f"PUBLIC_MODE is enabled but data root is not a directory: {PUBLIC_DATA_ROOT}"
            )
    
    # Display session configuration
    session_type = app.config.get('SESSION_TYPE', 'unknown')
    print(f"Session storage: {session_type}")
    
    if session_type == 'redis':
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        print(f"Redis URL: {redis_url}")
    elif REDIS_FALLBACK:
        print("WARNING: Redis not available in PUBLIC_MODE, using filesystem sessions as fallback")
        print("         Install redis package (pip install redis) for production use")
    
    if PUBLIC_MODE:
        print(f"Database path: {get_public_database_path()}")
        print(f"Data root: {PUBLIC_DATA_ROOT}")
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
