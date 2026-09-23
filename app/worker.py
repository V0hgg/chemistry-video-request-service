import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import httpx

from .config import Settings, get_settings
from .generator import GenerationError, generate_storyboard
from .renderer import RenderError, render_video
from .store import JobStore


LOG = logging.getLogger(__name__)
LEASE_SECONDS = 90
HEARTBEAT_SECONDS = 15


def run_once(store: JobStore, generator: Callable, renderer: Callable) -> bool:
    claim = store.claim_next_job(lease_seconds=LEASE_SECONDS)
    if claim is None:
        return False
    done = threading.Event()
    lost = threading.Event()

    def heartbeat():
        while not done.wait(HEARTBEAT_SECONDS):
            if not store.renew_lease(claim.id, claim.claim_token, lease_seconds=LEASE_SECONDS):
                lost.set()
                return

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    artifact: Path | None = None
    try:
        storyboard = generator(claim.concept)
        if lost.is_set():
            return True
        artifact = renderer(claim, storyboard)
        if lost.is_set() or not store.mark_succeeded(claim.id, claim.claim_token, artifact.name):
            artifact.unlink(missing_ok=True)
        else:
            LOG.info("Completed video job %s", claim.id)
    except (GenerationError, RenderError) as exc:
        if artifact is not None:
            artifact.unlink(missing_ok=True)
        store.mark_failed(claim.id, claim.claim_token, str(exc))
        LOG.warning("Video job %s failed: %s", claim.id, exc)
    except Exception:
        if artifact is not None:
            artifact.unlink(missing_ok=True)
        store.mark_failed(claim.id, claim.claim_token, "Video generation failed")
        LOG.exception("Video job %s failed unexpectedly", claim.id)
    finally:
        done.set()
        thread.join(timeout=1)
    return True


def run_pool(concurrency: int | None = None, settings: Settings | None = None,
             stop: threading.Event | None = None) -> None:
    settings = settings or get_settings()
    settings.validate_worker()
    settings.validate_media()
    concurrency = concurrency or settings.worker_concurrency
    if not 1 <= concurrency <= 4:
        raise ValueError("Worker concurrency must be between 1 and 4")
    store = JobStore(settings.data_root / "jobs.sqlite3")
    stop = stop or threading.Event()

    def loop(index: int):
        with httpx.Client() as client:
            while not stop.is_set():
                generator = lambda concept: generate_storyboard(concept, client, settings)
                renderer = lambda claim, story: render_video(
                    str(claim.id), claim.claim_token, story, settings.work_root,
                    settings.data_root / "videos", settings)
                if not run_once(store, generator, renderer):
                    stop.wait(0.5)

    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="video-worker") as pool:
        futures = [pool.submit(loop, i) for i in range(concurrency)]
        try:
            while not stop.wait(0.5):
                for future in futures:
                    if future.done():
                        future.result()
        except KeyboardInterrupt:
            stop.set()
        finally:
            stop.set()
            for future in futures:
                future.result()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    run_pool()
