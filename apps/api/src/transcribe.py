import html
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
import httpx
import yt_dlp

# Set UTF-8 encoding for standard output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Cache directory for transcripts
CACHE_DIR = Path(os.getenv("YTRAG_CACHE_DIR", Path(__file__).resolve().parent.parent / "data" / "transcripts"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def clean_text(text: str) -> str:
    """Unescape HTML entities and normalize whitespace."""
    if not text:
        return ""
    text = html.unescape(text)
    # Replace non-breaking spaces and collapse whitespace
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def is_playlist_url(url: str, force_playlist: bool = False) -> bool:
    """
    Check if the given URL is a YouTube playlist URL.
    - If force_playlist is True and a playlist ID exists: True
    - Pure playlist URL: 'youtube.com/playlist?list=...' -> True
    - Playlist URL with list= and NO video ID (no v=) -> True
    - Video URL with playlist context (watch?v=...&list=...): False by default,
      because the user is usually targeting the specific video they are watching.
    """
    if force_playlist and extract_playlist_id(url):
        return True
    if "playlist?list=" in url:
        return True
    if "list=" in url and "v=" not in url:
        return True
    return False


def extract_playlist_id(url: str) -> Optional[str]:
    """Extract playlist ID from URL if present."""
    match = re.search(r"[?&]list=([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None


def extract_video_url(url: str) -> str:
    """Extract YouTube 11-character video ID from a URL or raw ID."""
    match = re.search(r"(?:v=|\/|youtu\.be\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})", url)
    if not match:
        if re.match(r"^[0-9A-Za-z_-]{11}$", url.strip()):
            return url.strip()
        raise ValueError(f"Could not extract video ID from URL: {url}")
    return match.group(1)


def get_playlist_details(playlist_url: str) -> Dict[str, Any]:
    """
    Extract playlist metadata and all video items without downloading content.
    Returns:
    {
        "playlist_id": Optional[str],
        "playlist_title": str,
        "videos": List[Dict[str, str]] # [{'video_id': ..., 'title': ..., 'url': ...}]
    }
    """
    playlist_id = extract_playlist_id(playlist_url)
    clean_target = f"https://www.youtube.com/playlist?list={playlist_id}" if playlist_id else playlist_url

    ydl_opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    videos: List[Dict[str, str]] = []
    playlist_title = "YouTube Playlist"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_target, download=False)
            if info:
                playlist_title = info.get("title") or playlist_title
                entries = info.get("entries", [])
                for entry in entries:
                    if not entry:
                        continue
                    video_id = entry.get("id")
                    if not video_id:
                        continue
                    raw_title = entry.get("title")
                    title = str(raw_title).strip() if (raw_title is not None and str(raw_title).strip()) else f"Video {video_id}"
                    videos.append({
                        "video_id": str(video_id),
                        "title": title,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                    })
    except Exception as e:
        print(f"Warning: Failed to fetch playlist from {clean_target}: {e}")

    # Fallback: if no playlist entries found, check if a single video was specified in playlist_url
    if not videos:
        try:
            single_vid = extract_video_url(playlist_url)
            if single_vid:
                meta = get_video_metadata(playlist_url)
                raw_title = meta.get("title")
                title = str(raw_title).strip() if (raw_title is not None and str(raw_title).strip()) else f"Video {single_vid}"
                videos.append({
                    "video_id": str(single_vid),
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={single_vid}",
                })
                playlist_title = title
        except Exception:
            pass

    return {
        "playlist_id": playlist_id,
        "playlist_title": playlist_title,
        "videos": videos,
    }


def get_playlist_videos(playlist_url: str) -> List[Dict[str, str]]:
    """
    Extract video IDs and titles from a YouTube playlist without downloading content.
    Returns a list of dicts: [{'video_id': ..., 'title': ..., 'url': ...}]
    """
    return get_playlist_details(playlist_url)["videos"]



def get_video_metadata(url: str) -> Dict[str, Any]:
    """
    Fetch lightweight metadata for a single video.
    Returns dict with video_id, title, channel, duration, and clean_url.
    """
    video_id = extract_video_url(url)
    clean_url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            raw_title = info.get("title") if info else None
            title = str(raw_title).strip() if (raw_title is not None and str(raw_title).strip()) else f"YouTube Video {video_id}"
            return {
                "video_id": str(video_id),
                "title": title,
                "channel": (info.get("uploader") or info.get("channel", "Unknown Channel")) if info else "Unknown Channel",
                "duration": info.get("duration", 0) if info else 0,
                "url": clean_url,
            }
    except Exception as e:
        return {
            "video_id": str(video_id),
            "title": f"YouTube Video {video_id}",
            "channel": "Unknown Channel",
            "duration": 0,
            "url": clean_url,
            "error": str(e),
        }


def parse_vtt_subtitles(vtt_text: str) -> List[Dict[str, Any]]:
    """Fallback parser for WebVTT subtitle format."""
    segments = []
    cue_pattern = re.compile(
        r"(?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3})\s+-->\s+(?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3})"
    )

    def to_seconds(h, m, s, ms):
        hours = int(h or 0)
        minutes = int(m)
        seconds = int(s)
        millis = int(ms)
        return hours * 3600 + minutes * 60 + seconds + millis / 1000.0

    lines = vtt_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = cue_pattern.search(line)
        if match:
            h1, m1, s1, ms1, h2, m2, s2, ms2 = match.groups()
            start = to_seconds(h1, m1, s1, ms1)
            end = to_seconds(h2, m2, s2, ms2)
            duration = max(0.0, end - start)
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                cleaned_line = re.sub(r"<[^>]+>", "", lines[i])
                text_lines.append(cleaned_line)
                i += 1
            segment_text = clean_text(" ".join(text_lines))
            if segment_text:
                segments.append({"start": start, "duration": duration, "text": segment_text})
        else:
            i += 1
    return segments


def _load_cached_transcript(video_id: str) -> Optional[List[Dict[str, Any]]]:
    """Check if transcript is already cached on disk."""
    cache_file = CACHE_DIR / f"{video_id}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("segments", [])
        except Exception as e:
            print(f"Warning: Failed reading cache for {video_id}: {e}")
    return None


def _save_cached_transcript(video_id: str, segments: List[Dict[str, Any]], title: str = "") -> None:
    """Atomically save transcript to local JSON cache to prevent partial writes."""
    if not segments:
        return
    cache_file = CACHE_DIR / f"{video_id}.json"
    temp_file = CACHE_DIR / f"{video_id}.tmp"
    try:
        payload = {
            "video_id": video_id,
            "title": title,
            "total_segments": len(segments),
            "segments": segments,
        }
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, cache_file)
    except Exception as e:
        print(f"Warning: Failed caching transcript for {video_id}: {e}")
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass


def get_transcript(url: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Fetch transcript segments with timestamps for a YouTube video.
    Checks local disk cache first. If not cached, fetches from YouTube.
    Returns a list of dicts: [{'start': float, 'duration': float, 'text': str}]
    """
    video_id = extract_video_url(url)

    # 1. Check local cache first (idempotent & fast)
    if not force_refresh:
        cached = _load_cached_transcript(video_id)
        if cached is not None:
            return cached

    clean_url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": ["android"]}},
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            video_title = info.get("title", f"Video {video_id}")

            # Filter out non-subtitle tracks like live_chat
            subs = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat"}
            auto = {k: v for k, v in (info.get("automatic_captions") or {}).items() if k != "live_chat"}
            # Manual subtitles take precedence over auto-generated ones (merge: auto first, subs overwrite)
            all_subs = {**auto, **subs}

            if not all_subs:
                print(f"No captions found for video {video_id}.")
                return []

            # Priority order:
            # 1. *-orig tracks — the raw original-language audio (most accurate for non-English content)
            #    Sort by explicit preference: hi-orig > en-orig > other-orig
            # 2. Manual subtitles in common Indian/Hinglish languages
            # 3. English variants as fallback (may be auto-translated and lower quality for non-EN videos)
            # 4. Any remaining track
            _ORIG_PREF = ["hi-orig", "en-orig", "pa-orig", "ur-orig", "bn-orig", "mr-orig"]
            orig_keys_raw = [k for k in all_subs if k.endswith("-orig")]
            orig_keys = sorted(
                orig_keys_raw,
                key=lambda k: _ORIG_PREF.index(k) if k in _ORIG_PREF else len(_ORIG_PREF),
            )
            preferred_keys = (
                orig_keys  # e.g. hi-orig, en-orig — always prefer original speech
                + ["hi", "hi-IN", "pa", "ur", "bn", "mr", "te", "ta", "kn", "gu", "ml"]  # Indian languages
                + ["en", "en-US", "en-GB", "en-CA"]  # English fallbacks (may be translated)
            )
            track_key = None
            track_list = None
            for key in preferred_keys:
                if key in all_subs:
                    track_key = key
                    track_list = all_subs[key]
                    break
            if not track_list:
                track_key, track_list = next(iter(all_subs.items()))
            print(f"  -> Selected caption track: '{track_key}' (from {len(all_subs)} available: {list(all_subs.keys())[:8]}{'...' if len(all_subs) > 8 else ''})")  # noqa: E501

            # 1. Look for json3 format first (standard for Android client)
            json3_track = next((t for t in track_list if t.get("ext") == "json3"), None)
            if json3_track and "url" in json3_track:
                res = httpx.get(json3_track["url"], timeout=15.0)
                if res.status_code == 200:
                    data = res.json()
                    segments: List[Dict[str, Any]] = []
                    for event in data.get("events", []):
                        if "segs" in event:
                            raw_text = "".join(s.get("utf8", "") for s in event["segs"])
                            cleaned = clean_text(raw_text)
                            if cleaned:
                                start = event.get("tStartMs", 0) / 1000.0
                                duration = event.get("dDurationMs", 0) / 1000.0
                                segments.append({"start": start, "duration": duration, "text": cleaned})
                    if segments:
                        _save_cached_transcript(video_id, segments, video_title)
                        return segments

            # 2. Fallback to vtt format if json3 wasn't available
            vtt_track = next((t for t in track_list if t.get("ext") == "vtt"), None)
            if vtt_track and "url" in vtt_track:
                res = httpx.get(vtt_track["url"], timeout=15.0)
                if res.status_code == 200:
                    segments = parse_vtt_subtitles(res.text)
                    if segments:
                        _save_cached_transcript(video_id, segments, video_title)
                        return segments

            print(f"No parseable caption track available for video {video_id}.")
            return []
    except Exception as e:
        print(f"Error fetching transcript for {video_id}: {e}")
        return []


if __name__ == "__main__":
    url_input = input(">> Enter YouTube video or playlist URL: ").strip()
    if not url_input:
        url_input = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    if is_playlist_url(url_input):
        print(f"Detected playlist URL. Extracting videos...")
        videos = get_playlist_videos(url_input)
        print(f"Found {len(videos)} videos in playlist.")
        if videos:
            first = videos[0]
            print(f"\nProcessing first video: {first['title']} ({first['video_id']})")
            segs = get_transcript(first["url"])
            print(f"Fetched {len(segs)} segments.")
            for s in segs[:3]:
                print(f"  [{s['start']:.1f}s - {s['start'] + s['duration']:.1f}s]: {s['text']}")
    else:
        print(f"Fetching transcript for video: {url_input}")
        meta = get_video_metadata(url_input)
        print(f"Title: {meta.get('title')}")
        segments = get_transcript(url_input)
        print(f"\nTotal segments fetched: {len(segments)}")
        print("\nFirst 3 segments:")
        for s in segments[:3]:
            print(f"  [{s['start']:.1f}s - {s['start'] + s['duration']:.1f}s]: {s['text']}")
