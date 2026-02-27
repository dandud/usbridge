from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api_status():
    """Verify that the API boots up and the status path operates"""
    response = client.get("/api/status")
    assert response.status_code == 200
    assert "version" in response.json()
