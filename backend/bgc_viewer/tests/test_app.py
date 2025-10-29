import pytest
import json
from bgc_viewer.app import app


@pytest.fixture
def client():
    """Create a test client for the Flask application."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_index_route(client):
    """Test the main index route."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'BGC Viewer' in response.data


def test_404_handler(client):
    """Test 404 error handling."""
    response = client.get('/nonexistent')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data


def test_cors_headers(client):
    """Test that CORS headers are present."""
    response = client.get('/api/version')
    assert response.status_code == 200
    # Flask-CORS should add these headers
    assert 'Access-Control-Allow-Origin' in response.headers
