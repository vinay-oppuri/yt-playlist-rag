# YT-RAG

Ask questions about YouTube videos and playlists, get transcript-grounded answers, and jump directly to the cited moments.

YT-RAG combines timestamp-preserving transcript chunking, Qdrant retrieval, local reranking, and a Next.js study workspace. Transcripts are the factual source for answers. Video titles and transcript-derived profiles help route a question, but are not answer evidence.

## Features

- Register playlists quickly from YouTube metadata and explore videos in the study workspace.
- Index transcripts on demand and continue background playlist indexing while searching or chatting.
- Search with dense vectors, exact-token candidates, reciprocal rank fusion, video profiles, cross-encoder reranking, and result diversification.
- Ask questions in English or Hinglish; lexical routing removes common filler words before matching.
- Receive timestamp citations that seek the embedded player.
- Refuse answers without sufficient transcript evidence or sentence-level citations.
- Review retrieval and generated-answer quality using labeled evaluation cases.

## Requirements

- Node.js 24 or newer and npm 11 or newer for the web monorepo.
- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) for the API.
- Docker for the included Qdrant service.
- A Gemini or Groq API key to generate answers. Transcript search works without an LLM key.

## Run locally

Start Qdrant from the repository root:

```powershell
docker compose up -d qdrant
```

Install API dependencies and start FastAPI:

```powershell
cd apps/api
uv sync
Copy-Item .env.example .env
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Set `GEMINI_API_KEY` or `GROQ_API_KEY` in `apps/api/.env` to enable generated answers. Embedding and reranking models download locally when first used.

In a second terminal, start the web app from the repository root:

```powershell
npm install
npm run dev:web
```

Open `http://localhost:3000`. FastAPI docs are at `http://127.0.0.1:8000/docs`; Qdrant's dashboard is at `http://localhost:6333/dashboard`.

## How a question is answered

1. The API applies the selected video or playlist filter and retrieves transcript candidates using dense and lexical search.
2. Video profiles contribute routing rank only; transcript chunks remain the sole factual source.
3. Reciprocal rank fusion, a local cross-encoder, and diversity selection order the candidates.
4. The generator refuses when no chunk passes the relevance cutoff, asks the configured LLM to answer only from excerpts, and requires valid citations on every sentence or list item.
5. The UI shows the cited video and timestamp. Clicking a citation seeks the in-page player.

Playlist indexing is stored as a SQLite job with per-video progress, errors, and retries. Pending work resumes when the API starts again. The worker is sequential and local to one API process; multi-replica queue coordination and priority scheduling for JIT work remain planned.

## Evaluation

The retrieval golden set lives in `apps/api/eval/golden.json`. It includes English and Hinglish queries with expected video and timestamp labels. Run it from `apps/api` after the corresponding videos have transcript vectors in Qdrant:

```powershell
uv run python eval/eval_retrieval.py --group strivers_a2z --json-out eval/results.json
```

Add `--playlist-id YOUR_PLAYLIST_ID` to constrain playlist retrieval. Use `--disable-reranker` to compare rank fusion without the cross-encoder. Reports include timestamp Hit@K, video Hit@K, MRR, and metrics by query language.

Generated-answer review cases are in `apps/api/eval/golden_answers.json`. The evaluator can call the configured LLM:

```powershell
uv run python eval/eval_answers.py --group campusx_fastapi --json-out eval/answer_report.json
```

Inspect generated answers and cited transcript excerpts manually. A citation check confirms the answer points to retrieved evidence; it does not prove that every claim is entailed by that evidence.

## Configuration

Copy `apps/api/.env.example` to `apps/api/.env` and configure:

| Variable | Purpose |
| --- | --- |
| `LLM_PROVIDER` | Select `gemini` or `groq` |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Gemini credentials and model |
| `GROQ_API_KEY`, `GROQ_MODEL` | Groq credentials and model |
| `QDRANT_URL` | Qdrant endpoint, default `http://localhost:6333` |
| `RERANKER_MODEL` | Local cross-encoder; set `none` to disable |
| `MIN_SIMILARITY_SCORE` | Transcript relevance cutoff used by grounded chat |
| `INGESTION_DB_PATH` | SQLite file for durable playlist jobs, relative to `apps/api` by default |
| `INGESTION_MAX_ATTEMPTS` | Maximum attempts per video before marking it failed; default `3` |
| `CORS_ORIGIN` | Additional allowed web origin |

See [PROJECT_CONTEXT_AND_ROADMAP.md](PROJECT_CONTEXT_AND_ROADMAP.md) for the current architecture, quality rules, and next phases.
