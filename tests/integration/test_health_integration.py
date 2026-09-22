import pytest

pytestmark = pytest.mark.integration


def test_health_and_readiness_with_real_database(integration_client):
    response = integration_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    response = integration_client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_closed_pool_is_not_ready_but_app_is_alive(integration_client, integration_pool):
    # The pool belongs to the app's event loop, so close it there.
    assert integration_client.portal is not None
    integration_client.portal.call(integration_pool.close)

    response = integration_client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}

    response = integration_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
