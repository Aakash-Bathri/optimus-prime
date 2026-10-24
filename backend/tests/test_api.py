from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_inventory_round_trip(tmp_path):
    settings = Settings(database_path=tmp_path / "test.sqlite3")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert settings.resolved_database_path.exists()
        page = client.get("/api/resources").json()
        assert page["total"] == 1
        resource = page["items"][0]
        assert resource["provenance"] == "synthetic"
        assert client.get(f"/api/resources/{resource['id']}").json() == resource
        plans = client.get("/api/plans").json()
        assert resource["current_plan_id"] in {plan["id"] for plan in plans}
        assert all(plan["pricing_source"] == "illustrative" for plan in plans)
        assert client.get("/api/resources?environment=development").json()["total"] == 0


def test_errors_and_pagination(tmp_path):
    with TestClient(create_app(Settings(database_path=tmp_path / "test.sqlite3"))) as client:
        assert client.get("/api/resources?offset=1").json()["items"] == []
        for path, status, code in [
            ("/api/resources/missing", 404, "http_404"),
            ("/api/resources?limit=0", 422, "validation_error"),
        ]:
            response = client.get(path)
            assert response.status_code == status
            body = response.json()
            assert body["code"] == code
            assert body["request_id"] == response.headers["X-Request-ID"]

