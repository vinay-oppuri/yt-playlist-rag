import os
from typing import Any, Dict, List, Literal, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from src.generator import generate_answer
from src.vector_store import get_vector_store

load_dotenv()

app = FastAPI(
    title="YouTube Playlist RAG API",
    description="API for transcribing YouTube videos/playlists, generating vector embeddings, and answering context-aware questions with grounded timestamps.",
    version="0.2.0",
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
    deep_ingest: bool = Field(default=False, description="Set True to transcribe every video in playlist upfront. Default False uses instant Hierarchical Tier 1 registration.")


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
        return {
            "status": "healthy",
            "qdrant_target": store.target_url,
            "embedding_model": store.embedding_model_name,
            "vector_dimension": store.vector_dim,
            "collections": collection_names,
            "llm": {
                "configured_provider": llm_provider,
                "has_gemini_key": has_gemini,
                "has_groq_key": has_groq,
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
    - If playlist: Instantly registers all video titles and metadata into Tier 1 (yt_videos) in ~2s.
      Transcribes 1st video for immediate playback; remaining transcripts load on-demand (JIT).
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
    Returns whether the worker is active, the video currently being chunked, and completion count.
    """
    try:
        store = get_vector_store()
        return store.get_background_ingest_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch ingest status: {str(e)}")


@app.post("/api/ingest/stop")
def stop_background_ingestion():
    """
    Manually halt any active background playlist ingestion worker.
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
    Halts background ingestion immediately upon arrival.
    Uses Two-Tier routing: if query relates to an unindexed lecture, it transcribes and chunks JIT.
    Returns matched chunks with timestamps, lead-in links, and text preview.
    """
    try:
        store = get_vector_store()
        store.stop_background_ingest(reason=f"search_query: {request.query[:30]}")
        hits = store.search(
            query=request.query,
            collection_name=request.collection_name,
            videos_collection=request.videos_collection,
            limit=request.limit,
            score_threshold=request.score_threshold,
            filter_video_id=request.video_id,
            filter_playlist_id=request.playlist_id,
            enable_jit=request.enable_jit,
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
    - Halts background ingestion immediately upon query arrival.
    - Hierarchical Two-Tier Routing: routes question across playlist titles and JIT fetches/chunks transcripts.
    - Retrieves relevant chunks from Qdrant.
    - Guardrail 1: Rejects off-topic questions without calling the LLM.
    - Generates grounded answers using Gemini or Groq.
    - Guardrail 2: Enforces refusal if excerpts are insufficient.
    - Guardrail 3: Filters and renumbers only cited timestamps.
    """
    try:
        store = get_vector_store()
        store.stop_background_ingest(reason=f"chat_query: {request.question[:30]}")
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
        )
        return {
            "question": request.question,
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
