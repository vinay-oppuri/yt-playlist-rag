"use client";

import React, { useState, useEffect } from "react";

interface HealthData {
  status: string;
  qdrant_target?: string;
  embedding_model?: string;
  vector_dimension?: number;
  collections?: string[];
  llm?: {
    configured_provider: string;
    has_gemini_key: boolean;
    has_groq_key: boolean;
  };
  error?: string;
}

interface SystemHealthViewProps {
  apiBaseUrl?: string;
}

export const SystemHealthView: React.FC<SystemHealthViewProps> = ({
  apiBaseUrl = "http://127.0.0.1:8000",
}) => {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastChecked, setLastChecked] = useState<string>("");

  const fetchHealth = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/health`);
      const data = await res.json();
      setHealth(data);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (err: any) {
      setHealth({
        status: "offline",
        error: "Failed to connect to http://127.0.0.1:8000/api/health",
      });
      setLastChecked(new Date().toLocaleTimeString());
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const isHealthy = health?.status === "healthy";

  return (
    <div style={styles.container}>
      {/* ── Top Status Banner ────────────────────────────────────── */}
      <div className="glass-panel" style={styles.statusBanner}>
        <div style={styles.bannerLeft}>
          <div
            style={{
              ...styles.statusPulseBox,
              background: isHealthy ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
              borderColor: isHealthy ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)",
            }}
          >
            <span className={`live-dot ${isHealthy ? "" : "danger"}`} style={{ width: "12px", height: "12px" }} />
          </div>
          <div>
            <div style={styles.statusTitleRow}>
              <h2 style={styles.statusTitle}>
                {isHealthy ? "All RAG Services Operational" : "Backend Service Degraded / Offline"}
              </h2>
              <span className={`badge ${isHealthy ? "badge-success" : "badge-yt"}`}>
                {health?.status?.toUpperCase() || "UNKNOWN"}
              </span>
            </div>
            <p style={styles.statusSubtitle}>
              Backend running at <code>{apiBaseUrl}</code> • Last pinged at {lastChecked || "just now"}
            </p>
          </div>
        </div>

        <button
          className="btn-secondary"
          onClick={fetchHealth}
          disabled={isLoading}
          style={{ whiteSpace: "nowrap" }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
          <span>{isLoading ? "Pinging..." : "Refresh Status"}</span>
        </button>
      </div>

      {/* ── Subsystems Grid ──────────────────────────────────────── */}
      <div style={styles.grid}>
        {/* Card 1: Qdrant Vector Database */}
        <div className="glass-panel" style={styles.card}>
          <div style={styles.cardHeader}>
            <div style={styles.cardIconBox}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <ellipse cx="12" cy="5" rx="9" ry="3" />
                <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
              </svg>
            </div>
            <div>
              <h3 style={styles.cardTitle}>Qdrant Vector Database</h3>
              <p style={styles.cardSubtitle}>HNSW High-Dimensional Vector Storage</p>
            </div>
          </div>

          <div style={styles.specList}>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Connection Target</span>
              <span style={styles.specVal}>{health?.qdrant_target || "http://localhost:6333"}</span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Distance Metric</span>
              <span style={styles.specVal}>Cosine Similarity</span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Vector Dimension</span>
              <span style={styles.specVal}>{health?.vector_dimension || 384} dims</span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Active Collections</span>
              <span style={styles.specVal}>
                {health?.collections && health.collections.length > 0
                  ? health.collections.join(", ")
                  : "yt_transcripts"}
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: FastEmbed ONNX Pipeline */}
        <div className="glass-panel" style={styles.card}>
          <div style={styles.cardHeader}>
            <div style={{ ...styles.cardIconBox, color: "#34d399", background: "rgba(52, 211, 153, 0.12)" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </div>
            <div>
              <h3 style={styles.cardTitle}>FastEmbed ONNX Engine</h3>
              <p style={styles.cardSubtitle}>Local CPU Embedding Pipeline</p>
            </div>
          </div>

          <div style={styles.specList}>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Model Architecture</span>
              <span style={styles.specVal}>{health?.embedding_model || "BAAI/bge-small-en-v1.5"}</span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Hardware Requirement</span>
              <span style={styles.specVal}>Zero GPU (Optimized CPU ONNX)</span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Latency</span>
              <span style={styles.specVal}>~12ms per 180-word chunk</span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Deduplication</span>
              <span style={styles.specVal}>Deterministic UUID from video+timestamp</span>
            </div>
          </div>
        </div>

        {/* Card 3: LLM & Anti-Hallucination Guardrails */}
        <div className="glass-panel" style={styles.card}>
          <div style={styles.cardHeader}>
            <div style={{ ...styles.cardIconBox, color: "#f472b6", background: "rgba(244, 114, 182, 0.12)" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2a10 10 0 1 0 10 10H12V2z" />
              </svg>
            </div>
            <div>
              <h3 style={styles.cardTitle}>LLM & Anti-Hallucination Guardrails</h3>
              <p style={styles.cardSubtitle}>Prompt Grounding & Refusal Engine</p>
            </div>
          </div>

          <div style={styles.specList}>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Configured Provider</span>
              <span style={styles.specVal}>{health?.llm?.configured_provider || "gemini"}</span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Google Gemini API Key</span>
              <span style={styles.specVal}>
                {health?.llm?.has_gemini_key ? "✅ Present & Configured" : "❌ Missing in .env"}
              </span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Groq API Key (Llama 3.3)</span>
              <span style={styles.specVal}>
                {health?.llm?.has_groq_key ? "✅ Present & Configured" : "❌ Missing in .env"}
              </span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Pre-LLM Score Cutoff</span>
              <span style={styles.specVal}>0.50 (Rejects irrelevant queries without invoking LLM)</span>
            </div>
          </div>
        </div>

        {/* Card 4: Multi-Language Caption Pipeline */}
        <div className="glass-panel" style={styles.card}>
          <div style={styles.cardHeader}>
            <div style={{ ...styles.cardIconBox, color: "#fbbf24", background: "rgba(251, 191, 36, 0.12)" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
            </div>
            <div>
              <h3 style={styles.cardTitle}>Multi-Language & Disk Cache</h3>
              <p style={styles.cardSubtitle}>yt-dlp Caption Priority & Persistence</p>
            </div>
          </div>

          <div style={styles.specList}>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Language Priority</span>
              <span style={styles.specVal}>hi-orig → en-orig → hi → en → Indian regional → ASR</span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Hinglish Support</span>
              <span style={styles.specVal}>Automatic manual Hindi track selection</span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Atomic Disk Cache</span>
              <span style={styles.specVal}><code>.transcripts_cache/*.json</code></span>
            </div>
            <div style={styles.specRow}>
              <span style={styles.specKey}>Timestamp Lead-in Offset</span>
              <span style={styles.specVal}>-5 seconds lead-in on all generated links</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
    paddingBottom: "40px",
  },
  statusBanner: {
    padding: "24px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "16px",
  },
  bannerLeft: {
    display: "flex",
    alignItems: "center",
    gap: "16px",
  },
  statusPulseBox: {
    width: "44px",
    height: "44px",
    borderRadius: "12px",
    border: "1px solid",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  statusTitleRow: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    marginBottom: "4px",
  },
  statusTitle: {
    fontSize: "1.15rem",
    fontWeight: 700,
    color: "var(--text-main)",
  },
  statusSubtitle: {
    fontSize: "0.8rem",
    color: "var(--text-muted)",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))",
    gap: "20px",
  },
  card: {
    padding: "24px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  cardHeader: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
    paddingBottom: "14px",
    borderBottom: "1px solid var(--border-subtle)",
  },
  cardIconBox: {
    width: "40px",
    height: "40px",
    borderRadius: "10px",
    background: "rgba(99, 102, 241, 0.12)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#818cf8",
  },
  cardTitle: {
    fontSize: "0.95rem",
    fontWeight: 700,
    color: "var(--text-main)",
  },
  cardSubtitle: {
    fontSize: "0.75rem",
    color: "var(--text-muted)",
  },
  specList: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  specRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    fontSize: "0.82rem",
    gap: "12px",
  },
  specKey: {
    color: "var(--text-dim)",
    fontWeight: 500,
  },
  specVal: {
    color: "var(--text-main)",
    fontWeight: 600,
    textAlign: "right",
    fontFamily: "var(--font-mono)",
    fontSize: "0.78rem",
  },
};
