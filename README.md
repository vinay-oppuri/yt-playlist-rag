# YouTube Playlist RAG Assistant

> An end-to-end Retrieval-Augmented Generation (RAG) system for YouTube playlists and technical video lectures. Ask questions in English or Hinglish, receive answers strictly grounded in transcript evidence, and jump directly to exact timestamped video moments.

---

## Architecture Overview

This project is organized as a Turborepo monorepo:

```text
yt-playlist-rag/
├── apps/
│   ├── api/          # FastAPI backend (Python 3.12, uv, Qdrant, FastEmbed, Google Gemini)
│   ├── web/          # Interactive study workspace (Next.js 16, React, YouTube IFrame player)
│   └── docs/         # Documentation & landing page (Next.js 16)
└── packages/         # Shared configs (ESLint, TypeScript, Tailwind/UI)
```

### Core Technologies
- **Backend**: FastAPI, `uv`, `fastembed` (`BAAI/bge-small-en-v1.5`), `google-genai` (`gemini-2.5-flash`), `yt-dlp`.
- **Vector Database**: Qdrant (`http://localhost:6333`) containerized with persistent storage.
- **Reranker**: Local cross-encoder (`Xenova/ms-marco-MiniLM-L-6-v2`).
- **Frontend**: Next.js, React, Tailwind CSS, Turborepo.

---

## Prerequisites

Before starting, ensure you have the following installed:

1. **Docker Desktop** (for Qdrant vector database)
2. **Python 3.12+** and [**uv**](https://docs.astral.sh/uv/) (for the FastAPI backend)
3. **Node.js 20+** and **npm** / **pnpm** (for the web and docs applications)
4. A **Google Gemini API Key** (get one at [Google AI Studio](https://aistudio.google.com/apikey))

---

## Step-by-Step Setup Guide

### 1. Start Qdrant Vector Database

All Docker configuration is located inside `apps/api/`:

```powershell
cd apps/api
docker compose up -d qdrant
```

- **Qdrant REST API**: `http://localhost:6333`
- **Qdrant Web Dashboard**: `http://localhost:6333/dashboard`
- Persistent vectors and collections are stored in `apps/api/qdrant_data/`.

---

### 2. Configure & Start the FastAPI Backend

From the `apps/api` directory:

1. Copy the example environment file:
   ```powershell
   Copy-Item .env.example .env
   ```

2. Open `.env` and set your Google Gemini API key:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   QDRANT_URL=http://localhost:6333
   ```

3. Install dependencies and start the API server using `uv`:
   ```powershell
   uv sync
   uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```

- **API Base**: `http://127.0.0.1:8000`
- **Interactive OpenAPI Docs**: `http://127.0.0.1:8000/docs`
- **Health Check**: `http://127.0.0.1:8000/api/health`

---

### 3. Start the Next.js Web Application

In a separate terminal, from the root of the repository:

```powershell
# Install Node dependencies across the monorepo
npm install

# Start the web study workspace
npm run dev:web
```

Open **`http://localhost:3000`** in your browser.

---

### 4. (Optional) Start Documentation App

To view the documentation and landing site:

```powershell
npm run dev:docs
```

Open **`http://localhost:3001`** in your browser.

---

## Configuration Reference (`apps/api/.env`)

| Variable | Default Value | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(Required)* | Your Google Gemini API key from AI Studio |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use for grounded answer generation |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector database URL |
| `QDRANT_COLLECTION` | `yt_transcripts` | Collection name for transcript chunk vectors |
| `RERANKER_MODEL` | `Xenova/ms-marco-MiniLM-L-6-v2` | Local cross-encoder model (or `none` to disable) |
| `MIN_SIMILARITY_SCORE` | `0.50` | Relevance cutoff score; queries below this refuse to hallucinate |
| `INGESTION_DB_PATH` | `data/ingestion_jobs.sqlite3` | SQLite database for tracking playlist indexing jobs |
| `INGESTION_MAX_ATTEMPTS`| `3` | Max retries per video during background playlist ingestion |
| `CORS_ORIGIN` | `""` | Production frontend domain (leave empty for localhost) |

---

## Key RAG Features & Guardrails

1. **Two-Tier Search Routing**:
   - Matches questions against video metadata (`yt_videos`) to select the best lecture.
   - Retrieves semantic chunks from transcripts (`yt_transcripts`) with JIT fetching for unindexed videos.

2. **Strict Hallucination Defense (3 Guardrails)**:
   - **Guard 1 (Cosine Cutoff)**: If no chunks meet `MIN_SIMILARITY_SCORE`, the system refuses immediately without calling the LLM.
   - **Guard 2 (Strict Prompting)**: Gemini is instructed to use *only* facts present in the excerpts, returning an exact refusal if insufficient.
   - **Guard 3 (Citation Filtering & Dynamic Renumbering)**: Only excerpts cited by the model are returned to the user, sequentially numbered `[1]`, `[2]`.

3. **In-Page Player Seeking (`-5s` Lead-In)**:
   - Citations include calculated time offsets subtracting 5 seconds from the chunk start, providing natural conversational context when the video starts playing.

---

## Quality Evaluation

Accuracy benchmarks can be run from `apps/api`:

```powershell
cd apps/api

# Evaluate retrieval accuracy (Hit@K, MRR, Cutoff Accuracy):
uv run python eval/eval_retrieval.py --group strivers_a2z --json-out eval/results.json

# Evaluate generated answers with Gemini:
uv run python eval/eval_answers.py --group campusx_fastapi --json-out eval/answer_report.json
```
