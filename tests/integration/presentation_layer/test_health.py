from fastapi import status

from tests.resources.api import HEALTH_PATH, HEALTH_READY_PATH, STATUS_KEY


class TestHealth:
    def test_health_alive(self, client):
        response = client.get(HEALTH_PATH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {STATUS_KEY: "alive"}

    def test_health_ready(self, client):
        response = client.get(HEALTH_READY_PATH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {STATUS_KEY: "ready"}
