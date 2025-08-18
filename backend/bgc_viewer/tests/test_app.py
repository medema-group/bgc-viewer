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


def test_api_info_route(client):
    """Test the /api/info endpoint."""
    response = client.get('/api/info')
    assert response.status_code == 200
    data = json.loads(response.data)
    # Could be empty if no data file, but should have consistent structure
    if 'error' not in data:
        assert 'version' in data
        assert 'total_records' in data


def test_api_records_route(client):
    """Test the /api/records endpoint."""
    response = client.get('/api/records')
    assert response.status_code in [200, 404]  # 404 if no data file
    data = json.loads(response.data)
    if response.status_code == 200:
        assert isinstance(data, list)


def test_api_feature_types_route(client):
    """Test the /api/feature-types endpoint."""
    response = client.get('/api/feature-types')
    assert response.status_code in [200, 404]  # 404 if no data file
    data = json.loads(response.data)
    if response.status_code == 200:
        assert isinstance(data, list)


def test_api_stats_route(client):
    """Test the /api/stats endpoint."""
    response = client.get('/api/stats')
    assert response.status_code in [200, 404]  # 404 if no data file
    data = json.loads(response.data)
    if response.status_code == 200:
        assert 'total_records' in data
        assert 'total_features' in data
        assert 'feature_types' in data


def test_health_check_route(client):
    """Test the /api/health endpoint."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert 'message' in data


def test_404_handler(client):
    """Test 404 error handling."""
    response = client.get('/nonexistent')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data


def test_cors_headers(client):
    """Test that CORS headers are present."""
    response = client.get('/api/health')
    assert response.status_code == 200
    # Flask-CORS should add these headers
    assert 'Access-Control-Allow-Origin' in response.headers
