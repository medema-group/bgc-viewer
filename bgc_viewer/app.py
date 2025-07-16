from flask import Flask, render_template, jsonify
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

# Sample data - replace with your actual data source
SAMPLE_DATA = {
    "users": [
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob", "email": "bob@example.com"},
        {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
    ],
    "stats": {
        "total_users": 3,
        "active_sessions": 12,
        "last_updated": "2025-01-15T10:30:00Z"
    }
}

@app.route('/')
def index():
    """Serve the main HTML page."""
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    """API endpoint to get custom data."""
    return jsonify(SAMPLE_DATA)

@app.route('/api/users')
def get_users():
    """API endpoint to get user list."""
    return jsonify(SAMPLE_DATA["users"])

@app.route('/api/users/<int:user_id>')
def get_user(user_id):
    """API endpoint to get a specific user."""
    user = next((u for u in SAMPLE_DATA["users"] if u["id"] == user_id), None)
    if user:
        return jsonify(user)
    return jsonify({"error": "User not found"}), 404

@app.route('/api/stats')
def get_stats():
    """API endpoint to get application statistics."""
    return jsonify(SAMPLE_DATA["stats"])

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
    # Example: Load from JSON file
    data_file = Path("data/custom_data.json")
    if data_file.exists():
        with open(data_file, 'r') as f:
            return json.load(f)
    return SAMPLE_DATA

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
