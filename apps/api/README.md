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
- `GET /api/ready` is a readiness probe and returns HTTP 503 when Qdrant is unavailable; `/api/health` remains a diagnostic/liveness endpoint.
- `GET /api/videos` lists registered playlist videos.
- `POST /api/ingest` registers a video or playlist and creates a durable indexing job.
- `GET /api/ingest/status` reports worker state and aggregate progress.
- `GET /api/ingest/jobs` and `GET /api/ingest/jobs/{job_id}` report persisted job and per-video state.
- `POST /api/ingest/jobs/{job_id}/retry?video_id=...` retries one failed video; omit `video_id` to retry all failed videos.
- `POST /api/ingest/stop` pauses queued work; `POST /api/ingest/resume` resumes it.
- `POST /api/search` returns timestamped transcript matches.
- `POST /api/chat` and `/api/ask` return a grounded answer and citations used.
- `POST /api/v1/llm/generate` generates a text completion from the configured LLM provider.
- `GET /api/v1/llm/health` reports configured LLM provider and model.
- `GET /api/v1/llm/connectivity` probes the upstream LLM for reachability.

Jobs and per-video attempts are stored in SQLite at `apps/api/data/ingestion_jobs.sqlite3` by default. Queued work and items interrupted during a restart recover automatically. A SQLite lease elects one sequential queue worker across API processes that share this same local database file. Interactive retrieval gets the transcript slot after the current video completes, before the worker takes another video. Cross-host SQLite sharing and distributed JIT locks are unsupported; use one API process until those are added.

Set `INGESTION_DB_PATH` to move the queue database, `INGESTION_MAX_ATTEMPTS` to change retry count, and `INGESTION_WORKER_LEASE_SECONDS` to change the worker failover window. Keep the database on persistent local storage; placing it on ephemeral storage removes restart recovery.

## Retrieval and grounding

Transcript search combines Qdrant dense retrieval, exact-token full-text candidates, video-profile ranks, reciprocal rank fusion, a local cross-encoder, and a diversity pass. Common English and Hinglish filler terms are removed from lexical/profile matching. Profile summaries and titles route retrieval but are never factual answer evidence.

The answer cutoff now uses transcript-body overlap and dense similarity. Exact transcript matches can help short concept queries pass the cutoff when dense similarity clears a minimum floor; a title or profile match alone cannot qualify an answer. The retrieval evaluator uses the same cutoff logic as chat.

The answer generator applies a transcript relevance cutoff before calling an LLM. It rejects answers that omit sentence-level citations, cite excerpt indices that were not supplied, or contain no valid transcript references. This is a structural citation check; human review is still needed to establish whether a cited excerpt supports each claim.

## Quality evaluation

From this directory, evaluate retrieval after indexing the target videos:

```powershell
uv run python eval/eval_retrieval.py --group strivers_a2z --json-out eval/results.json
```

Use `--playlist-id` for a playlist constraint and `--disable-reranker` for a rank-fusion comparison. `eval/golden.json` stores expected videos and timestamp windows. `eval/eval_answers.py` runs generated-answer review cases and may call the configured LLM; inspect its report manually.

See the repository's [project roadmap](../../PROJECT_CONTEXT_AND_ROADMAP.md) for known limitations and planned work.

## API boundaries and diagnostics

- Ingestion accepts HTTPS URLs on `youtube.com` and `youtu.be`, or an 11-character video ID. Other hosts, URL credentials, and nonstandard ports are rejected before invoking `yt-dlp`.
- Collection names, video IDs, playlist IDs, question lengths, chat history size, and list limits are validated at the request boundary.
- Each response includes an `X-Request-ID`. API logs include that ID, route, status, and duration, but do not log question or transcript content.
- Internal exception details are written to server logs and are not returned in HTTP 500 responses.
- The API does not provide user authentication or per-user data isolation. Put it behind an authenticated gateway before exposing it to untrusted users; CORS is a browser policy, not access control.

## LLM provider abstraction

The `src/llm/` package provides a unified `BaseLLM` interface that lets application code call any supported LLM provider without knowing which one is active. Switching providers requires only environment variable changes — no code changes.

### Supported providers

| Provider | SDK | Notes |
|----------|-----|-------|
| `ollama` | `openai` (OpenAI-compatible API) | Local models via Ollama |
| `openai` | `openai` | OpenAI API |
| `gemini` | `google-genai` | Google Gemini API |

### Running with Ollama (local)

```powershell
# Make sure Ollama is running and the model is pulled
ollama list
ollama run qwen3:8b

# Configure .env
# LLM_PROVIDER=ollama
# LLM_MODEL=qwen3:8b

uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Running with OpenAI

Set in `.env`:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=sk-...
```

### Running with Gemini

Set in `.env`:

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=AIza...
```

### Usage in application code

```python
from src.llm import get_llm

llm = get_llm()
response = await llm.generate(
    prompt="Explain this security event",
    system_prompt="You are a cybersecurity analyst.",
)
```

Or as a FastAPI dependency:

```python
from fastapi import Depends
from src.llm import BaseLLM, get_llm

@app.post("/my-endpoint")
async def my_endpoint(llm: BaseLLM = Depends(get_llm)):
    return await llm.generate(prompt="Hello")
```

### Architecture

Ollama and OpenAI share a single `OpenAICompatibleLLM` implementation — only the `base_url` and `api_key` differ. Gemini uses a separate provider class backed by the `google-genai` SDK. All providers implement the same `BaseLLM` abstract interface.
