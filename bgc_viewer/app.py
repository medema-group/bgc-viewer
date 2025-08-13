from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import os
from pathlib import Path
from waitress import serve
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

def load_antismash_data():
    """Load AntiSMASH JSON data from file."""
    data_file = Path("data/C178.transcripts.antismash8.output.json")
    if data_file.exists():
        with open(data_file, 'r') as f:
            return json.load(f)
    return None

# Load the data once at startup
ANTISMASH_DATA = load_antismash_data()

@app.route('/')
def index():
    """Serve the SPA."""
    return app.send_static_file('dist/index.html')

@app.route('/<path:path>')
def spa_fallback(path):
    """Fallback for SPA routing - serve index.html for all non-API routes."""
    if path.startswith('api/'):
        # Let API routes be handled by their specific handlers
        return jsonify({"error": "Not found"}), 404
    return app.send_static_file('dist/index.html')

@app.route('/api/info')
def get_info():
    """API endpoint to get basic information about the dataset."""
    if not ANTISMASH_DATA:
        return jsonify({"error": "AntiSMASH data not found"}), 404
    
    return jsonify({
        "version": ANTISMASH_DATA.get("version"),
        "input_file": ANTISMASH_DATA.get("input_file"),
        "taxon": ANTISMASH_DATA.get("taxon"),
        "total_records": len(ANTISMASH_DATA.get("records", [])),
        "schema": ANTISMASH_DATA.get("schema")
    })

@app.route('/api/records')
def get_records():
    """API endpoint to get list of all records (regions)."""
    if not ANTISMASH_DATA:
        return jsonify({"error": "AntiSMASH data not found"}), 404
    
    records = []
    for record in ANTISMASH_DATA.get("records", []):
        records.append({
            "id": record.get("id"),
            "description": record.get("description"),
            "gc_content": record.get("gc_content"),
            "feature_count": len(record.get("features", []))
        })
    
    return jsonify(records)

@app.route('/api/records/<record_id>')
def get_record(record_id):
    """API endpoint to get a specific record."""
    if not ANTISMASH_DATA:
        return jsonify({"error": "AntiSMASH data not found"}), 404
    
    record = next((r for r in ANTISMASH_DATA.get("records", []) if r.get("id") == record_id), None)
    if record:
        return jsonify(record)
    return jsonify({"error": "Record not found"}), 404

@app.route('/api/records/<record_id>/features')
def get_record_features(record_id):
    """API endpoint to get all features for a specific record."""
    if not ANTISMASH_DATA:
        return jsonify({"error": "AntiSMASH data not found"}), 404
    
    # Get optional query parameters
    feature_type = request.args.get('type')
    limit = request.args.get('limit', type=int)
    
    record = next((r for r in ANTISMASH_DATA.get("records", []) if r.get("id") == record_id), None)
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

@app.route('/api/feature-types')
def get_feature_types():
    """API endpoint to get all available feature types across all records."""
    if not ANTISMASH_DATA:
        return jsonify({"error": "AntiSMASH data not found"}), 404
    
    feature_types = set()
    for record in ANTISMASH_DATA.get("records", []):
        for feature in record.get("features", []):
            if "type" in feature:
                feature_types.add(feature["type"])
    
    return jsonify(sorted(list(feature_types)))

@app.route('/api/stats')
def get_stats():
    """API endpoint to get statistics about the dataset."""
    if not ANTISMASH_DATA:
        return jsonify({"error": "AntiSMASH data not found"}), 404
    
    # Calculate statistics
    records = ANTISMASH_DATA.get("records", [])
    total_features = sum(len(r.get("features", [])) for r in records)
    
    feature_type_counts = {}
    for record in records:
        for feature in record.get("features", []):
            ftype = feature.get("type", "unknown")
            feature_type_counts[ftype] = feature_type_counts.get(ftype, 0) + 1
    
    return jsonify({
        "total_records": len(records),
        "total_features": total_features,
        "feature_types": feature_type_counts,
        "version": ANTISMASH_DATA.get("version"),
        "schema": ANTISMASH_DATA.get("schema")
    })

@app.route('/api/health')
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "message": "Server is running"})

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500

def load_custom_data():
    """Load custom data from a file or database."""
    # This function is deprecated - now using ANTISMASH_DATA
    return load_antismash_data()

def main():
    """Main entry point for the application."""

    host = os.environ.get('BGCV_HOST', 'localhost')
    port = int(os.environ.get('BGCV_PORT', 5005))
    debug_mode = os.getenv('BGCV_DEBUG_MODE', 'False').lower() == 'true'

    if debug_mode:
        print(f"Running in debug mode on {host}:{port}")
        app.run(host=host, port=port, debug=True)
    else:
        print(f"Running server on {host}:{port}")
        serve(app, host=host, port=port, threads=4)

if __name__ == '__main__':
    main()
