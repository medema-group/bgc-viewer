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
    assert b'My Flask Application' in response.data


def test_api_data_route(client):
    """Test the /api/data endpoint."""
    response = client.get('/api/data')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'users' in data
    assert 'stats' in data
    assert isinstance(data['users'], list)


def test_api_users_route(client):
    """Test the /api/users endpoint."""
    response = client.get('/api/users')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) > 0
    assert 'id' in data[0]
    assert 'name' in data[0]


def test_api_user_by_id_route(client):
    """Test the /api/users/<id> endpoint."""
    # Test existing user
    response = client.get('/api/users/1')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['id'] == 1
    assert 'name' in data
    
    # Test non-existing user
    response = client.get('/api/users/999')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data


def test_api_stats_route(client):
    """Test the /api/stats endpoint."""
    response = client.get('/api/stats')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'total_users' in data
    assert 'active_sessions' in data
    assert 'last_updated' in data


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
