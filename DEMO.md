# API walkthrough and three generated examples

Start the API and worker as shown in [README.md](README.md), then submit any of the exact questions below. `POST /videos` returns HTTP 202 and a job ID with `status: "queued"`.

| Learner query | Committed generated video | Example job ID |
| --- | --- | --- |
| How does the pH scale work? | [pH scale MP4](demo/videos/ph-scale.mp4) | `e285f110-dfed-47f1-8725-a17af20ad064` |
| Why do atoms form covalent bonds? | [Covalent bonds MP4](demo/videos/covalent-bonds.mp4) | `74770f20-2ed1-469e-b333-afe51a948556` |
| What is the difference between ionic and covalent bonding? | [Ionic versus covalent MP4](demo/videos/ionic-vs-covalent.mp4) | `79fb8f91-2906-487f-bd43-93eef2459cac` |

**Watch the submitted videos:** click any MP4 link in the table. These files are committed to the public repository, so reviewers can watch or download them without starting the backend. [demo/videos/manifest.json](demo/videos/manifest.json) records each exact learner query, job ID, duration, and SHA-256. The sample job IDs refer to the original generation run; a fresh local installation has a different database and new job IDs.

```bash
curl -i -X POST http://127.0.0.1:8000/videos -H 'Content-Type: application/json' \
  -d '{"concept":"How does the pH scale work?"}'
curl -i -X POST http://127.0.0.1:8000/videos -H 'Content-Type: application/json' \
  -d '{"concept":"Why do atoms form covalent bonds?"}'
curl -i -X POST http://127.0.0.1:8000/videos -H 'Content-Type: application/json' \
  -d '{"concept":"What is the difference between ionic and covalent bonding?"}'

curl http://127.0.0.1:8000/videos
JOB_ID="replace-with-id-from-POST"
curl "http://127.0.0.1:8000/videos/$JOB_ID"
curl -L "http://127.0.0.1:8000/videos/$JOB_ID/file" -o explanation.mp4
```

Poll the detail URL until `succeeded` or `failed`. The `video_url` field is populated only for `succeeded`; prefix it with `http://127.0.0.1:8000` to open the generated MP4 in a browser. `GET /videos` shows all requests, including jobs still queued or processing. FastAPI's interactive API docs are at `http://127.0.0.1:8000/docs`.

**Postman:** send `POST http://127.0.0.1:8000/videos` with header `Content-Type: application/json` and a raw JSON body such as `{"concept":"How does the pH scale work?"}`. Copy the returned `id`; send `GET http://127.0.0.1:8000/videos/<that-id>` until its status is `succeeded`. Then send `GET http://127.0.0.1:8000/videos/<that-id>/file` and save the binary response as an `.mp4` file. Postman must run on the same machine as the localhost API. For a remote reviewer, use the committed MP4 links above.
