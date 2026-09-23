from collections import Counter
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional

_SENTENCE_SPLIT = re.compile(r"[.!?\n]+")


def is_repetitive(text: str, threshold: float = 0.6) -> bool:
    """
    Check if one sentence makes up most of the chunk.
    Catches caption/Whisper loop hallucinations on background music or silences.
    These repetitive chunks are retrieval poison: they match everything and say nothing.
    """
    sentences = [s.strip().lower() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if len(sentences) < 3:
        return False
    most_common_count = Counter(sentences).most_common(1)[0][1]
    return (most_common_count / len(sentences)) >= threshold


def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS."""
    total_seconds = max(0, int(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


@dataclass
class TranscriptChunk:
    id: str
    text: str
    body: str  # Raw body without title prefix
    start: float
    end: float
    link_sec: int  # -5s offset timestamp for player jump
    video_id: str
    video_title: str
    video_url: str
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def timestamp(self) -> str:
        return format_timestamp(self.start)

    def to_payload(self) -> Dict[str, Any]:
        """Convert chunk into a JSON-serializable dictionary for Qdrant payload storage."""
        return {
            "chunk_id": self.id,
            "text": self.text,
            "body": self.body,
            "start": round(self.start, 2),
            "end": round(self.end, 2),
            "link_sec": self.link_sec,
            "timestamp": self.timestamp,
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
    target_words: int = 180,
    overlap_words: int = 35,
    min_words: int = 15,
    lead_in_seconds: int = 5,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> List[TranscriptChunk]:
    """
    Split transcript segments into semantic chunks with a sliding window,
    preserving exact start and end timestamps, applying a -5s lead-in for player jumping,
    filtering repetition loops, and prefixing the video title for strong retrieval grounding.
    """
    if not segments:
        return []

    valid_segments = [s for s in segments if s.get("text", "").strip()]
    if not valid_segments:
        return []

    chunks: List[TranscriptChunk] = []
    num_segments = len(valid_segments)
    start_idx = 0
    chunk_index = 0
    resolved_title = video_title or f"Video {video_id}"

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

        chunk_segs = valid_segments[start_idx:end_idx]
        if not chunk_segs:
            break

        body_text = " ".join(s["text"].strip() for s in chunk_segs)
        start_time = float(chunk_segs[0]["start"])
        last_seg = chunk_segs[-1]
        end_time = float(last_seg["start"]) + float(last_seg.get("duration", 0.0))

        word_count = len(body_text.split())

        # Guard 1: Drop very short chunks (e.g. intros, silence, outros)
        # Guard 2: Filter out repetitive loop hallucinations
        if word_count >= min_words and not is_repetitive(body_text):
            # The -5s rule: jump lands slightly before explanation begins
            link_start_sec = max(0, int(start_time) - lead_in_seconds)
            video_url = f"https://www.youtube.com/watch?v={video_id}&t={link_start_sec}s"

            # Title prefixing: acts as semantic anchor for retrieval
            enriched_text = f"{resolved_title}\n\n{body_text}"
            chunk_id = f"{video_id}_c{chunk_index}"

            chunks.append(
                TranscriptChunk(
                    id=chunk_id,
                    text=enriched_text,
                    body=body_text,
                    start=start_time,
                    end=end_time,
                    link_sec=link_start_sec,
                    video_id=video_id,
                    video_title=resolved_title,
                    video_url=video_url,
                    chunk_index=chunk_index,
                    metadata=extra_metadata or {},
                )
            )
            chunk_index += 1

        if end_idx >= num_segments:
            break

        # Calculate next start_idx using overlap_words without splitting segments
        accumulated_overlap = 0
        next_start = end_idx
        for rewind_idx in range(end_idx - 1, start_idx, -1):
            accumulated_overlap += len(valid_segments[rewind_idx]["text"].split())
            if accumulated_overlap >= overlap_words:
                next_start = rewind_idx
                break

        # Guarantee forward progress
        if next_start <= start_idx:
            next_start = start_idx + 1

        start_idx = next_start

    return chunks


if __name__ == "__main__":
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
        min_words=5,
    )
    print(f"Generated {len(test_chunks)} chunks:")
    for c in test_chunks:
        print(f"\n[{c.id}] ({c.timestamp}) -> Link: {c.video_url}")
        print(f"Text Preview:\n{c.text[:80]}...")
        print(f"Payload: {c.to_payload()}")
