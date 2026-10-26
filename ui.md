# UI Design Specification & Context: YT-Playlist-RAG

## 1. Inspiration & Design Prompt

* **Inspiration Reference**: [https://lavender-negativ.vercel.app/](https://lavender-negativ.vercel.app/)
* **Target Application**: `apps/docs` (Documentation & Landing Page on port 3001)
* **Goal**: Build a landing page and documentation experience for `yt-playlist-rag` that mirrors the technical, modern aesthetic of `lavender-negativ` while reflecting actual domain features, API contracts, and architecture.

---

## 2. Project & Domain Context

**yt-playlist-rag** is an end-to-end Retrieval-Augmented Generation (RAG) system for YouTube playlists and long-form video lectures.

### Core Problems Solved
1. **Video Navigation Inefficiency**: Students and engineers spend hours seeking through 1-3 hour technical playlists.
2. **Hallucination in Video RAG**: Standard LLMs fabricate details or hallucinate video timecodes. YT-RAG uses a 3-tier guardrail system (pre-LLM cosine similarity cutoff, refusal prompting, and citation filtering) to guarantee answers link strictly to spoken material.
3. **Multi-Language & Hinglish Transcripts**: Technical tutorials often mix Hindi and English or use manual Hindi tracks (`hi-orig`). Using `yt-dlp` caption extraction with priority fallbacks, the system extracts transcripts regardless of whether auto-translate or creator subtitles are present.
4. **Instant Playback Jump**: Citations include YouTube deep links with a `-5s` lead-in offset so the video player starts right before the topic explanation begins.

### Monorepo Architecture
* **`apps/api` (FastAPI, Python 3.12+)**:
  * `/api/health`: Health status of Qdrant, FastEmbed, and LLM providers.
  * `/api/ingest`: Fetches transcripts via `yt-dlp`, chunks with timestamps, generates embeddings via FastEmbed (`BAAI/bge-small-en-v1.5`), and indexes into Qdrant vector database.
  * `/api/search`: Cosine similarity vector search over timestamped chunks.
  * `/api/chat`: Grounded RAG with strict citations and timestamp links.
* **`apps/web` (Next.js 16, Port 3000)**:
  * Interactive chat UI, YouTube embedded player with synchronized timecode seeking, and playlist ingestion progress bar.
* **`apps/docs` (Next.js 16, Port 3001)**:
  * Landing page, architecture documentation, API explorer, and configuration reference.

---

## 3. Design Aesthetics & Visual Identity

### Aesthetic Philosophy
* **Technical Blueprint Elegance**: High precision, subtle borders, registration marks, and monospace accents that convey developer-grade tooling.
* **Light Theme with Lavender Glow**: High-contrast white canvas (`#ffffff`), subtle gray framing (`#e5e7eb`), and lavender accents (`#7c3aed`, `#a78bfa`, `#c4b5fd`).
* **Micro-interactions & Motion**: Smooth CSS transitions, infinite vertical card ticker, and interactive code block tabs.

### Key Design Tokens

```css
:root {
  --bg: #ffffff;
  --fg: #0f0f0f;
  --muted: #6b7280;
  --border: #e5e7eb;
  --border-dashed: #d1d5db;

  /* Lavender Accents */
  --lavender:       #a78bfa;
  --lavender-light: #c4b5fd;
  --lavender-dark:  #7c3aed;
  --lavender-faint: rgba(167, 139, 250, 0.12);

  /* Functional Accents */
  --yt-red: #ef4444;
  --emerald: #10b981;
  --blue: #3b82f6;
  --amber: #f59e0b;
}
```

### Signature UI Components (Mirrored from Lavender-Negativ)
1. **Corner Registration Dots (`.corner-dot`)**: 8px square registration dots placed at corner intersections (`tl`, `tr`, `bl`, `br`) to provide an engineering blueprint feel.
2. **Diagonal Hatching Accent (`.hatch`)**: Subtle 45° repeating stripes highlighting key hero words (`lose`, etc.).
3. **Marquee Preview Window**: Browser mock header (macOS traffic lights) with two oppositely scrolling columns of video lecture cards (DSA, System Design, ML, Docker, Python).
4. **Interactive Code Switcher**: Interactive tabs for `/api/ingest`, `/api/search`, and `/api/chat` with syntax-colored JSON responses and copy-to-clipboard functionality.
5. **Bento Box Feature Grid**: 3-column structured grid highlighting caption support, vector search, grounded citations, timestamp links, and idempotent storage.

---

## 4. Documentation Structure (`apps/docs`)

| Section | Component / Content |
|---|---|
| **1. Header & Navigation** | Sticky header with lavender gradient border, branding, section links, and "Open App" direct link. |
| **2. Hero Section** | Live status badge, headline with hatched emphasis, subtitle, primary/secondary CTAs, and animated dual-column card marquee. |
| **3. Tech Stack Strip** | Horizontal pill scroll showcasing FastAPI, Qdrant, FastEmbed, Next.js, Gemini, Groq, Docker, and Turborepo. |
| **4. Feature Grid** | 6-card bento box with icons, titles, and technical specifications. |
| **5. How It Works** | 3-step timeline (Ingest → Vectorize → Chat) paired with a live interactive code preview. |
| **6. API Reference** | Method badges (`GET`, `POST`), endpoint paths, parameter tables, and request descriptions. |
| **7. Configuration** | Environment variables table and syntax-highlighted `.env` snippet. |
| **8. Footer** | Sitemap links, backend health status indicator, and copyright. |

---

## 5. Continued Improvements Checklist

- [x] Complete landing page layout in `apps/docs/app/page.tsx`
- [x] Integrate full lavender styling and CSS tokens in `apps/docs/app/globals.css`
- [x] Fix JSX template string syntax in code blocks using `dangerouslySetInnerHTML`
- [x] Add copy-to-clipboard button to all code preview blocks with active feedback
- [x] Wire up responsive mobile drawer navigation toggle
- [x] Add live API health check hook in the footer / header badge

---

## 6. Real App & Dashboard Architecture (`apps/web` on Port 3000)

The main application in `apps/web` has been structured into a full-featured study studio and vector management dashboard:

### 1. Header Navigation (`HeaderNav.tsx`)
* **Branding & Versioning**: `YT-RAG Studio v1.0` with YouTube red accent and gradient title.
* **Navigation Tabs**:
  * 📊 **Dashboard**: Metrics overview, video library cards, and ingestion hero.
  * 🎬 **Study Studio**: Split-view YouTube player with synchronized timestamp seeker and conversational Q&A.
  * 🔍 **Search Explorer**: Semantic vector similarity search with score sliders and chunk inspector.
  * ⚡ **Vector DB & Specs**: Live diagnostic status for Qdrant, FastEmbed ONNX, LLM keys, and disk cache.
* **Global Actions**: `+ Ingest URL` modal trigger, direct link to Docs (`:3001`), and real-time backend health badge.

### 2. Dashboard Overview (`DashboardView.tsx`)
* **4 Metric Stat Cards**:
  1. Total Indexed Videos
  2. Vector Chunks stored in Qdrant (`yt_transcripts`)
  3. Embedding Engine (FastEmbed 384d, Cosine similarity, CPU ONNX)
  4. Anti-Hallucination Guardrails (Cutoff ≥ 0.50, Refusal prompt, -5s lead-in)
* **Ingestion Station**: Instant URL ingestion banner with preset chips.
* **Lecture Video Library Grid**: Bento cards with YouTube thumbnails, chunk count badges, multi-language tags, and direct "Study in Studio" / "Vector Search" actions.
* **Quick Discovery Chips**: Example questions from indexed videos for quick testing.

### 3. Study Studio (`StudioView.tsx`)
* **YouTube Embedded Player**: Synchronized playback using the YouTube IFrame API with -5s lead-in notification.
* **Playlist Video Selector**: Instant switching between all indexed videos in the playlist.
* **Grounded Conversational Q&A (`ChatPanel.tsx`)**:
  * Zero-hallucination guardrail active badge.
  * Clickable timestamp citations (`[1] 14:32 (-5s lead-in)`) that seek the embedded player.
  * Cosine similarity match score indicator on every citation.

### 4. Semantic Search Explorer (`SearchExplorerView.tsx`)
* Direct vector similarity querying to `/api/search`.
* Filters by specific video or across all indexed videos.
* Sliders for minimum similarity score (`0.0` to `1.0`) and max chunks limit (`1` to `20`).
* Ranked result cards with match percentage, transcript excerpts, and "Jump in Studio" buttons.

### 5. Vector DB Diagnostics (`SystemHealthView.tsx`)
* Live connectivity verification for Qdrant (`localhost:6333`), FastEmbed model info, LLM API keys (Gemini / Groq), and `.transcripts_cache` persistence.

### 6. Quick Ingestion Modal (`IngestModal.tsx`)
* Clean modal accessible from anywhere with single video/playlist inputs, quick test presets, and advanced chunking configuration.

---

## 5. Hierarchical Two-Tier RAG for Large Playlists (300+ Videos)

### The Problem
Ingesting a 300-video YouTube course sequentially (fetching captions, chunking text, computing 384d FastEmbed embeddings, and indexing vectors) takes 7–10+ minutes over HTTP. This destroys UX, times out HTTP requests, and leaves users waiting.

### The Solution: Two-Tier Hierarchical Routing
1. **Tier 1 (Instant Registry & Title Indexing ~2 seconds)**:
   * When a playlist is submitted, `yt-dlp` flat extraction (`extract_flat: True`) extracts metadata for all 300 videos in ~2 seconds without downloading video content.
   * All 300 video titles are batch-embedded and indexed into Qdrant collection `yt_videos`.
   * Video 1 is immediately transcribed and ready for interactive playback in the Studio.
   * The user immediately receives an instant success confirmation and can explore the library.

2. **Tier 2 (Just-In-Time JIT Transcription on Demand)**:
   * **Targeted Video Query**: When a user queries a specific video, the system verifies if its transcript is already in `yt_transcripts`. If not, it fetches and indexes it JIT in ~1–2s.
   * **Cross-Playlist General Query**: When a user asks a general question without knowing which lecture covers it, Tier 1 semantic title routing identifies the top matching video lectures (`yt_videos`).
   * The backend dynamically JIT-transcribes the top matching video(s), indexes their chunks into `yt_transcripts`, and performs the vector search and grounded LLM generation.
   * Cached transcript files on disk (`.transcripts_cache/*.json`) guarantee sub-millisecond retrieval on future visits.

