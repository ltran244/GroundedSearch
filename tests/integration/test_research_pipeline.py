import pytest

pytestmark = [pytest.mark.integration, pytest.mark.live]


def test_a_question_produces_an_answer(integration_client):
    response = integration_client.post(
        "/api/v1/research", json={"query": "What is photosynthesis?"}
    )
    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "completed"
    assert job["answer"]
