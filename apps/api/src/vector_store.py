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
    get_playlist_details,
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

DEFAULT_TRANSCRIPTS_COLLECTION = "yt_transcripts"
DEFAULT_VIDEOS_COLLECTION = "yt_videos"


class VectorStore:
    """
    Manages vector embeddings with FastEmbed and storage/search with Qdrant.
    Supports Hierarchical Two-Tier RAG for large YouTube playlists (300+ videos):
      - Tier 1: Instant video registry indexing for semantic routing across titles (~2s).
      - Tier 2: Just-In-Time (JIT) transcript fetching, chunking, and vector indexing on demand.
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

    def ensure_collection(self, collection_name: str = DEFAULT_TRANSCRIPTS_COLLECTION) -> bool:
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
        collection_name: str = DEFAULT_TRANSCRIPTS_COLLECTION,
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

    def upsert_videos(
        self,
        videos: List[Dict[str, Any]],
        collection_name: str = DEFAULT_VIDEOS_COLLECTION,
        batch_size: int = 64,
    ) -> int:
        """
        Embed and upsert video titles and metadata into Qdrant video registry.
        Enables instant semantic routing across hundreds of videos in a playlist.
        """
        if not videos:
            return 0

        self.ensure_collection(collection_name)
        total_upserted = 0

        for i in range(0, len(videos), batch_size):
            batch = videos[i : i + batch_size]
            # Embed video title for semantic topic routing
            texts = [v.get("title", f"Video {v['video_id']}") for v in batch]
            embeddings = self.embed_texts(texts, batch_size=len(texts))

            points: List[models.PointStruct] = []
            for item, emb in zip(batch, embeddings):
                vid = item["video_id"]
                point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"video_{vid}"))
                payload = {
                    "video_id": vid,
                    "title": item.get("title", f"Video {vid}"),
                    "url": item.get("url", f"https://www.youtube.com/watch?v={vid}"),
                    "playlist_id": item.get("playlist_id"),
                    "playlist_title": item.get("playlist_title"),
                    "is_transcribed": bool(item.get("is_transcribed", False)),
                    "chunks_count": int(item.get("chunks_count", 0)),
                    "status": item.get("status", "registered"),
                }
                points.append(
                    models.PointStruct(
                        id=point_uuid,
                        vector=emb,
                        payload=payload,
                    )
                )

            self.client.upsert(collection_name=collection_name, points=points)
            total_upserted += len(points)

        return total_upserted

    def search_videos(
        self,
        query: str,
        collection_name: str = DEFAULT_VIDEOS_COLLECTION,
        limit: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search Qdrant video metadata registry to route a query to the most relevant videos.
        Returns matching videos with semantic relevance score.
        """
        self.ensure_collection(collection_name)
        query_vector = self.embed_query(query)

        try:
            response = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )
        except Exception as e:
            print(f"Error querying video registry '{collection_name}': {e}")
            return []

        results: List[Dict[str, Any]] = []
        for point in response.points:
            payload = point.payload or {}
            results.append(
                {
                    "score": round(float(point.score), 4),
                    "video_id": payload.get("video_id"),
                    "title": payload.get("title"),
                    "url": payload.get("url"),
                    "playlist_id": payload.get("playlist_id"),
                    "playlist_title": payload.get("playlist_title"),
                    "is_transcribed": bool(payload.get("is_transcribed", False)),
                    "chunks_count": int(payload.get("chunks_count", 0)),
                    "status": payload.get("status", "registered"),
                }
            )
        return results

    def list_videos(
        self,
        collection_name: str = DEFAULT_VIDEOS_COLLECTION,
        limit: int = 300,
    ) -> List[Dict[str, Any]]:
        """List all videos registered in the Qdrant video metadata registry."""
        try:
            self.ensure_collection(collection_name)
            res, _ = self.client.scroll(
                collection_name=collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            videos = []
            for p in res:
                payload = p.payload or {}
                videos.append(
                    {
                        "video_id": payload.get("video_id"),
                        "title": payload.get("title"),
                        "url": payload.get("url"),
                        "playlist_id": payload.get("playlist_id"),
                        "playlist_title": payload.get("playlist_title"),
                        "is_transcribed": bool(payload.get("is_transcribed", False)),
                        "chunks_count": int(payload.get("chunks_count", 0)),
                        "status": payload.get("status", "registered"),
                    }
                )
            return videos
        except Exception as e:
            print(f"Error listing videos from '{collection_name}': {e}")
            return []

    def is_video_transcribed(
        self,
        video_id: str,
        collection_name: str = DEFAULT_TRANSCRIPTS_COLLECTION,
    ) -> bool:
        """Check if chunks for this video already exist in the transcripts collection."""
        try:
            self.ensure_collection(collection_name)
            cnt = self.client.count(
                collection_name=collection_name,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="video_id",
                            match=models.MatchValue(value=video_id),
                        )
                    ]
                ),
                exact=False,
            )
            return cnt.count > 0
        except Exception:
            return False

    def ensure_video_transcribed(
        self,
        video_id: str,
        title: Optional[str] = None,
        url: Optional[str] = None,
        transcripts_collection: str = DEFAULT_TRANSCRIPTS_COLLECTION,
        videos_collection: str = DEFAULT_VIDEOS_COLLECTION,
        target_words: int = 180,
        overlap_words: int = 35,
    ) -> Dict[str, Any]:
        """
        Just-In-Time (JIT) transcript extraction and chunking.
        If video is already transcribed in Qdrant, returns immediately without network calls.
        Otherwise fetches captions, chunks text, and embeds into Qdrant on the fly.
        """
        if self.is_video_transcribed(video_id, collection_name=transcripts_collection):
            chunk_cnt = 0
            try:
                cnt = self.client.count(
                    collection_name=transcripts_collection,
                    count_filter=models.Filter(
                        must=[models.FieldCondition(key="video_id", match=models.MatchValue(value=video_id))]
                    ),
                    exact=False,
                )
                chunk_cnt = cnt.count
            except Exception:
                chunk_cnt = 1
            return {"status": "success", "video_id": video_id, "chunks": chunk_cnt, "already_indexed": True}

        target_url = url or f"https://www.youtube.com/watch?v={video_id}"
        print(f"[JIT] Fetching on-demand transcript for video {video_id} ('{title or target_url}')...")
        segments = get_transcript(target_url)

        point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"video_{video_id}"))

        if not segments:
            print(f"[JIT] No transcript available for {video_id}.")
            try:
                self.ensure_collection(videos_collection)
                self.client.set_payload(
                    collection_name=videos_collection,
                    payload={"status": "no_captions", "is_transcribed": False},
                    points=[point_uuid],
                )
            except Exception:
                pass
            return {"status": "no_captions", "video_id": video_id, "chunks": 0}

        resolved_title = title or f"Video {video_id}"
        chunks = chunk_transcript(
            segments=segments,
            video_id=video_id,
            video_title=resolved_title,
            target_words=target_words,
            overlap_words=overlap_words,
        )

        upserted = self.upsert_chunks(chunks=chunks, collection_name=transcripts_collection)
        print(f"[JIT] Successfully indexed {upserted} chunks for video {video_id}.")

        try:
            self.ensure_collection(videos_collection)
            self.client.set_payload(
                collection_name=videos_collection,
                payload={"status": "success", "is_transcribed": True, "chunks_count": upserted},
                points=[point_uuid],
            )
        except Exception:
            pass

        return {"status": "success", "video_id": video_id, "chunks": upserted}

    def search(
        self,
        query: str,
        collection_name: str = DEFAULT_TRANSCRIPTS_COLLECTION,
        videos_collection: str = DEFAULT_VIDEOS_COLLECTION,
        limit: int = 5,
        score_threshold: Optional[float] = None,
        filter_video_id: Optional[str] = None,
        enable_jit: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search Qdrant for transcript chunks most semantically relevant to the query.
        Incorporates Hierarchical Two-Tier RAG:
        1. If filter_video_id is provided, ensures that video's transcript is loaded JIT.
        2. If no filter_video_id is provided, routes query against video titles in Tier 1
           and JIT-transcribes top matching videos before searching chunks.
        3. Returns matching chunks with relevance score, text, and timestamp links.
        """
        self.ensure_collection(collection_name)

        if enable_jit:
            if filter_video_id:
                # Video-specific filter: JIT ingest this video if not already indexed
                self.ensure_video_transcribed(
                    video_id=filter_video_id,
                    transcripts_collection=collection_name,
                    videos_collection=videos_collection,
                )
            else:
                # Two-tier semantic routing across video titles
                try:
                    top_candidates = self.search_videos(
                        query=query,
                        collection_name=videos_collection,
                        limit=2,
                    )
                    for cand in top_candidates:
                        # If video is not yet transcribed and has reasonable title relevance
                        if cand.get("score", 0.0) >= 0.35 and not cand.get("is_transcribed"):
                            self.ensure_video_transcribed(
                                video_id=cand["video_id"],
                                title=cand.get("title"),
                                url=cand.get("url"),
                                transcripts_collection=collection_name,
                                videos_collection=videos_collection,
                            )
                except Exception as e:
                    print(f"[Two-Tier Routing] Note: {e}")

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
        collection_name: str = DEFAULT_TRANSCRIPTS_COLLECTION,
        videos_collection: str = DEFAULT_VIDEOS_COLLECTION,
        target_words: int = 180,
        overlap_words: int = 35,
        force_playlist: bool = False,
        deep_ingest: bool = False,
    ) -> Dict[str, Any]:
        """
        Hierarchical End-to-End Ingestion Pipeline:
        - If URL is a playlist:
          1. Instantly extracts all video items and metadata via yt-dlp flat extraction (~2s).
          2. Embeds and registers ALL video titles into Tier 1 (Qdrant `yt_videos` registry).
          3. If deep_ingest is False (default): JIT transcribes ONLY the 1st video for instant playback,
             leaving remaining videos to be transcribed on-demand during search/chat queries.
             Takes ~2-3 seconds instead of 10 minutes!
          4. If deep_ingest is True: sequentially transcribes all videos.
        - If URL is a single video:
          Registers in Tier 1 and transcribes into Tier 2.
        """
        is_playlist = is_playlist_url(url, force_playlist=force_playlist)
        videos_to_process: List[Dict[str, str]] = []
        playlist_title: Optional[str] = None
        playlist_id: Optional[str] = None

        if is_playlist:
            print(f"Hierarchical Ingestion for playlist: {url}")
            details = get_playlist_details(url)
            videos_to_process = details.get("videos", [])
            playlist_title = details.get("playlist_title", "YouTube Playlist")
            playlist_id = details.get("playlist_id")
            print(f"Found {len(videos_to_process)} videos in playlist '{playlist_title}'.")

        # Fallback to single video if not a playlist or if playlist extraction yielded nothing
        if not videos_to_process:
            is_playlist = False
            try:
                meta = get_video_metadata(url)
                videos_to_process = [
                    {
                        "video_id": meta["video_id"],
                        "title": meta.get("title", ""),
                        "url": meta.get("url", url),
                    }
                ]
            except Exception as e:
                print(f"Failed to fetch metadata for single video URL '{url}': {e}")

        if not videos_to_process:
            return {
                "success": False,
                "url": url,
                "error": "No videos found or unable to fetch metadata.",
                "videos_total": 0,
                "details": [],
            }

        # ── 1. Register all videos in Tier 1 Registry ──
        for vid in videos_to_process:
            if playlist_id:
                vid["playlist_id"] = playlist_id
            if playlist_title:
                vid["playlist_title"] = playlist_title

        self.upsert_videos(videos_to_process, collection_name=videos_collection)
        print(f"Registered {len(videos_to_process)} videos in Tier 1 registry ('{videos_collection}').")

        # ── 2. Handle Hierarchical Fast Registration vs Full Deep Ingest ──
        results_summary = []
        total_chunks_stored = 0

        # If it's a playlist and NOT deep_ingest: JIT transcribe only the first video
        if is_playlist and not deep_ingest:
            first_vid = videos_to_process[0]
            v_id = first_vid["video_id"]
            title = first_vid.get("title", f"Video {v_id}")
            v_url = first_vid.get("url", f"https://www.youtube.com/watch?v={v_id}")

            print(f"Hierarchical fast-path: JIT indexing first video {v_id} ('{title}')...")
            jit_res = self.ensure_video_transcribed(
                video_id=v_id,
                title=title,
                url=v_url,
                transcripts_collection=collection_name,
                videos_collection=videos_collection,
                target_words=target_words,
                overlap_words=overlap_words,
            )

            total_chunks_stored = jit_res.get("chunks", 0)
            status_val = "success" if (total_chunks_stored > 0 or jit_res.get("status") == "success") else jit_res.get("status", "no_captions")
            results_summary.append({
                "video_id": v_id,
                "title": title,
                "status": status_val,
                "chunks": total_chunks_stored,
            })

            # Mark all remaining videos as registered in Tier 1 (on-demand)
            for vid in videos_to_process[1:]:
                results_summary.append({
                    "video_id": vid["video_id"],
                    "title": vid.get("title", f"Video {vid['video_id']}"),
                    "status": "registered",
                    "chunks": 0,
                })

            return {
                "success": True,
                "mode": "hierarchical",
                "url": url,
                "is_playlist": True,
                "playlist_title": playlist_title,
                "playlist_id": playlist_id,
                "collection_name": collection_name,
                "videos_total": len(videos_to_process),
                "videos_registered": len(videos_to_process),
                "videos_indexed": 1 if total_chunks_stored > 0 else 0,
                "total_chunks_stored": total_chunks_stored,
                "details": results_summary,
                "message": (
                    f"Registered all {len(videos_to_process)} videos instantly! "
                    "First video is loaded for playback; remaining lecture transcripts are indexed on-demand."
                ),
            }

        # Otherwise: Ingest all specified videos (single video or deep_ingest=True)
        for idx, vid in enumerate(videos_to_process):
            v_id = vid["video_id"]
            title = vid.get("title", f"Video {v_id}")
            v_url = vid.get("url", f"https://www.youtube.com/watch?v={v_id}")

            print(f"[{idx+1}/{len(videos_to_process)}] Processing video {v_id} - '{title}'...")
            jit_res = self.ensure_video_transcribed(
                video_id=v_id,
                title=title,
                url=v_url,
                transcripts_collection=collection_name,
                videos_collection=videos_collection,
                target_words=target_words,
                overlap_words=overlap_words,
            )

            chunks_cnt = jit_res.get("chunks", 0)
            total_chunks_stored += chunks_cnt
            status_val = "success" if (chunks_cnt > 0 or jit_res.get("status") == "success") else jit_res.get("status", "no_captions")
            results_summary.append({
                "video_id": v_id,
                "title": title,
                "status": status_val,
                "chunks": chunks_cnt,
            })

        return {
            "success": True,
            "mode": "deep" if is_playlist else "single_video",
            "url": url,
            "is_playlist": is_playlist,
            "playlist_title": playlist_title,
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
