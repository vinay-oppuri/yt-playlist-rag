"use client";

/* =========================================================
   YT-RAG Landing Page — inspired by lavender-negativ.vercel.app
   Sections:
     1. Sticky Nav
     2. Hero (left: copy + CTAs, right: chat preview)
     3. Stack scroll strip
     4. Features (3-col bento)
     5. How It Works (steps + live code)
     6. API Reference
     7. Configuration (.env)
     8. Footer
   ========================================================= */

import React, { useState, useEffect } from "react";

// ─── Tiny reusable helpers ────────────────────────────────────────────────────

const CornerDots = () => (
  <>
    <span className="corner-dot tl" />
    <span className="corner-dot tr" />
    <span className="corner-dot bl" />
    <span className="corner-dot br" />
  </>
);

// ─── Data ─────────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: "🎬",
    title: "Multi-Language Captions",
    desc: "Automatically selects the best caption track — hi-orig, en-orig, or any Indian language. Never gets stuck on a translated track.",
  },
  {
    icon: "🔍",
    title: "Semantic Vector Search",
    desc: "FastEmbed (ONNX, zero GPU) embeds chunks into Qdrant. Cosine similarity search returns the most relevant 60-second window.",
  },
  {
    icon: "🤖",
    title: "Grounded AI Answers",
    desc: "3-tier hallucination guardrails: pre-LLM score cutoff, model refusal prompting, and citation filtering — only shows timestamps actually cited.",
  },
  {
    icon: "⏱️",
    title: "Timestamp Deep Links",
    desc: "Every citation includes a YouTube URL with -5s lead-in offset, so the player lands slightly before the explanation begins.",
  },
  {
    icon: "⚡",
    title: "Atomic Transcript Cache",
    desc: "Transcripts are saved atomically to disk. Re-indexing with new chunk sizes or embedding models takes seconds, not minutes.",
  },
  {
    icon: "🛡️",
    title: "Idempotent Ingestion",
    desc: "Chunk IDs are deterministic UUIDs derived from video_id + timestamp. Running ingest twice never creates duplicates.",
  },
];

const STACK = [
  { label: "FastAPI", icon: "⚡" },
  { label: "Qdrant", icon: "🔷" },
  { label: "FastEmbed", icon: "🧠" },
  { label: "yt-dlp", icon: "📥" },
  { label: "Next.js 16", icon: "▲" },
  { label: "Gemini / Groq", icon: "🤖" },
  { label: "Python 3.12+", icon: "🐍" },
  { label: "Turborepo", icon: "🚀" },
  { label: "Docker", icon: "🐳" },
  { label: "TypeScript", icon: "🔵" },
  { label: "Pydantic", icon: "✅" },
  { label: "UV", icon: "📦" },
];

const API_ENDPOINTS = [
  {
    method: "GET",
    path: "/api/health",
    desc: "Check Qdrant connection, embedding model, collections, and LLM key status.",
    params: [],
  },
  {
    method: "POST",
    path: "/api/ingest",
    desc: "Ingest a YouTube video or full playlist. Fetches captions, chunks with timestamps, embeds, and stores in Qdrant.",
    params: [
      { name: "url", type: "string", desc: "YouTube video or playlist URL" },
      { name: "collection_name", type: "string", desc: "Qdrant collection (default: yt_transcripts)" },
      { name: "target_words", type: "int", desc: "Words per chunk (default: 180)" },
    ],
  },
  {
    method: "POST",
    path: "/api/search",
    desc: "Run semantic vector search across ingested transcripts. Returns chunks with scores and timestamp links.",
    params: [
      { name: "query", type: "string", desc: "Your search question" },
      { name: "video_id", type: "string?", desc: "Filter to a specific video ID" },
      { name: "score_threshold", type: "float?", desc: "Min cosine similarity (e.g. 0.35)" },
    ],
  },
  {
    method: "POST",
    path: "/api/chat",
    desc: "Full grounded RAG — retrieves chunks, runs 3-tier guardrails, calls LLM, and returns cited timestamps.",
    params: [
      { name: "question", type: "string", desc: "Natural language question" },
      { name: "top_k", type: "int", desc: "Chunks to retrieve (default: 5)" },
      { name: "min_score", type: "float", desc: "Score cutoff before LLM (default: 0.50)" },
    ],
  },
];

// Cards for the animated scrolling columns
const CARDS_LEFT = [
  { color: "card-purple", icon: "🎓", title: "DSA Lecture", body: "What is the time complexity of binary search?" },
  { color: "card-blue", icon: "📐", title: "System Design", body: "Explain consistent hashing in distributed systems." },
  { color: "card-emerald", icon: "🤖", title: "AI/ML Course", body: "How does attention mechanism work in transformers?" },
  { color: "card-amber", icon: "🔥", title: "React Tutorial", body: "What is the difference between useMemo and useCallback?" },
  { color: "card-rose", icon: "🏗️", title: "Backend Series", body: "How do I implement rate limiting in FastAPI?" },
  { color: "card-purple", icon: "📊", title: "Stats Lecture", body: "When should I use a t-test vs z-test?" },
];

const CARDS_RIGHT = [
  { color: "card-emerald", icon: "🐍", title: "Python Course", body: "What are Python generators and when to use them?" },
  { color: "card-rose", icon: "🌐", title: "Networking", body: "Explain the TCP 3-way handshake step by step." },
  { color: "card-blue", icon: "📦", title: "Docker Series", body: "What is the difference between CMD and ENTRYPOINT?" },
  { color: "card-amber", icon: "🔐", title: "Security Basics", body: "How does JWT authentication work?" },
  { color: "card-purple", icon: "🎯", title: "Algorithms", body: "Walk me through Dijkstra's shortest path algorithm." },
  { color: "card-emerald", icon: "🧠", title: "ML Interview", body: "What is the bias-variance tradeoff?" },
];

const CODE_SNIPPETS = {
  ingest: `{
  "url": "https://youtube.com/playlist?list=...",
  "collection_name": "yt_transcripts",
  "target_words": 180,
  "overlap_words": 35
}`,
  search: `{
  "query": "how does quicksort work",
  "video_id": "dQw4w9WgXcQ",
  "limit": 5,
  "score_threshold": 0.35
}`,
  chat: `{
  "question": "memoization vs tabulation?",
  "top_k": 5,
  "min_score": 0.50
}`,
  env: `# LLM Provider: 'groq' or 'gemini'
LLM_PROVIDER=gemini

# Google Gemini — aistudio.google.com/apikey
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.0-flash

# Groq — console.groq.com/keys
GROQ_API_KEY=your-key-here
GROQ_MODEL=llama-3.3-70b-versatile

# Qdrant (docker run -p 6333:6333 qdrant/qdrant)
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=yt_transcripts

# Score cutoff before calling LLM (0.0 – 1.0)
MIN_SIMILARITY_SCORE=0.50

# Production CORS origin
CORS_ORIGIN=http://localhost:3000`,
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function Home() {
  const [activeCode, setActiveCode] = useState<"ingest" | "search" | "chat">("ingest");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/health")
      .then((res) => {
        if (res.ok) setApiStatus("online");
        else setApiStatus("offline");
      })
      .catch(() => setApiStatus("offline"));
  }, []);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => {
      setCopiedId((prev) => (prev === id ? null : prev));
    }, 2000);
  };

  return (
    <div style={{ background: "#fff", minHeight: "100vh" }}>

      {/* ── 1. Sticky Nav ─────────────────────────────────────────── */}
      <nav className="nav">
        <div className="container">
          <div className="nav-inner grad-bg" style={{ position: "relative" }}>
            <CornerDots />
            <span className="nav-logo grad-text">YT-RAG</span>
            <div className="nav-links" style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
              <a href="#features">Features</a>
              <a href="#how-it-works">How it works</a>
              <a href="#api">API</a>
              <a href="#config">Config</a>
              <a
                href="http://localhost:3000"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary"
                style={{ marginLeft: "0.75rem", fontSize: "0.8rem", padding: "0.4rem 1rem" }}
              >
                Open App ↗
              </a>
            </div>
            <button
              className="nav-mobile-btn"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle Navigation Menu"
            >
              {mobileMenuOpen ? "✕" : "☰"}
            </button>
          </div>
          {mobileMenuOpen && (
            <div className="nav-mobile-drawer">
              <a href="#features" onClick={() => setMobileMenuOpen(false)}>Features</a>
              <a href="#how-it-works" onClick={() => setMobileMenuOpen(false)}>How it works</a>
              <a href="#api" onClick={() => setMobileMenuOpen(false)}>API</a>
              <a href="#config" onClick={() => setMobileMenuOpen(false)}>Config</a>
              <a
                href="http://localhost:3000"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary"
                style={{ justifyContent: "center", marginTop: "0.5rem" }}
                onClick={() => setMobileMenuOpen(false)}
              >
                Open App ↗
              </a>
            </div>
          )}
        </div>
      </nav>

      {/* ── 2. Hero ───────────────────────────────────────────────── */}
      <section className="hero-section" id="home">
        <div className="container">
          <div className="hero-inner" style={{ position: "relative" }}>
            <CornerDots />

            {/* Left: Copy */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div className="hero-badge">
                <span className="badge-dot">
                  <span />
                  <span className="ping" />
                </span>
                v1.0 — Multi-language support live
              </div>

              <h1 className="hero-h1">
                Never{" "}
                <span className="hero-keyword">
                  <span className="hatch" />
                  <span>lose</span>
                  <CornerDots />
                </span>{" "}
                a lecture<br />moment again
              </h1>

              <p className="hero-sub">
                Paste any YouTube playlist URL.<br />
                Ask questions. Get answers grounded<br />
                in exact timestamps — not hallucinations.
              </p>

              <div className="hero-ctas">
                <a href="#how-it-works" className="btn-primary">
                  Get started
                </a>
                <a href="#api" className="btn-outline">
                  API reference →
                </a>
              </div>
            </div>

            {/* Right: Animated chat preview */}
            <div className="hero-preview">
              <CornerDots />
              <div className="preview-window">
                <div className="preview-window-inner">
                  <div className="preview-titlebar">
                    <span className="dot-red" />
                    <span className="dot-yellow" />
                    <span className="dot-green" />
                    <span style={{ flex: 1, textAlign: "center", fontSize: "0.65rem", fontFamily: "monospace", color: "#9ca3af" }}>
                      YT-RAG · Chat
                    </span>
                  </div>

                  {/* Scrolling card columns */}
                  <div className="preview-body" style={{ overflow: "hidden", padding: "0.75rem", flex: 1 }}>
                    <div className="card-columns">
                      {/* Left column scrolls up */}
                      <div className="card-col col-up">
                        {[...CARDS_LEFT, ...CARDS_LEFT].map((c, i) => (
                          <div key={i} className={`vid-card ${c.color}`}>
                            <div className="vid-card-header">
                              <div className="vid-card-icon" style={{ background: "rgba(167,139,250,0.1)" }}>
                                {c.icon}
                              </div>
                              <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "#374151" }}>{c.title}</div>
                            </div>
                            <div className="vid-card-body">
                              <p>{c.body}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                      {/* Right column scrolls down */}
                      <div className="card-col col-down">
                        {[...CARDS_RIGHT, ...CARDS_RIGHT].map((c, i) => (
                          <div key={i} className={`vid-card ${c.color}`}>
                            <div className="vid-card-header">
                              <div className="vid-card-icon" style={{ background: "rgba(167,139,250,0.1)" }}>
                                {c.icon}
                              </div>
                              <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "#374151" }}>{c.title}</div>
                            </div>
                            <div className="vid-card-body">
                              <p>{c.body}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Input bar */}
                  <div className="preview-input">
                    <span>Ask anything about your playlist...</span>
                    <div className="send-btn">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                        <path d="M22 2L11 13M22 2L15 22 11 13 2 9l20-7z" />
                      </svg>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── 3. Stack Pills ────────────────────────────────────────── */}
      <section className="stack-section" style={{ borderBottom: "1px solid #e5e7eb", overflow: "hidden" }}>
        <div className="stack-scroll">
          {[...STACK, ...STACK].map((s, i) => (
            <span key={i} className="stack-pill">
              <span>{s.icon}</span>
              {s.label}
            </span>
          ))}
        </div>
      </section>

      {/* ── 4. Features ───────────────────────────────────────────── */}
      <section className="features-section" id="features">
        <div className="features-inner">
          <CornerDots />
          <div style={{ padding: "2.5rem 2rem 1.5rem", borderBottom: "1px solid #e5e7eb" }}
               className="grad-bg">
            <CornerDots />
            <h2 className="section-heading">Everything you need</h2>
            <p className="section-subheading" style={{ marginBottom: 0 }}>
              Built on production-grade patterns from real RAG deployments.
            </p>
          </div>
          <div className="features-grid">
            {FEATURES.map((f) => (
              <div key={f.title} className="feature-card">
                <CornerDots />
                <div className="feature-icon">{f.icon}</div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 5. How it Works ───────────────────────────────────────── */}
      <section className="how-section" id="how-it-works">
        <div className="container">
          <div style={{ borderLeft: "1px solid #e5e7eb", borderRight: "1px solid #e5e7eb", position: "relative" }}>
            <CornerDots />
            <div className="how-inner">
              {/* Steps */}
              <div className="how-steps">
                <div style={{ marginBottom: "0.5rem" }}>
                  <h2 className="section-heading">How it works</h2>
                  <p className="section-subheading" style={{ marginBottom: 0 }}>
                    From URL to grounded answer in 4 steps.
                  </p>
                </div>
                {[
                  { n: "1", title: "Paste a YouTube URL", body: "Single video or full playlist — both work. yt-dlp extracts the video list without downloading media." },
                  { n: "2", title: "Transcripts are fetched & cached", body: "Captions are pulled directly (hi-orig, en-orig priority). Atomic JSON cache means re-indexing is instant." },
                  { n: "3", title: "Semantic chunks are stored in Qdrant", body: "60-75s time-window chunks with -5s lead-in, title prefixing, and repetition filtering. Embedded with FastEmbed ONNX." },
                  { n: "4", title: "Ask questions, get grounded answers", body: "Pre-LLM score cutoff → LLM with strict system prompt → citation filtering. Only cited timestamps are shown." },
                ].map((s) => (
                  <div key={s.n} className="step">
                    <span className="step-num">{s.n}</span>
                    <div>
                      <h3>{s.title}</h3>
                      <p>{s.body}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Code tabs */}
              <div className="how-code">
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  {(["ingest", "search", "chat"] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveCode(tab)}
                      className={activeCode === tab ? "btn-primary" : "btn-outline"}
                      style={{ fontSize: "0.75rem", padding: "0.3rem 0.9rem" }}
                    >
                      /api/{tab}
                    </button>
                  ))}
                </div>

                {activeCode === "ingest" && (
                  <div className="code-block">
                    <div className="code-header">
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span className="code-method post">POST</span>
                        <span className="code-label">/api/ingest</span>
                      </div>
                      <button
                        onClick={() => handleCopy("ingest", CODE_SNIPPETS.ingest)}
                        className={`code-copy-btn ${copiedId === "ingest" ? "copied" : ""}`}
                      >
                        {copiedId === "ingest" ? "✓ Copied" : "Copy"}
                      </button>
                    </div>
                    <pre className="code-body" dangerouslySetInnerHTML={{ __html: `{
  <span class="code-key">"url"</span>: <span class="code-str">"https://youtube.com/playlist?list=..."</span>,
  <span class="code-key">"collection_name"</span>: <span class="code-str">"yt_transcripts"</span>,
  <span class="code-key">"target_words"</span>: <span class="code-num">180</span>,
  <span class="code-key">"overlap_words"</span>: <span class="code-num">35</span>
}

<span class="code-comment">// Response</span>
{
  <span class="code-key">"success"</span>: <span class="code-num">true</span>,
  <span class="code-key">"videos_indexed"</span>: <span class="code-num">12</span>,
  <span class="code-key">"total_chunks_stored"</span>: <span class="code-num">847</span>
}` }} />
                  </div>
                )}

                {activeCode === "search" && (
                  <div className="code-block">
                    <div className="code-header">
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span className="code-method post">POST</span>
                        <span className="code-label">/api/search</span>
                      </div>
                      <button
                        onClick={() => handleCopy("search", CODE_SNIPPETS.search)}
                        className={`code-copy-btn ${copiedId === "search" ? "copied" : ""}`}
                      >
                        {copiedId === "search" ? "✓ Copied" : "Copy"}
                      </button>
                    </div>
                    <pre className="code-body" dangerouslySetInnerHTML={{ __html: `{
  <span class="code-key">"query"</span>: <span class="code-str">"how does quicksort work"</span>,
  <span class="code-key">"video_id"</span>: <span class="code-str">"dQw4w9WgXcQ"</span>,
  <span class="code-key">"limit"</span>: <span class="code-num">5</span>,
  <span class="code-key">"score_threshold"</span>: <span class="code-num">0.35</span>
}

<span class="code-comment">// Response: top-k chunks with timestamps</span>
{
  <span class="code-key">"count"</span>: <span class="code-num">3</span>,
  <span class="code-key">"results"</span>: [
    { <span class="code-key">"score"</span>: <span class="code-num">0.812</span>, <span class="code-key">"timestamp"</span>: <span class="code-str">"14:32"</span>, ... }
  ]
}` }} />
                  </div>
                )}

                {activeCode === "chat" && (
                  <div className="code-block">
                    <div className="code-header">
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span className="code-method post">POST</span>
                        <span className="code-label">/api/chat</span>
                      </div>
                      <button
                        onClick={() => handleCopy("chat", CODE_SNIPPETS.chat)}
                        className={`code-copy-btn ${copiedId === "chat" ? "copied" : ""}`}
                      >
                        {copiedId === "chat" ? "✓ Copied" : "Copy"}
                      </button>
                    </div>
                    <pre className="code-body" dangerouslySetInnerHTML={{ __html: `{
  <span class="code-key">"question"</span>: <span class="code-str">"memoization vs tabulation?"</span>,
  <span class="code-key">"top_k"</span>: <span class="code-num">5</span>,
  <span class="code-key">"min_score"</span>: <span class="code-num">0.50</span>
}

<span class="code-comment">// Grounded answer with cited timestamps</span>
{
  <span class="code-key">"answer"</span>: <span class="code-str">"Memoization stores [1]..."</span>,
  <span class="code-key">"citations"</span>: [
    { <span class="code-key">"citation_index"</span>: <span class="code-num">1</span>,
      <span class="code-key">"timestamp"</span>: <span class="code-str">"12:05"</span>,
      <span class="code-key">"video_url"</span>: <span class="code-str">"...&t=720s"</span> }
  ],
}` }} />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── 6. API Reference ──────────────────────────────────────── */}
      <section className="api-section" id="api">
        <div className="api-inner" style={{ position: "relative" }}>
          <CornerDots />
          <h2 className="section-heading">API Reference</h2>
          <p className="section-subheading">
            FastAPI backend running at <code style={{ fontFamily: "monospace", fontSize: "0.8em", background: "#f3f4f6", padding: "1px 6px", borderRadius: 4 }}>http://127.0.0.1:8000</code>.
            Interactive docs at <code style={{ fontFamily: "monospace", fontSize: "0.8em", background: "#f3f4f6", padding: "1px 6px", borderRadius: 4 }}>/docs</code>.
          </p>
          <div className="api-grid">
            {API_ENDPOINTS.map((ep) => (
              <div key={ep.path} className="api-card">
                <div className="api-card-header">
                  <span className={`method-badge ${ep.method.toLowerCase()}`}>{ep.method}</span>
                  <span className="api-path">{ep.path}</span>
                </div>
                <div className="api-card-body">
                  <p>{ep.desc}</p>
                  {ep.params.length > 0 && (
                    <div className="api-params">
                      {ep.params.map((p) => (
                        <div key={p.name} className="api-param">
                          <span className="param-name">{p.name}</span>
                          <span className="param-type">{p.type}</span>
                          <span className="param-desc">— {p.desc}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 7. Configuration ──────────────────────────────────────── */}
      <section className="config-section" id="config">
        <div className="config-inner" style={{ position: "relative" }}>
          <CornerDots />
          <div className="config-desc">
            <h2>Configuration</h2>
            <p style={{ marginBottom: "1rem" }}>
              All settings live in <code style={{ fontFamily: "monospace", fontSize: "0.85em" }}>apps/api/.env</code>.
              Copy from <code style={{ fontFamily: "monospace", fontSize: "0.85em" }}>.env.example</code> and fill in your API keys.
            </p>
            {[
              { key: "LLM_PROVIDER", val: "gemini | groq", desc: "Which LLM to use" },
              { key: "GEMINI_API_KEY", val: "your-key", desc: "From aistudio.google.com" },
              { key: "GROQ_API_KEY", val: "your-key", desc: "From console.groq.com" },
              { key: "QDRANT_URL", val: "http://localhost:6333", desc: "Docker Qdrant" },
              { key: "MIN_SIMILARITY_SCORE", val: "0.50", desc: "Pre-LLM cutoff threshold" },
              { key: "CORS_ORIGIN", val: "https://your-app.vercel.app", desc: "Production domain" },
            ].map((row) => (
              <div key={row.key} style={{ display: "flex", gap: "0.5rem", alignItems: "baseline", marginBottom: "0.4rem", fontFamily: "monospace", fontSize: "0.78rem" }}>
                <span style={{ color: "#7c3aed", fontWeight: 600, minWidth: "200px" }}>{row.key}</span>
                <span style={{ color: "#059669" }}>{row.val}</span>
                <span style={{ color: "#9ca3af" }}>— {row.desc}</span>
              </div>
            ))}
          </div>

          <div className="code-block" style={{ alignSelf: "stretch" }}>
            <div className="code-header">
              <span className="code-label">apps/api/.env</span>
              <button
                onClick={() => handleCopy("env", CODE_SNIPPETS.env)}
                className={`code-copy-btn ${copiedId === "env" ? "copied" : ""}`}
              >
                {copiedId === "env" ? "✓ Copied" : "Copy"}
              </button>
            </div>
            <pre className="code-body" style={{ fontSize: "0.72rem" }} dangerouslySetInnerHTML={{ __html: `<span class="code-comment"># LLM Provider: 'groq' or 'gemini'</span>
<span class="code-key">LLM_PROVIDER</span>=<span class="code-str">gemini</span>

<span class="code-comment"># Google Gemini — aistudio.google.com/apikey</span>
<span class="code-key">GEMINI_API_KEY</span>=<span class="code-str">your-key-here</span>
<span class="code-key">GEMINI_MODEL</span>=<span class="code-str">gemini-2.0-flash</span>

<span class="code-comment"># Groq — console.groq.com/keys</span>
<span class="code-key">GROQ_API_KEY</span>=<span class="code-str">your-key-here</span>
<span class="code-key">GROQ_MODEL</span>=<span class="code-str">llama-3.3-70b-versatile</span>

<span class="code-comment"># Qdrant (docker run -p 6333:6333 qdrant/qdrant)</span>
<span class="code-key">QDRANT_URL</span>=<span class="code-str">http://localhost:6333</span>
<span class="code-key">QDRANT_COLLECTION</span>=<span class="code-str">yt_transcripts</span>

<span class="code-comment"># Score cutoff before calling LLM (0.0 – 1.0)</span>
<span class="code-key">MIN_SIMILARITY_SCORE</span>=<span class="code-num">0.50</span>

<span class="code-comment"># Production CORS origin</span>
<span class="code-key">CORS_ORIGIN</span>=` }} />
          </div>
        </div>
      </section>

      {/* ── 8. Footer ─────────────────────────────────────────────── */}
      <footer className="footer">
        <div className="footer-inner">
          <span className="footer-logo grad-text">YT-RAG</span>
          <div className="footer-links">
            <a href="#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <a href="#api">API</a>
            <a href="#config">Config</a>
            <a href="http://localhost:3000" target="_blank" rel="noopener noreferrer">Open App ↗</a>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px", alignItems: "flex-end" }}>
            <span className={`status-dot ${apiStatus}`}>
              {apiStatus === "online"
                ? "API online (port 8000)"
                : apiStatus === "checking"
                ? "Checking API..."
                : "API offline"}
            </span>
            <span className="footer-copy">© 2026 YT-RAG. Ask smarter.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
