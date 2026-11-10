# YouTube Playlist RAG API (`apps/api`)

FastAPI backend serving YouTube transcript ingestion, vector retrieval, and grounded Q&A with Google Gemini.

The live service exposes its OpenAPI interactive docs at `http://127.0.0.1:8000/docs`.

---

## 1. Quick Start

### Step 1: Start Qdrant (Docker)

From this directory:

```powershell
docker compose up -d qdrant
```

Qdrant runs with persistent storage mounted to `./qdrant_data`.
- **REST API**: `http://localhost:6333`
- **Dashboard**: `http://localhost:6333/dashboard`

### Step 2: Configure Environment

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set your Google Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

*(Transcript retrieval and search work without an API key; Gemini is only required for generating synthesized answers).*

### Step 3: Install Dependencies & Run

Using [uv](https://docs.astral.sh/uv/):

```powershell
uv sync
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

---

## 2. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API status and directory of available endpoints |
| `GET` | `/api/health` | Diagnostic status (Qdrant, embedding model, reranker, and LLM) |
| `GET` | `/api/ready` | Readiness probe (returns HTTP 503 if Qdrant is unavailable) |
| `GET` | `/api/videos` | List all registered video lectures in the Tier 1 registry |
| `POST` | `/api/ingest` | Register and ingest a YouTube video or playlist URL into Qdrant |
| `GET` | `/api/ingest/status` | Current background queue progress and active worker state |
| `GET` | `/api/ingest/jobs` | List recent durable playlist ingestion jobs |
| `GET` | `/api/ingest/jobs/{id}` | Inspect a specific job and per-video status |
| `POST` | `/api/ingest/jobs/{id}/retry` | Retry failed videos from an ingestion job |
| `POST` | `/api/ingest/stop` | Pause active playlist queue worker |
| `POST` | `/api/ingest/resume` | Resume paused background playlist ingestion |
| `POST` | `/api/search` | Semantic vector search across transcript chunks with timestamps |
| `POST` | `/api/chat` (or `/api/ask`) | Grounded RAG Q&A with Gemini and sentence-level timestamp citations |

---

## 3. Retrieval & Grounding Architecture

1. **Two-Tier Indexing**:
   - `yt_videos`: Fast catalog registry containing video titles and metadata for playlist routing.
   - `yt_transcripts`: Dense vector chunks with exact timestamp windows (`start`, `duration`, `link_sec`).
   - `yt_video_profiles`: Extractive video summaries for discovery and initial routing.
2. **Dense + Lexical Retrieval**:
   - Embeddings: `BAAI/bge-small-en-v1.5` (FastEmbed).
   - Local Cross-Encoder Reranker: `Xenova/ms-marco-MiniLM-L-6-v2`.
   - Hinglish and English support with conversational filler filtering.
3. **Strict Grounding Guardrails**:
   - **Guard 1 (Cutoff Guard)**: Queries with similarity below `MIN_SIMILARITY_SCORE` refuse immediately without calling Gemini, saving latency and cost.
   - **Guard 2 (Strict Refusal)**: The model is prompted to answer strictly from transcript excerpts and output an exact refusal string if context is insufficient.
   - **Guard 3 (Citation Validation)**: The response must cite valid transcript excerpts. Citations are filtered and sequentially renumbered.

---

## 4. Evaluation

Run accuracy evaluation benchmarks from this directory:

```powershell
# Evaluate retrieval quality against golden test cases:
uv run python eval/eval_retrieval.py --group strivers_a2z --json-out eval/results.json

# Evaluate answer generation:
uv run python eval/eval_answers.py --group campusx_fastapi --json-out eval/answer_report.json
```

---

## 5. Docker Deployment

To run both Qdrant and the API containerized:

```powershell
docker compose --profile full up -d
```
