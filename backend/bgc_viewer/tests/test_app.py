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
    # Include an Origin header to trigger CORS response
    response = client.get('/api/version', headers={'Origin': 'http://localhost:3000'})
    assert response.status_code == 200
    # Flask-CORS should add these headers when Origin is present
    assert 'Access-Control-Allow-Origin' in response.headers


def test_antismash_db_proxy(client, monkeypatch):
    """Test that the antiSMASH DB proxy streams the upstream JSON file."""
    import io
    import urllib.request
    requested = []

    def fake_urlopen(url, timeout=None):
        requested.append(url)
        upstream = io.BytesIO(b'{"records": []}')
        upstream.headers = {}
        return upstream

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)
    response = client.get('/api/antismash-db/GCF_000725555.1')
    assert response.status_code == 200
    assert json.loads(response.data) == {"records": []}
    assert requested == [
        'https://antismash-db.secondarymetabolites.org/output/GCF_000725555.1/GCF_000725555.1.json'
    ]


def test_antismash_db_proxy_not_found(client, monkeypatch):
    """Test that a missing accession returns 404."""
    import urllib.error
    import urllib.request

    def fake_urlopen(url, timeout=None):
        raise urllib.error.HTTPError(url, 404, 'Not Found', {}, None)

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)
    response = client.get('/api/antismash-db/GCF_999999999.9')
    assert response.status_code == 404
    assert 'error' in json.loads(response.data)


def test_antismash_db_proxy_invalid_accession(client):
    """Test that accessions with unexpected characters are rejected."""
    response = client.get('/api/antismash-db/..')
    assert response.status_code == 400
