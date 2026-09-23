import os
from typing import Any, Dict, List, Optional
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
    description="API for transcribing YouTube videos/playlists, generating vector embeddings, and answering questions with grounded timestamps.",
    version="0.2.0",
)

# Enable CORS for Next.js web application
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestRequest(BaseModel):
    url: str = Field(..., description="YouTube video or playlist URL")
    collection_name: str = Field(default="yt_transcripts", description="Qdrant collection name")
    target_words: int = Field(default=180, ge=50, le=1000, description="Target word count per chunk")
    overlap_words: int = Field(default=35, ge=0, le=200, description="Word overlap between chunks")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query string")
    collection_name: str = Field(default="yt_transcripts", description="Qdrant collection name")
    limit: int = Field(default=5, ge=1, le=50, description="Maximum results to return")
    video_id: Optional[str] = Field(default=None, description="Optional filter by specific YouTube video ID")
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Minimum cosine similarity score")


class ChatRequest(BaseModel):
    question: str = Field(..., description="User question to answer using indexed video transcripts")
    collection_name: str = Field(default="yt_transcripts", description="Qdrant collection name")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")
    min_score: float = Field(default=0.50, ge=0.0, le=1.0, description="Minimum similarity score cutoff")
    video_id: Optional[str] = Field(default=None, description="Optional filter to a specific video")


@app.get("/")
def root():
    return {
        "message": "YouTube Playlist RAG Assistant API is online",
        "docs": "/docs",
        "endpoints": ["/api/health", "/api/ingest", "/api/search", "/api/chat"],
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


@app.post("/api/ingest")
def ingest_url(request: IngestRequest):
    """
    Ingest a YouTube video or playlist:
    - Fetches captions / subtitles with timestamps (with atomic disk cache)
    - Chunks text into semantic windows with title prefixing and -5s lead-in
    - Generates vector embeddings using FastEmbed
    - Stores vectors and payloads into Qdrant
    """
    try:
        store = get_vector_store()
        result = store.ingest_youtube_url(
            url=request.url,
            collection_name=request.collection_name,
            target_words=request.target_words,
            overlap_words=request.overlap_words,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest URL: {str(e)}")


@app.post("/api/search")
def search_transcripts(request: SearchRequest):
    """
    Perform semantic vector search across ingested YouTube transcripts.
    Returns matched chunks with timestamps, lead-in links, and text preview.
    """
    try:
        store = get_vector_store()
        hits = store.search(
            query=request.query,
            collection_name=request.collection_name,
            limit=request.limit,
            score_threshold=request.score_threshold,
            filter_video_id=request.video_id,
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
    - Retrieves relevant chunks from Qdrant
    - Guardrail 1: Rejects off-topic questions without calling the LLM
    - Generates grounded answers using Gemini or Groq
    - Guardrail 2: Enforces refusal if excerpts are insufficient
    - Guardrail 3: Filters and renumbers only cited timestamps
    """
    try:
        result = generate_answer(
            question=request.question,
            collection_name=request.collection_name,
            top_k=request.top_k,
            min_score=request.min_score,
            filter_video_id=request.video_id,
        )
        return {
            "question": request.question,
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)