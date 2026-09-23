# Architecture note

## Job lifecycle

`POST /videos` validates the learner's chemistry question, inserts a `queued` row in SQLite, and returns HTTP 202 immediately. A separate worker process atomically claims the oldest available job and marks it `processing`. The worker creates a query-specific explanation and animation plan, renders narration and 3D scenes, verifies the MP4, and marks the row `succeeded`. `GET /videos` lists jobs; `GET /videos/{id}` exposes status and, on success, `video_url`; `GET /videos/{id}/file` serves the finished file. A generation or rendering error marks the job `failed` with a short safe error message.

The API never waits for rendering. Two worker threads run by default, configurable from one to four. SQLite WAL and an atomic claim transaction allow concurrent submissions and workers. Each claim has a 90-second renewable lease and a unique token. An interrupted worker's job can be reclaimed up to three attempts; the token prevents a stale attempt from publishing a result for the new owner.

## Persistence and artifacts

`app/store.py` owns job state in `data/jobs.sqlite3`. It stores the question, status, timestamps, error, attempt count, lease, and only the basename of a published file. `app/renderer.py` owns temporary media under `work/<job-id>/<claim-token>/` and final MP4s under `data/videos/<job-id>/<claim-token>.mp4`. It verifies H.264 video, AAC audio, and duration before atomic publication. `app/main.py` serves a file only when its job is `succeeded` and the stored basename resolves inside that job's artifact directory. The database, downloaded voice model, render intermediates, and API credentials are intentionally outside the Git submission.

## AI and video generation

`app/generator.py` calls an OpenAI-compatible Chat Completions endpoint using the configured `cx/gpt-5.6-sol` route and `max` reasoning effort. It validates the storyboard, repairs malformed responses where possible, and makes a separate relevance and obvious-error review. A constrained motion plan selects from supported 3D demonstrations; a local heuristic is the fallback for motion selection. This boundary accepts arbitrary chemistry questions, though accuracy still depends on the model and should be reviewed for high-stakes teaching.

`app/speech.py` synthesizes local Kokoro ONNX narration using the Heart US English voice. `app/blender_scene.py` renders moving 3D models; `app/renderer.py` adds concise labels and uses FFmpeg to combine scenes with normalized audio. Blender and the local voice model have compute and download costs, but no per-video media API charge. The model gateway may bill for input and output tokens; its actual price depends on the endpoint. As an illustrative **direct OpenAI** calculation only, 2,500 input tokens and 5,000 output tokens at the [published GPT-5.6 Sol rates](https://developers.openai.com/api/docs/models/gpt-5.6-sol) would be about $0.11, excluding local compute, retries, and any gateway markup. This is not a measured cost for these samples.

## POC limits

This is a localhost POC: no authentication, tenant isolation, queue broker, object storage, or cleanup policy. It uses one host's SQLite and filesystem. For a shared deployment, add user ownership, access control, object storage, retention, and a durable distributed worker queue.
