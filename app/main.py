from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .config import get_settings
from .jobs import VideoJob, VideoRequest
from .store import JobStore


def create_app(store: JobStore | None = None, artifact_root: Path | None = None) -> FastAPI:
    settings = get_settings()
    store = store or JobStore(settings.data_root / "jobs.sqlite3")
    artifact_root = artifact_root or settings.data_root / "videos"
    app = FastAPI(title="Chemistry Explainer Video API")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/videos", response_model=VideoJob, status_code=202)
    def create_video(body: VideoRequest):
        return store.create_job(body.concept)

    @app.get("/videos", response_model=list[VideoJob])
    def list_videos():
        return store.list_jobs()

    @app.get("/videos/{job_id}", response_model=VideoJob)
    def get_video(job_id: UUID):
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(404, "Video job not found")
        return job

    @app.get("/videos/{job_id}/file")
    def get_video_file(job_id: UUID):
        filename = store.get_filename(job_id)
        if filename is None:
            raise HTTPException(404, "Video is not ready")
        # The database only receives a server-generated token basename.
        if Path(filename).name != filename or not filename.endswith(".mp4"):
            raise HTTPException(404, "Video unavailable")
        path = artifact_root / str(job_id) / filename
        if not path.is_file():
            raise HTTPException(404, "Video unavailable")
        return FileResponse(path, media_type="video/mp4", filename=f"{job_id}.mp4")

    return app


app = create_app()
