from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.store import JobStore


def test_submission_listing_and_validation(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    client = TestClient(create_app(store, tmp_path / "videos"))
    assert client.get("/health").json() == {"status": "ok"}
    response = client.post("/videos", json={"concept": "  How does pH work?  "})
    assert response.status_code == 202
    job = response.json()
    assert job["concept"] == "How does pH work?"
    assert job["status"] == "queued" and job["video_url"] is None
    assert client.get("/videos").json()[0]["id"] == job["id"]
    assert client.get(f'/videos/{job["id"]}').json()["id"] == job["id"]
    assert client.get(f'/videos/{job["id"]}/file').status_code == 404
    assert client.post("/videos", json={"concept": "  "}).status_code == 422
    assert client.post("/videos", json={"concept": "x" * 301}).status_code == 422
    assert client.post("/videos", json={"concept": " x " + " " * 301}).json()["concept"] == "x"
    assert client.get(f"/videos/{uuid4()}").status_code == 404


def test_jobs_survive_store_reopen(tmp_path):
    path = tmp_path / "jobs.db"
    job = JobStore(path).create_job("Why do atoms bond?")
    assert JobStore(path).get_job(job.id).concept == job.concept
