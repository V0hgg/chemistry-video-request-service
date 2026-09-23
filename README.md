# Chemistry explainer video backend

A FastAPI proof of concept that accepts an open-ended chemistry question, queues a durable video job, asks the configured `gpt-5.6-sol` route for a checked explanation and animation plan, and renders a narrated 3D MP4 on this Mac.

## Requirements

- macOS with Blender 5.2 or newer, `ffmpeg`, and `ffprobe`. The default Blender executable is `/Applications/Blender.app/Contents/MacOS/Blender`.
- Python 3.11–3.14.
- An OpenAI-compatible Chat Completions endpoint and API key with access to `gpt-5.6-sol`. This workspace's verified route is `cx/gpt-5.6-sol`.
- The local Kokoro ONNX model and voices file. Media generation uses the **Heart** US English voice. The model files are about 337 MB together and are downloaded once.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]' -c constraints.txt
.venv/bin/python scripts/download_voice_model.py
cp .env.example .env
```

Edit the workspace-root `.env`. Set `OPENAI_BASE_URL` to your API root, usually ending in `/v1`, and set `OPENAI_API_KEY` to your key. Keep `OPENAI_MODEL=cx/gpt-5.6-sol` for the verified gateway or use the exact model ID listed by another compatible endpoint. `OPENAI_REASONING_EFFORT=max` is required. The worker fails fast if Blender or the voice assets are missing. `.env` is ignored and must remain private. The downloaded model files are ignored by Git and excluded from the source archive.

Run the API and worker in separate terminals:

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
.venv/bin/python -m app.worker
```

The worker runs two jobs concurrently by default. Set `VIDEO_WORKER_CONCURRENCY` from 1 to 4 to change this. Blender renders every scene as a moving 3D animation; local Kokoro produces narration; FFmpeg combines the animations and audio. Rendering can take several minutes per video. The API remains responsive and records each job's status in SQLite.

## API

```bash
curl -X POST http://127.0.0.1:8000/videos \
  -H 'Content-Type: application/json' \
  -d '{"concept":"How does the pH scale work?"}'

curl http://127.0.0.1:8000/videos
JOB_ID="replace-with-id-from-POST"
curl "http://127.0.0.1:8000/videos/$JOB_ID"
curl -L "http://127.0.0.1:8000/videos/$JOB_ID/file" -o explanation.mp4
```

`POST /videos` responds `202` with a `queued` job. Poll the detail endpoint until `succeeded` or `failed`. A successful job has `video_url: /videos/<job-id>/file`, which streams an MP4. `GET /health` reports API health. The list is global and has no user accounts, so run this POC on localhost.

To watch immediately without running the backend, open one of the three committed MP4s linked in [the demo walkthrough](DEMO.md). That page also explains how to save a newly generated MP4 from Postman. A `127.0.0.1` API link works only on the machine running this service.

Job records persist in `data/jobs.sqlite3`, completed videos in `data/videos/`, and temporary render files under `work/`. Workers use atomic claims, renewable leases, and token-specific artifact paths so an interrupted attempt can be reclaimed. All model/media failures leave the job in `failed` without a served partial file.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Tests cover API validation, persistence, twenty simultaneous submissions, overlapping workers, lease recovery, provider failure, motion planning, and failed media publication. See [the architecture note](ARCHITECTURE.md) for component boundaries and [the demo walkthrough](DEMO.md) for all three requested concepts and playable example videos.
