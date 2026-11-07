"""Exercise the real application lifespan and route registration, without a DB."""
from fastapi.testclient import TestClient
from main import app


def test_application_starts_and_exposes_critical_routes():
    with TestClient(app) as client:
        response = client.get('/openapi.json')
        assert response.status_code == 200
        schema = response.json()
        paths = schema['paths']
        for suffix, method in [('/s3_directory/pending_deletions', 'get'),
                               ('/s3_directory/retry_deletion', 'post'),
                               ('/image/upload', 'post')]:
            matches = [path for path in paths if path.endswith(suffix)]
            assert len(matches) == 1
            assert method in paths[matches[0]]
