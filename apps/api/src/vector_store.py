import os
import sys
import uuid
from typing import Any, Dict, List, Optional
from fastembed import TextEmbedding
import httpx
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.chunker import TranscriptChunk, chunk_transcript
from src.transcribe import (
    get_playlist_videos,
    get_transcript,
    get_video_metadata,
    is_playlist_url,
)

# Ensure console UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class VectorStore:
    """
    Manages vector embeddings with FastEmbed and storage/search with Qdrant.
    Supports connecting to Qdrant Docker/server with seamless local disk fallback.
    """

    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        local_path: str = "./qdrant_storage",
        embedding_model_name: str = "BAAI/bge-small-en-v1.5",
    ):
        self.embedding_model_name = embedding_model_name
        self.vector_dim = 384  # Default for BAAI/bge-small-en-v1.5
        self.target_url = qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.local_path = local_path

        # 1. Initialize FastEmbed model
        print(f"Loading FastEmbed model: {self.embedding_model_name}...")
        self.embedder = TextEmbedding(model_name=self.embedding_model_name)

        # 2. Connect to Qdrant (server or local disk fallback)
        self.client = self._init_qdrant_client()

    def _init_qdrant_client(self) -> QdrantClient:
        """Connect to Qdrant server if running, otherwise fallback to local on-disk storage."""
        # Test if remote Qdrant server is reachable
        try:
            res = httpx.get(f"{self.target_url.rstrip('/')}/readyz", timeout=1.5)
            if res.status_code == 200:
                print(f"Connected to Qdrant server at {self.target_url}")
                return QdrantClient(url=self.target_url)
        except Exception:
            pass

        print(
            f"Qdrant server at '{self.target_url}' is not accessible. "
            f"Falling back to local disk storage at '{self.local_path}'."
        )
        os.makedirs(self.local_path, exist_ok=True)
        return QdrantClient(path=self.local_path)

    def ensure_collection(self, collection_name: str = "yt_transcripts") -> bool:
        """Create Qdrant collection if it does not already exist."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)
            if not exists:
                print(f"Creating Qdrant collection '{collection_name}' (dim={self.vector_dim}, distance=Cosine)...")
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_dim,
                        distance=models.Distance.COSINE,
                    ),
                )
            return True
        except Exception as e:
            print(f"Error checking/creating collection '{collection_name}': {e}")
            raise

    def embed_texts(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """Generate dense vector embeddings for a list of text strings."""
        if not texts:
            return []
        embeddings_gen = self.embedder.embed(texts, batch_size=batch_size)
        return [vec.tolist() for vec in embeddings_gen]

    def embed_query(self, query: str) -> List[float]:
        """Generate embedding vector for a single search query."""
        results = self.embed_texts([query])
        return results[0] if results else []

    def upsert_chunks(
        self,
        chunks: List[TranscriptChunk],
        collection_name: str = "yt_transcripts",
        batch_size: int = 64,
    ) -> int:
        """
        Embed and upsert transcript chunks with payloads into Qdrant.
        Uses deterministic UUIDs derived from chunk IDs for idempotent storage.
        """
        if not chunks:
            return 0

        self.ensure_collection(collection_name)

        total_upserted = 0
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            texts = [c.text for c in batch_chunks]
            embeddings = self.embed_texts(texts, batch_size=len(texts))

            points: List[models.PointStruct] = []
            for chunk, emb in zip(batch_chunks, embeddings):
                # Qdrant requires point IDs to be valid integers or UUIDs
                point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.id))
                points.append(
                    models.PointStruct(
                        id=point_uuid,
                        vector=emb,
                        payload=chunk.to_payload(),
                    )
                )

            self.client.upsert(collection_name=collection_name, points=points)
            total_upserted += len(points)

        return total_upserted

    def search(
        self,
        query: str,
        collection_name: str = "yt_transcripts",
        limit: int = 5,
        score_threshold: Optional[float] = None,
        filter_video_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search Qdrant for transcript chunks most semantically relevant to the query.
        Returns matching chunks with relevance score, text, and timestamp links.
        """
        self.ensure_collection(collection_name)
        query_vector = self.embed_query(query)

        query_filter = None
        if filter_video_id:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="video_id",
                        match=models.MatchValue(value=filter_video_id),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )

        results: List[Dict[str, Any]] = []
        for point in response.points:
            payload = point.payload or {}
            start_val = float(payload.get("start", 0.0))
            end_val = float(payload.get("end", 0.0))
            link_sec_val = int(payload.get("link_sec", max(0, int(start_val) - 5)))
            results.append(
                {
                    "score": round(float(point.score), 4),
                    "chunk_id": payload.get("chunk_id"),
                    "text": payload.get("text"),
                    "body": payload.get("body", payload.get("text", "")),
                    "start": start_val,
                    "end": end_val,
                    "link_sec": link_sec_val,
                    "timestamp": payload.get("timestamp") or f"{int(start_val // 60):02d}:{int(start_val % 60):02d}",
                    "duration": payload.get("duration", round(max(0.0, end_val - start_val), 2)),
                    "video_id": payload.get("video_id"),
                    "video_title": payload.get("video_title"),
                    "video_url": payload.get("video_url"),
                }
            )
        return results

    def ingest_youtube_url(
        self,
        url: str,
        collection_name: str = "yt_transcripts",
        target_words: int = 200,
        overlap_words: int = 40,
    ) -> Dict[str, Any]:
        """
        Complete end-to-end ingestion pipeline:
        1. Identifies if URL is a single video or playlist
        2. Retrieves transcripts with timestamps
        3. Chunks transcripts preserving time intervals
        4. Computes vector embeddings and indexes into Qdrant
        """
        is_playlist = is_playlist_url(url)
        videos_to_process: List[Dict[str, str]] = []

        if is_playlist:
            print(f"Ingesting playlist: {url}")
            videos_to_process = get_playlist_videos(url)
            print(f"Found {len(videos_to_process)} videos in playlist.")
        else:
            meta = get_video_metadata(url)
            videos_to_process = [
                {
                    "video_id": meta["video_id"],
                    "title": meta.get("title", ""),
                    "url": meta.get("url", url),
                }
            ]

        results_summary = []
        total_chunks_stored = 0

        for idx, vid in enumerate(videos_to_process):
            v_id = vid["video_id"]
            title = vid.get("title", f"Video {v_id}")
            v_url = vid.get("url", f"https://www.youtube.com/watch?v={v_id}")

            print(f"[{idx+1}/{len(videos_to_process)}] Processing video {v_id} - '{title}'...")
            segments = get_transcript(v_url)

            if not segments:
                print(f"  -> No transcript available for {v_id}, skipping.")
                results_summary.append({
                    "video_id": v_id,
                    "title": title,
                    "status": "no_captions",
                    "chunks": 0,
                })
                continue

            chunks = chunk_transcript(
                segments=segments,
                video_id=v_id,
                video_title=title,
                target_words=target_words,
                overlap_words=overlap_words,
            )

            upserted = self.upsert_chunks(chunks=chunks, collection_name=collection_name)
            total_chunks_stored += upserted
            print(f"  -> Upserted {upserted} vector embeddings for '{title}'.")

            results_summary.append({
                "video_id": v_id,
                "title": title,
                "status": "success",
                "chunks": upserted,
            })

        return {
            "success": True,
            "url": url,
            "is_playlist": is_playlist,
            "collection_name": collection_name,
            "videos_total": len(videos_to_process),
            "videos_indexed": sum(1 for r in results_summary if r["status"] == "success"),
            "total_chunks_stored": total_chunks_stored,
            "details": results_summary,
        }


# Global singleton instance for easy import across FastAPI routes
_global_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create singleton VectorStore instance."""
    global _global_vector_store
    if _global_vector_store is None:
        _global_vector_store = VectorStore()
    return _global_vector_store


if __name__ == "__main__":
    store = get_vector_store()
    print("\n--- Testing Ingestion Pipeline ---")
    test_url = input("Enter YouTube video or playlist URL (or press Enter for Rick Astley test): ").strip()
    if not test_url:
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    ingest_result = store.ingest_youtube_url(test_url)
    print("\nIngest Result:", ingest_result)

    print("\n--- Testing Semantic Search ---")
    query = input("Enter search query (e.g. 'strangers to love'): ").strip()
    if not query:
        query = "strangers to love"

    search_hits = store.search(query, limit=3)
    print(f"\nTop {len(search_hits)} results for query: '{query}':")
    for hit in search_hits:
        print(f"\n[Score: {hit['score']}] Video: {hit['video_title']}")
        print(f"Timestamp: {hit['start']:.1f}s - {hit['end']:.1f}s")
        print(f"Deep Link: {hit['video_url']}")
        print(f"Text: {hit['text']}")
