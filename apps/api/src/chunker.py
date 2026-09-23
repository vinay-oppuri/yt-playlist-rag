from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TranscriptChunk:
    id: str
    text: str
    start: float
    end: float
    video_id: str
    video_title: str
    video_url: str
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        """Convert chunk into a JSON-serializable dictionary for Qdrant payload storage."""
        return {
            "chunk_id": self.id,
            "text": self.text,
            "start": round(self.start, 2),
            "end": round(self.end, 2),
            "duration": round(max(0.0, self.end - self.start), 2),
            "video_id": self.video_id,
            "video_title": self.video_title,
            "video_url": self.video_url,
            "chunk_index": self.chunk_index,
            **self.metadata,
        }


def chunk_transcript(
    segments: List[Dict[str, Any]],
    video_id: str,
    video_title: str = "",
    target_words: int = 200,
    overlap_words: int = 40,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> List[TranscriptChunk]:
    """
    Split transcript segments into semantic chunks with a sliding window,
    preserving exact start and end timestamps and generating deep-link URLs.

    Args:
        segments: List of dicts, each with keys 'start', 'duration', 'text'
        video_id: YouTube video ID
        video_title: Title of the video (optional)
        target_words: Target word count per chunk
        overlap_words: Word count overlap between consecutive chunks
        extra_metadata: Optional additional metadata (e.g. playlist_id, channel)

    Returns:
        List of TranscriptChunk objects
    """
    if not segments:
        return []

    # Filter out empty or whitespace-only segments
    valid_segments = [s for s in segments if s.get("text", "").strip()]
    if not valid_segments:
        return []

    chunks: List[TranscriptChunk] = []
    num_segments = len(valid_segments)
    start_idx = 0
    chunk_index = 0

    while start_idx < num_segments:
        curr_words = 0
        end_idx = start_idx

        # Accumulate segments until target_words is reached
        while end_idx < num_segments:
            seg_text = valid_segments[end_idx]["text"].strip()
            words_in_seg = len(seg_text.split())
            curr_words += words_in_seg
            end_idx += 1
            if curr_words >= target_words:
                break

        # Slice the segments for this chunk
        chunk_segs = valid_segments[start_idx:end_idx]
        if not chunk_segs:
            break

        chunk_text = " ".join(s["text"].strip() for s in chunk_segs)
        start_time = float(chunk_segs[0]["start"])
        last_seg = chunk_segs[-1]
        end_time = float(last_seg["start"]) + float(last_seg.get("duration", 0.0))

        # Deep link direct to timestamp
        start_sec_int = max(0, int(start_time))
        video_url = f"https://www.youtube.com/watch?v={video_id}&t={start_sec_int}s"

        chunk_id = f"{video_id}_c{chunk_index}"
        chunks.append(
            TranscriptChunk(
                id=chunk_id,
                text=chunk_text,
                start=start_time,
                end=end_time,
                video_id=video_id,
                video_title=video_title or f"Video {video_id}",
                video_url=video_url,
                chunk_index=chunk_index,
                metadata=extra_metadata or {},
            )
        )
        chunk_index += 1

        # If reached end of segments, finish
        if end_idx >= num_segments:
            break

        # Calculate next start_idx using overlap_words
        accumulated_overlap = 0
        next_start = end_idx
        for rewind_idx in range(end_idx - 1, start_idx, -1):
            accumulated_overlap += len(valid_segments[rewind_idx]["text"].split())
            if accumulated_overlap >= overlap_words:
                next_start = rewind_idx
                break

        # Guarantee forward progress by at least 1 segment
        if next_start <= start_idx:
            next_start = start_idx + 1

        start_idx = next_start

    return chunks


if __name__ == "__main__":
    # Quick self-test with dummy segments
    dummy_segments = [
        {"start": 0.0, "duration": 4.0, "text": "Welcome to our complete guide on vector search and embeddings."},
        {"start": 4.0, "duration": 3.5, "text": "Today we are building an end-to-end RAG system with YouTube playlists."},
        {"start": 7.5, "duration": 5.0, "text": "First, we fetch the transcript using yt-dlp and extract subtitles."},
        {"start": 12.5, "duration": 4.0, "text": "Next, we chunk the segments with timestamps into semantic windows."},
        {"start": 16.5, "duration": 4.5, "text": "Then, we compute dense vector embeddings with FastEmbed and store them in Qdrant."},
    ]
    test_chunks = chunk_transcript(
        dummy_segments,
        video_id="test1234567",
        video_title="Vector Search Guide",
        target_words=20,
        overlap_words=5,
    )
    print(f"Generated {len(test_chunks)} chunks:")
    for c in test_chunks:
        print(f"\n[{c.id}] ({c.start:.1f}s - {c.end:.1f}s) -> {c.video_url}")
        print(f"Text: {c.text}")
        print(f"Payload: {c.to_payload()}")
