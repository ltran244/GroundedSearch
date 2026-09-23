import time

import pytest

# Real Gemini and Brave calls: one question costs a Gemini call for the
# queries, 3-5 Brave searches, and a second Gemini call for the answer.
pytestmark = [pytest.mark.integration, pytest.mark.live]

TIMEOUT_SECONDS = 120


def test_a_question_produces_an_answer(integration_client):
    created = integration_client.post(
        "/api/v1/research", json={"query": "What is photosynthesis?"}
    )
    assert created.status_code == 201
    job_id = created.json()["id"]

    # POST only starts the work now, so poll until the job finishes. The
    # timeout keeps a stuck pipeline from hanging the test run.
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        job = integration_client.get(f"/api/v1/research/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(2)
    else:
        pytest.fail(f"job {job_id} did not finish within {TIMEOUT_SECONDS}s")

    assert job["status"] == "completed", job["error_message"]
    assert job["answer"]
