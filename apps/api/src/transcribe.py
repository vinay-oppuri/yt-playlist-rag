import re
import yt_dlp
import httpx

# URL Extraction
def extract_video_url(url: str) -> str:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    if not match:
        raise ValueError(f"Could not extract video ID from URL: {url}")
    return match.group(1)



#
def get_transcript(url: str) -> str:
    video_id = extract_video_url(url)
    clean_url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": ["android"]}},
        "quiet": True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)

            # Filter out 'live_chat' which is not a subtitle track
            subs = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat"}
            auto = {k: v for k, v in (info.get("automatic_captions") or {}).items() if k != "live_chat"}
            all_subs = {**auto, **subs}

            if not all_subs:
                print("No captions found for this video.")
                return []

            # Prioritize English, then original English, then whatever language is available
            track_list = all_subs.get("en") or all_subs.get("en-orig") or next(iter(all_subs.values()))

            # Look specifically for the json3 format
            json3_track = next((t for t in track_list if t.get("ext") == "json3"), None)
            if not json3_track or "url" not in json3_track:
                print("No JSON3 caption track available.")
                return []

            res = httpx.get(json3_track["url"])
            if res.status_code != 200:
                print(f"Failed to fetch caption data (status {res.status_code})")
                return []

            data = res.json()

            segments = []
            for event in data.get("events", []):
                if "segs" in event:
                    text = "".join(s.get("utf8", "") for s in event["segs"]).strip()
                    if text and text != "\n":
                        start = event.get("tStartMs", 0) / 1000.0
                        duration = event.get("dDurationMs", 0) / 1000.0
                        segments.append({"start": start, "duration": duration, "text": text})

            return segments
    except Exception as e:
        print(f"Error fetching transcript: {e}")
        return []
            
    

if __name__ == "__main__":
    url = input(">> ")
    print(f"Fetching transcript for: {url}")
    
    segments = get_transcript(url)
    print(f"\n Total segments fetched: {len(segments)}")
    
    print("\n Here are the first 3 segments with their timestamps:")
    for s in segments[:3]:
        print(f"  [{s['start']:.1f}s - {s['start'] + s['duration']:.1f}s]: {s['text']}")
