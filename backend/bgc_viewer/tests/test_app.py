import pytest
import json
from bgc_viewer.app import app


@pytest.fixture
def client():
    """Create a test client for the Flask application."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_route(client):
    """Test the main index route."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"BGC Viewer" in response.data


def test_404_handler(client):
    """Test 404 error handling."""
    response = client.get("/nonexistent")
    assert response.status_code == 404
    data = json.loads(response.data)
    assert "error" in data


def test_cors_headers(client):
    """Test that CORS headers are present."""
    # Include an Origin header to trigger CORS response
    response = client.get("/api/version", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    # Flask-CORS should add these headers when Origin is present
    assert "Access-Control-Allow-Origin" in response.headers


def test_scan_folder_hides_tantivy_metadata(client, tmp_path):
    """Generated Tantivy metadata should not appear as index source files."""
    (tmp_path / "record.json").write_text("{}")
    (tmp_path / "meta.json").write_text("{}")
    index_dir = tmp_path / "tantivy.index"
    index_dir.mkdir()
    (index_dir / ".managed.json").write_text("{}")
    (index_dir / "meta.json").write_text("{}")

    response = client.post("/api/scan-folder", json={"path": str(tmp_path)})

    assert response.status_code == 200
    relative_paths = {
        item["relative_path"] for item in response.get_json()["json_files"]
    }
    assert relative_paths == {"meta.json", "record.json"}
