from app.store import JobStore


def test_claim_lease_and_old_token(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    job = store.create_job("Why salt?")
    first = store.claim_next_job(now=100, lease_seconds=10)
    assert first.id == job.id
    assert store.claim_next_job(now=105, lease_seconds=10) is None
    second = store.claim_next_job(now=111, lease_seconds=10)
    assert second.id == job.id and second.claim_token != first.claim_token
    assert not store.renew_lease(job.id, first.claim_token, now=112)
    assert not store.mark_succeeded(job.id, first.claim_token, "old.mp4", now=112)
    assert not store.mark_failed(job.id, first.claim_token, "old failed", now=112)
    assert store.mark_succeeded(job.id, second.claim_token, "new.mp4", now=112)
    assert store.get_job(job.id).status == "succeeded"


def test_three_expired_attempts_fail(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    job = store.create_job("Why salt?")
    for now in [100, 111, 122]:
        assert store.claim_next_job(now=now, lease_seconds=10)
    assert store.claim_next_job(now=133, lease_seconds=10) is None
    assert store.get_job(job.id).status == "failed"
