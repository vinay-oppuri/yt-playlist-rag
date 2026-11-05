# API development

FastAPI serves YouTube transcript ingestion, search, and grounded chat. The live service exposes its canonical endpoint schemas at `/docs`.

## Start

From this directory:

```powershell
uv sync
Copy-Item .env.example .env
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Start Qdrant from the repository root with `docker compose up -d qdrant`. Configure an LLM key in `.env` for generated answers; transcript retrieval works without a key.

## Endpoints

- `GET /api/health` reports Qdrant, embedding, reranker, and LLM configuration state.
- `GET /api/videos` lists registered playlist videos.
- `POST /api/ingest` registers a video or playlist and creates a durable indexing job.
- `GET /api/ingest/status` reports worker state and aggregate progress.
- `GET /api/ingest/jobs` and `GET /api/ingest/jobs/{job_id}` report persisted job and per-video state.
- `POST /api/ingest/jobs/{job_id}/retry?video_id=...` retries one failed video; omit `video_id` to retry all failed videos.
- `POST /api/ingest/stop` pauses queued work; `POST /api/ingest/resume` resumes it.
- `POST /api/search` returns timestamped transcript matches.
- `POST /api/chat` and `/api/ask` return a grounded answer and citations used.

Jobs and per-video attempts are stored in SQLite at `apps/api/data/ingestion_jobs.sqlite3` by default. Queued work and items interrupted during a restart recover automatically. A SQLite lease elects one sequential queue worker across API processes that share this same local database file. Interactive retrieval gets the transcript slot after the current video completes, before the worker takes another video. Cross-host SQLite sharing and distributed JIT locks are unsupported; use one API process until those are added.

Set `INGESTION_DB_PATH` to move the queue database, `INGESTION_MAX_ATTEMPTS` to change retry count, and `INGESTION_WORKER_LEASE_SECONDS` to change the worker failover window. Keep the database on persistent local storage; placing it on ephemeral storage removes restart recovery.

## Retrieval and grounding

Transcript search combines Qdrant dense retrieval, exact-token full-text candidates, video-profile ranks, reciprocal rank fusion, a local cross-encoder, and a diversity pass. Common English and Hinglish filler terms are removed from lexical/profile matching. Profile summaries and titles route retrieval but are never factual answer evidence.

The answer generator applies a transcript relevance cutoff before calling an LLM. It rejects answers that omit sentence-level citations, cite excerpt indices that were not supplied, or contain no valid transcript references. This is a structural citation check; human review is still needed to establish whether a cited excerpt supports each claim.

## Quality evaluation

From this directory, evaluate retrieval after indexing the target videos:

```powershell
uv run python eval/eval_retrieval.py --group strivers_a2z --json-out eval/results.json
```

Use `--playlist-id` for a playlist constraint and `--disable-reranker` for a rank-fusion comparison. `eval/golden.json` stores expected videos and timestamp windows. `eval/eval_answers.py` runs generated-answer review cases and may call the configured LLM; inspect its report manually.

See the repository's [project roadmap](../../PROJECT_CONTEXT_AND_ROADMAP.md) for known limitations and planned work.
