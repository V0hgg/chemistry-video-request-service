# API walkthrough and three generated examples

Start the API and worker as shown in [README.md](README.md), then submit any of the exact questions below. `POST /videos` returns HTTP 202 and a job ID with `status: "queued"`.

| Learner query | Committed generated video | Example job ID |
| --- | --- | --- |
| How does the pH scale work? | [pH scale MP4](demo/videos/ph-scale.mp4) | `e285f110-dfed-47f1-8725-a17af20ad064` |
| Why do atoms form covalent bonds? | [Covalent bonds MP4](demo/videos/covalent-bonds.mp4) | `74770f20-2ed1-469e-b333-afe51a948556` |
| What is the difference between ionic and covalent bonding? | [Ionic versus covalent MP4](demo/videos/ionic-vs-covalent.mp4) | `79fb8f91-2906-487f-bd43-93eef2459cac` |

The committed videos were generated from those exact learner queries. [demo/videos/manifest.json](demo/videos/manifest.json) records the query, job ID, duration, and SHA-256 for each file. Sample job IDs refer to the generation run and will differ when a reviewer runs the API locally.

```bash
curl -i -X POST http://127.0.0.1:8000/videos -H 'Content-Type: application/json' \
  -d '{"concept":"How does the pH scale work?"}'
curl -i -X POST http://127.0.0.1:8000/videos -H 'Content-Type: application/json' \
  -d '{"concept":"Why do atoms form covalent bonds?"}'
curl -i -X POST http://127.0.0.1:8000/videos -H 'Content-Type: application/json' \
  -d '{"concept":"What is the difference between ionic and covalent bonding?"}'

curl http://127.0.0.1:8000/videos
curl http://127.0.0.1:8000/videos/<job-id>
curl -o explanation.mp4 http://127.0.0.1:8000/videos/<job-id>/file
```

Poll the detail URL until `succeeded` or `failed`. The `video_url` field is populated only for `succeeded`; prefix it with `http://127.0.0.1:8000` to play or download the generated MP4. `GET /videos` shows all requests, including jobs still queued or processing. FastAPI's interactive API docs are at `http://127.0.0.1:8000/docs`.
