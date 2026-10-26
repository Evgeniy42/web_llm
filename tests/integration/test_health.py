from fastapi import status


class TestHealth:
    def test_health_alive(self, client):
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "alive"}

    def test_health_ready(self, client):
        response = client.get("/health/ready")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ready"}
