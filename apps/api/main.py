import logging
import os
import re
import time
from urllib.parse import parse_qs, urlsplit
from contextlib import asynccontextmanager, nullcontext
from typing import Any, Dict, List, Literal, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from uuid import uuid4
import uvicorn

from src.generator import generate_answer
from src.vector_store import get_vector_store

load_dotenv()
logger = logging.getLogger("yt_rag.api")


def _validate_collection_name(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("Collection names may contain only letters, numbers, underscores, and hyphens")
    return value


def _validate_video_id(value: Optional[str]) -> Optional[str]:
    if value is not None and not re.fullmatch(r"[A-Za-z0-9_-]{11}", value.strip()):
        raise ValueError("video_id must be an 11-character YouTube video ID")
    return value.strip() if value is not None else None


def _validate_youtube_url(value: str) -> str:
    value = value.strip()
    # Accept a raw YouTube video ID as a convenience, otherwise require HTTPS
    # and a known YouTube host so yt-dlp cannot be used as an arbitrary URL fetcher.
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return f"https://www.youtube.com/watch?v={value}"
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as exc:
        raise ValueError("Enter a valid YouTube URL") from exc
    allowed = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
    if parsed.scheme != "https" or host not in allowed or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("URL must use HTTPS and point to youtube.com or youtu.be")
    if not parsed.path or parsed.path == "/":
        raise ValueError("URL must identify a YouTube video or playlist")
    path = parsed.path.rstrip("/")
    video_id = parse_qs(parsed.query).get("v", [""])[0]
    playlist_id = parse_qs(parsed.query).get("list", [""])[0]
    video_path = any(
        path.startswith(prefix) and re.fullmatch(r"[A-Za-z0-9_-]{11}", path[len(prefix):])
        for prefix in ("/shorts/", "/embed/", "/live/")
    )
    short_link = host == "youtu.be" and bool(re.fullmatch(r"/[A-Za-z0-9_-]{11}", path))
    watch_link = path == "/watch" and bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id))
    playlist_link = path == "/playlist" and bool(re.fullmatch(r"[A-Za-z0-9_-]{10,128}", playlist_id))
    if not (video_path or short_link or watch_link or playlist_link):
        raise ValueError("URL must identify a YouTube video or playlist")
    return value


def _validate_playlist_id(value: Optional[str]) -> Optional[str]:
    if value is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value.strip()):
        raise ValueError("playlist_id contains invalid characters")
    return value.strip() if value is not None else None

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


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a request ID to each response and log latency without logging user content."""
    provided_id = request.headers.get("X-Request-ID", "")[:128]
    request_id = provided_id if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", provided_id) else str(uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id, request.method, request.url.path, response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response
    except Exception:
        logger.exception("request_failed request_id=%s path=%s", request_id, request.url.path)
        raise


class IngestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    url: str = Field(..., min_length=11, max_length=2048, description="YouTube video or playlist URL")
    collection_name: str = Field(default="yt_transcripts", description="Qdrant collection name for transcript chunks")
    videos_collection: str = Field(default="yt_videos", description="Qdrant collection name for Tier 1 video registry")
    target_words: int = Field(default=180, ge=50, le=1000, description="Target word count per chunk")
    overlap_words: int = Field(default=35, ge=0, le=200, description="Word overlap between chunks")
    force_playlist: bool = Field(default=False, description="Set True to force full playlist ingestion when URL contains list=")
    deep_ingest: bool = Field(default=False, description="Queue every playlist video for durable background indexing. Default False indexes the selected video first, then queues the remaining videos.")

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _validate_youtube_url(value)

    @field_validator("collection_name", "videos_collection")
    @classmethod
    def validate_collections(cls, value: str) -> str:
        return _validate_collection_name(value)

    @model_validator(mode="after")
    def validate_overlap(self):
        if self.overlap_words >= self.target_words:
            raise ValueError("overlap_words must be smaller than target_words")
        return self


class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    query: str = Field(..., min_length=1, max_length=1000, description="Search query string")
    collection_name: str = Field(default="yt_transcripts", description="Qdrant collection name")
    videos_collection: str = Field(default="yt_videos", description="Qdrant collection name for Tier 1 video registry")
    limit: int = Field(default=5, ge=1, le=50, description="Maximum results to return")
    video_id: Optional[str] = Field(default=None, description="Optional filter by specific YouTube video ID")
    playlist_id: Optional[str] = Field(default=None, description="Optional filter by specific YouTube playlist ID")
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Minimum cosine similarity score")
    enable_jit: bool = Field(default=True, description="Enable JIT on-demand transcript fetching")

    @field_validator("collection_name", "videos_collection")
    @classmethod
    def validate_collections(cls, value: str) -> str:
        return _validate_collection_name(value)

    @field_validator("video_id")
    @classmethod
    def validate_video(cls, value: Optional[str]) -> Optional[str]:
        return _validate_video_id(value)

    @field_validator("playlist_id")
    @classmethod
    def validate_playlist(cls, value: Optional[str]) -> Optional[str]:
        return _validate_playlist_id(value)


class ChatHistoryMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1200)


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(..., min_length=1, max_length=1000, description="User question to answer using indexed video transcripts")
    collection_name: str = Field(default="yt_transcripts", description="Qdrant collection name")
    videos_collection: str = Field(default="yt_videos", description="Qdrant collection name for Tier 1 video registry")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")
    min_score: float = Field(default=0.50, ge=0.0, le=1.0, description="Minimum similarity score cutoff")
    video_id: Optional[str] = Field(default=None, description="Optional filter to a specific video")
    playlist_id: Optional[str] = Field(default=None, description="Optional filter to a specific playlist")
    enable_jit: bool = Field(default=True, description="Enable JIT on-demand transcript fetching")
    chat_history: List[ChatHistoryMessage] = Field(default_factory=list, max_length=8)

    @field_validator("collection_name", "videos_collection")
    @classmethod
    def validate_collections(cls, value: str) -> str:
        return _validate_collection_name(value)

    @field_validator("video_id")
    @classmethod
    def validate_video(cls, value: Optional[str]) -> Optional[str]:
        return _validate_video_id(value)

    @field_validator("playlist_id")
    @classmethod
    def validate_playlist(cls, value: Optional[str]) -> Optional[str]:
        return _validate_playlist_id(value)

    @model_validator(mode="after")
    def limit_history_payload(self):
        if sum(len(message.content) for message in self.chat_history) > 4000:
            raise ValueError("Combined chat history must be 4000 characters or fewer")
        return self


@app.get("/")
def root():
    return {
        "message": "YouTube Playlist RAG Assistant API is online",
        "docs": "/docs",
        "endpoints": [
            "/api/health",
            "/api/ready",
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
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        has_gemini = bool(os.getenv("GEMINI_API_KEY"))
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
                "provider": "gemini",
                "model": gemini_model,
                "configured": has_gemini,
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
        logger.exception("health_check_failed")
        return {
            "status": "degraded",
            "error": "A required service could not be reached",
        }


@app.get("/api/ready")
def readiness_check():
    """Readiness probe for Qdrant; unlike liveness, this requires the data store."""
    try:
        store = get_vector_store()
        store.client.get_collections()
        return {"status": "ready", "qdrant_target": store.target_url}
    except Exception as exc:
        logger.exception("readiness_check_failed")
        raise HTTPException(status_code=503, detail="Vector database is unavailable") from exc


@app.get("/api/videos")
def get_indexed_videos(
    collection_name: str = Query(default="yt_videos", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
    limit: int = Query(default=1000, ge=1, le=1000),
):
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
        logger.exception("list_videos_failed")
        raise HTTPException(status_code=500, detail="Failed to list videos") from e


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
        logger.exception("ingest_url_failed")
        raise HTTPException(status_code=500, detail="Failed to ingest the YouTube URL") from e


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
        logger.exception("ingestion_status_failed")
        raise HTTPException(status_code=500, detail="Failed to fetch ingestion status") from e


@app.get("/api/ingest/jobs")
def get_ingestion_jobs(limit: int = Query(default=20, ge=1, le=100)):
    """List recent durable ingestion jobs with per-video progress."""
    try:
        return {"jobs": get_vector_store().list_ingestion_jobs(limit=limit)}
    except Exception as e:
        logger.exception("list_ingestion_jobs_failed")
        raise HTTPException(status_code=500, detail="Failed to list ingestion jobs") from e


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
        logger.exception("get_ingestion_job_failed")
        raise HTTPException(status_code=500, detail="Failed to fetch ingestion job") from e


@app.post("/api/ingest/jobs/{job_id}/retry")
def retry_ingestion_job(
    job_id: str,
    video_id: Optional[str] = Query(default=None, min_length=11, max_length=11, pattern=r"^[A-Za-z0-9_-]{11}$"),
):
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
        logger.exception("retry_ingestion_job_failed")
        raise HTTPException(status_code=500, detail="Failed to retry ingestion job") from e


@app.post("/api/ingest/resume")
def resume_background_ingestion():
    """Resume paused jobs and restart pending durable work."""
    try:
        store = get_vector_store()
        resumed = store.resume_background_ingest()
        return {"resumed": resumed, "status": store.get_background_ingest_status()}
    except Exception as e:
        logger.exception("resume_ingestion_failed")
        raise HTTPException(status_code=500, detail="Failed to resume ingestion") from e


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
        logger.exception("pause_ingestion_failed")
        raise HTTPException(status_code=500, detail="Failed to pause ingestion") from e


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
        logger.exception("transcript_search_failed")
        raise HTTPException(status_code=500, detail="Transcript search failed") from e


@app.post("/api/chat")
@app.post("/api/ask")
def chat_with_lectures(request: ChatRequest):
    """
    Full Grounded RAG Chat Endpoint:
    - Runs alongside background ingestion without cancelling the playlist job.
    - Hierarchical Two-Tier Routing: routes question across playlist titles and JIT fetches/chunks transcripts.
    - Retrieves relevant chunks from Qdrant.
    - Guardrail 1: Rejects off-topic questions without calling the LLM.
    - Generates grounded answers using Google Gemini.
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
        logger.exception("chat_generation_failed")
        raise HTTPException(status_code=500, detail="Chat generation failed") from e


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
