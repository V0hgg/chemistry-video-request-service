import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.main import create_app
from app.generator import GenerationError
from app.store import JobStore
from app.worker import run_once


def test_twenty_simultaneous_submissions(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    app = create_app(store, tmp_path / "videos")

    async def submit():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            responses = await asyncio.gather(*[
                client.post("/videos", json={"concept": f"Chemistry question {i}"}) for i in range(20)])
            return responses, (await client.get("/videos")).json()

    responses, jobs = asyncio.run(submit())
    assert all(r.status_code == 202 for r in responses)
    assert len({r.json()["id"] for r in responses}) == 20
    assert len(jobs) == 20


def test_two_jobs_overlap_without_duplicate_claims(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    jobs = [store.create_job(f"Question {i}") for i in range(2)]
    barrier = threading.Barrier(2, timeout=10)
    claimed = []
    lock = threading.Lock()

    def generate(concept):
        with lock:
            claimed.append(concept)
        barrier.wait()
        return concept

    def render(claim, story):
        path = tmp_path / f"{claim.claim_token}.mp4"
        path.write_bytes(b"fake")
        return path

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_once, store, generate, render) for _ in range(2)]
        assert all(f.result(timeout=15) for f in futures)
    assert len(set(claimed)) == 2
    assert all(store.get_job(j.id).status == "succeeded" for j in jobs)


def test_worker_failure_has_no_video_url(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    job = store.create_job("Why do atoms bond?")

    def fail(_):
        raise GenerationError("Model endpoint returned HTTP 503")

    assert run_once(store, fail, lambda claim, story: None)
    result = store.get_job(job.id)
    assert result.status == "failed"
    assert result.video_url is None
    assert "503" in result.error
