import os
from contextlib import asynccontextmanager, nullcontext
from typing import Any, Dict, List, Literal, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from src.generator import generate_answer
from src.vector_store import get_vector_store

load_dotenv()

@asynccontextmanager
async def lifespan(_: FastAPI):
    # The SQLite queue recovers queued/processing work when the API starts.
    store = get_vector_store()
    try:
        yield
    finally:
        store.shutdown_ingestion_queue()


app = FastAPI(
    title="YouTube Playlist RAG API",
    description="API for indexing YouTube playlists and answering questions with timestamped transcript evidence.",
    version="0.3.0",
    lifespan=lifespan,
)

# Enable CORS for Next.js web application.
# Extend ALLOWED_ORIGINS with your production domain before deploying.
ALLOWED_ORIGINS = [
    "http://localhost:3000",   # Next.js web dev server
    "http://localhost:3001",   # docs dev server
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    os.getenv("CORS_ORIGIN", ""),  # Set CORS_ORIGIN=https://yourdomain.com in .env for prod
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in ALLOWED_ORIGINS if o],  # filter empty strings
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class IngestRequest(BaseModel):
    url: str = Field(..., description="YouTube video or playlist URL")
    collection_name: str = Field(default="yt_transcripts", description="Qdrant collection name for transcript chunks")
    videos_collection: str = Field(default="yt_videos", description="Qdrant collection name for Tier 1 video registry")
    target_words: int = Field(default=180, ge=50, le=1000, description="Target word count per chunk")
    overlap_words: int = Field(default=35, ge=0, le=200, description="Word overlap between chunks")
    force_playlist: bool = Field(default=False, description="Set True to force full playlist ingestion when URL contains list=")
    deep_ingest: bool = Field(default=False, description="Queue every playlist video for durable background indexing. Default False indexes the selected video first, then queues the remaining videos.")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query string")
    collection_name: str = Field(default="yt_transcripts", description="Qdrant collection name")
    videos_collection: str = Field(default="yt_videos", description="Qdrant collection name for Tier 1 video registry")
    limit: int = Field(default=5, ge=1, le=50, description="Maximum results to return")
    video_id: Optional[str] = Field(default=None, description="Optional filter by specific YouTube video ID")
    playlist_id: Optional[str] = Field(default=None, description="Optional filter by specific YouTube playlist ID")
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Minimum cosine similarity score")
    enable_jit: bool = Field(default=True, description="Enable JIT on-demand transcript fetching")


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1200)


class ChatRequest(BaseModel):
    question: str = Field(..., description="User question to answer using indexed video transcripts")
    collection_name: str = Field(default="yt_transcripts", description="Qdrant collection name")
    videos_collection: str = Field(default="yt_videos", description="Qdrant collection name for Tier 1 video registry")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")
    min_score: float = Field(default=0.50, ge=0.0, le=1.0, description="Minimum similarity score cutoff")
    video_id: Optional[str] = Field(default=None, description="Optional filter to a specific video")
    playlist_id: Optional[str] = Field(default=None, description="Optional filter to a specific playlist")
    enable_jit: bool = Field(default=True, description="Enable JIT on-demand transcript fetching")
    chat_history: List[ChatHistoryMessage] = Field(default_factory=list, max_length=8)


@app.get("/")
def root():
    return {
        "message": "YouTube Playlist RAG Assistant API is online",
        "docs": "/docs",
        "endpoints": [
            "/api/health",
            "/api/videos",
            "/api/ingest",
            "/api/ingest/status",
            "/api/ingest/jobs",
            "/api/ingest/jobs/{job_id}",
            "/api/ingest/jobs/{job_id}/retry",
            "/api/ingest/resume",
            "/api/ingest/stop",
            "/api/search",
            "/api/chat",
        ],
    }


@app.get("/api/health")
def health_check():
    try:
        store = get_vector_store()
        collections = store.client.get_collections().collections
        collection_names = [c.name for c in collections]
        llm_provider = os.getenv("LLM_PROVIDER", "auto")
        has_gemini = bool(os.getenv("GEMINI_API_KEY"))
        has_groq = bool(os.getenv("GROQ_API_KEY"))
        reranker_enabled = bool(store._reranker_model_name) and store._reranker_model_name.lower() != "none"
        reranker_status = (
            "disabled" if not reranker_enabled else
            "loaded" if store._reranker is not None else
            "unavailable" if store._reranker_attempted else
            "loads_on_first_query"
        )
        ingestion_status = store.get_background_ingest_status()
        return {
            "status": "healthy",
            "qdrant_target": store.target_url,
            "embedding_model": store.embedding_model_name,
            "vector_dimension": store.vector_dim,
            "collections": collection_names,
            "reranker": {
                "model": store._reranker_model_name or None,
                "status": reranker_status,
            },
            "llm": {
                "configured_provider": llm_provider,
                "has_gemini_key": has_gemini,
                "has_groq_key": has_groq,
            },
            "ingestion": {
                "worker_alive": ingestion_status.get("worker_alive", False),
                "is_running": ingestion_status.get("is_running", False),
                "is_paused": ingestion_status.get("is_paused", False),
                "job_id": ingestion_status.get("job_id"),
                "current_video": ingestion_status.get("current_video"),
                "completed": ingestion_status.get("completed", 0),
                "total": ingestion_status.get("total", 0),
            },
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
        }


@app.get("/api/videos")
def get_indexed_videos(collection_name: str = "yt_videos", limit: int = 1000):
    """
    List all registered video lectures in the Tier 1 registry with transcription states.
    Allows frontend to display playlist library instantly without waiting for chunking.
    """
    try:
        store = get_vector_store()
        videos = store.list_videos(collection_name=collection_name, limit=limit)
        return {
            "collection_name": collection_name,
            "count": len(videos),
            "videos": videos,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {str(e)}")


@app.post("/api/ingest")
def ingest_url(request: IngestRequest):
    """
    Hierarchical Ingestion Endpoint:
    - If playlist: Registers all video titles and metadata, indexes the selected video, and queues remaining videos durably.
      With deep_ingest=True, all videos are queued without waiting for transcript processing.
    - If single video: Registers and transcribes immediately.
    """
    try:
        store = get_vector_store()
        result = store.ingest_youtube_url(
            url=request.url,
            collection_name=request.collection_name,
            videos_collection=request.videos_collection,
            target_words=request.target_words,
            overlap_words=request.overlap_words,
            force_playlist=request.force_playlist,
            deep_ingest=request.deep_ingest,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest URL: {str(e)}")


@app.get("/api/ingest/status")
def get_background_ingest_status():
    """
    Check the current progress of background playlist ingestion.
    Returns active worker state, aggregate progress, and recent durable jobs.
    """
    try:
        store = get_vector_store()
        return store.get_background_ingest_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch ingest status: {str(e)}")


@app.get("/api/ingest/jobs")
def get_ingestion_jobs(limit: int = 20):
    """List recent durable ingestion jobs with per-video progress."""
    try:
        return {"jobs": get_vector_store().list_ingestion_jobs(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list ingestion jobs: {str(e)}")


@app.get("/api/ingest/jobs/{job_id}")
def get_ingestion_job(job_id: str):
    """Get a durable ingestion job and its per-video results."""
    try:
        job = get_vector_store().get_ingestion_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Ingestion job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch ingestion job: {str(e)}")


@app.post("/api/ingest/jobs/{job_id}/retry")
def retry_ingestion_job(job_id: str, video_id: Optional[str] = None):
    """Retry failed videos from a job, or just one failed video."""
    try:
        store = get_vector_store()
        if store.get_ingestion_job(job_id) is None:
            raise HTTPException(status_code=404, detail="Ingestion job not found")
        retried = store.retry_failed_ingestion(job_id, video_id)
        return {"retried": retried, "job": store.get_ingestion_job(job_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retry ingestion job: {str(e)}")


@app.post("/api/ingest/resume")
def resume_background_ingestion():
    """Resume paused jobs and restart pending durable work."""
    try:
        store = get_vector_store()
        resumed = store.resume_background_ingest()
        return {"resumed": resumed, "status": store.get_background_ingest_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume ingestion: {str(e)}")


@app.post("/api/ingest/stop")
def stop_background_ingestion():
    """
    Pause active ingestion after its current video completes. Jobs can be resumed later.
    """
    try:
        store = get_vector_store()
        stopped = store.stop_background_ingest(reason="manual_user_stop")
        return {"stopped": stopped, "status": store.get_background_ingest_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop ingestion: {str(e)}")


@app.post("/api/search")
def search_transcripts(request: SearchRequest):
    """
    Perform semantic vector search across ingested YouTube transcripts.
    Runs alongside background ingestion; it does not cancel the playlist job.
    Uses Two-Tier routing: if query relates to an unindexed lecture, it transcribes and chunks JIT.
    Returns matched chunks with timestamps, lead-in links, and text preview.
    """
    try:
        store = get_vector_store()
        priority = store.prioritize_interactive_retrieval() if request.enable_jit else nullcontext()
        with priority:
            hits = store.search(
                query=request.query,
                collection_name=request.collection_name,
                videos_collection=request.videos_collection,
                limit=request.limit,
                score_threshold=request.score_threshold,
                filter_video_id=request.video_id,
                filter_playlist_id=request.playlist_id,
                enable_jit=request.enable_jit,
                interrupt_background_ingest=False,
            )
        return {
            "query": request.query,
            "collection_name": request.collection_name,
            "count": len(hits),
            "results": hits,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/api/chat")
@app.post("/api/ask")
def chat_with_lectures(request: ChatRequest):
    """
    Full Grounded RAG Chat Endpoint:
    - Runs alongside background ingestion without cancelling the playlist job.
    - Hierarchical Two-Tier Routing: routes question across playlist titles and JIT fetches/chunks transcripts.
    - Retrieves relevant chunks from Qdrant.
    - Guardrail 1: Rejects off-topic questions without calling the LLM.
    - Generates grounded answers using Gemini or Groq.
    - Guardrail 2: Enforces refusal if excerpts are insufficient.
    - Guardrail 3: Filters and renumbers only cited timestamps.
    """
    try:
        store = get_vector_store()
        result = generate_answer(
            question=request.question,
            collection_name=request.collection_name,
            videos_collection=request.videos_collection,
            top_k=request.top_k,
            min_score=request.min_score,
            filter_video_id=request.video_id,
            filter_playlist_id=request.playlist_id,
            enable_jit=request.enable_jit,
            chat_history=[message.model_dump() for message in request.chat_history],
            interrupt_background_ingest=False,
        )
        return {
            "question": request.question,
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
