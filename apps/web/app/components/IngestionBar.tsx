"use client";

import React, { useState } from "react";

export interface IngestedVideo {
  video_id: string;
  title: string;
  chunks: number;
  status: string;
}

interface IngestionBarProps {
  apiBaseUrl?: string;
  onIngestionSuccess?: (videos: IngestedVideo[]) => void;
  onSelectVideo?: (videoId: string, title: string) => void;
}

export const IngestionBar: React.FC<IngestionBarProps> = ({
  apiBaseUrl = "http://127.0.0.1:8000",
  onIngestionSuccess,
  onSelectVideo,
}) => {
  const [url, setUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [resultMsg, setResultMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleIngest = async (targetUrl?: string) => {
    const urlToIngest = targetUrl || url;
    if (!urlToIngest.trim()) return;

    setIsLoading(true);
    setResultMsg(null);

    try {
      const response = await fetch(`${apiBaseUrl}/api/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: urlToIngest.trim(),
          collection_name: "yt_transcripts",
          target_words: 180,
          overlap_words: 35,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: "Ingestion failed" }));
        throw new Error(errData.detail || `Server error (${response.status})`);
      }

      const data = await response.json();
      const isHierarchical = data.mode === "hierarchical";
      setResultMsg({
        type: "success",
        text: isHierarchical
          ? `⚡ Registered all ${data.videos_total} playlist videos instantly! (${data.total_chunks_stored} chunks ready). Remaining lecture transcripts index on-demand.`
          : `Indexed ${data.videos_indexed} of ${data.videos_total} video(s) • ${data.total_chunks_stored} vector embeddings stored.`,
      });

      if (onIngestionSuccess && Array.isArray(data.details)) {
        onIngestionSuccess(data.details);
        if (data.details.length > 0 && onSelectVideo) {
          const firstSuccess = data.details.find((d: any) => d.status === "success") || data.details[0];
          onSelectVideo(firstSuccess.video_id, firstSuccess.title);
        }
      }
    } catch (err: any) {
      setResultMsg({
        type: "error",
        text: err.message || "Failed to connect to backend at http://127.0.0.1:8000. Ensure FastAPI is running.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <header style={styles.header}>
      <div style={styles.topRow}>
        <div style={styles.brand}>
          <div style={styles.logoIcon}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17" fill="var(--accent-yt)" stroke="none" />
              <polygon points="10 15 15 12 10 9" fill="#ffffff" />
            </svg>
          </div>
          <div>
            <h1 style={styles.brandTitle}>YT Lecture RAG</h1>
            <p style={styles.brandSubtitle}>Timestamp-grounded retrieval assistant</p>
          </div>
        </div>

        <div style={styles.statusBadge}>
          <span className="live-dot" />
          <span>FastAPI + Qdrant + FastEmbed</span>
        </div>
      </div>

      <div style={styles.inputContainer}>
        <div style={styles.inputWrapper}>
          <svg style={styles.searchIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            id="youtube-url-input"
            type="text"
            style={styles.input}
            placeholder="Paste YouTube video or playlist URL (e.g. https://www.youtube.com/playlist?list=...)"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleIngest()}
          />
        </div>

        <button
          id="ingest-button"
          style={{
            ...styles.button,
            opacity: isLoading ? 0.7 : 1,
          }}
          disabled={isLoading}
          onClick={() => handleIngest()}
        >
          {isLoading ? (
            <>
              <div style={styles.spinner} />
              <span>Transcribing & Indexing...</span>
            </>
          ) : (
            <>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <span>Ingest Playlist</span>
            </>
          )}
        </button>
      </div>

      <div style={styles.quickSamples}>
        <span style={styles.quickLabel}>Try indexed video:</span>
        <button
          style={styles.sampleChip}
          onClick={() => {
            const sample = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";
            setUrl(sample);
            if (onSelectVideo) onSelectVideo("dQw4w9WgXcQ", "Rick Astley - Never Gonna Give You Up");
          }}
        >
          Rick Astley Demo
        </button>
        <button
          style={styles.sampleChip}
          onClick={() => {
            const sample = "https://www.youtube.com/watch?v=47YClVMlthI";
            setUrl(sample);
            if (onSelectVideo) onSelectVideo("47YClVMlthI", "Justin Bieber - Confident");
          }}
        >
          Confident Demo
        </button>
      </div>

      {resultMsg && (
        <div
          style={{
            ...styles.feedbackAlert,
            ...(resultMsg.type === "success" ? styles.successAlert : styles.errorAlert),
          }}
        >
          <span>{resultMsg.type === "success" ? "✓" : "⚠"}</span>
          <span>{resultMsg.text}</span>
        </div>
      )}
    </header>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  header: {
    background: "var(--bg-surface)",
    borderBottom: "1px solid var(--border-subtle)",
    padding: "20px 28px",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  topRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "12px",
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  logoIcon: {
    width: "36px",
    height: "36px",
    borderRadius: "var(--radius-md)",
    background: "rgba(255, 42, 42, 0.12)",
    border: "1px solid rgba(255, 42, 42, 0.25)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  brandTitle: {
    fontSize: "1.25rem",
    fontWeight: 700,
    color: "#fff",
    letterSpacing: "-0.02em",
  },
  brandSubtitle: {
    fontSize: "0.78rem",
    color: "var(--text-muted)",
  },
  statusBadge: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "0.76rem",
    color: "var(--text-muted)",
    padding: "6px 12px",
    borderRadius: "var(--radius-full)",
    background: "rgba(255, 255, 255, 0.04)",
    border: "1px solid var(--border-subtle)",
  },
  inputContainer: {
    display: "flex",
    gap: "12px",
    flexWrap: "wrap",
  },
  inputWrapper: {
    position: "relative",
    flex: 1,
    minWidth: "280px",
  },
  searchIcon: {
    position: "absolute",
    left: "14px",
    top: "50%",
    transform: "translateY(-50%)",
    color: "var(--text-dim)",
  },
  input: {
    width: "100%",
    padding: "12px 16px 12px 40px",
    background: "var(--bg-deep)",
    border: "1px solid var(--border-subtle)",
    borderRadius: "var(--radius-md)",
    color: "var(--text-main)",
    fontSize: "0.9rem",
    outline: "none",
    transition: "border-color 0.2s, box-shadow 0.2s",
  },
  button: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "12px 20px",
    background: "linear-gradient(135deg, var(--primary) 0%, var(--primary-hover) 100%)",
    color: "#fff",
    borderRadius: "var(--radius-md)",
    fontWeight: 600,
    fontSize: "0.88rem",
    boxShadow: "0 4px 14px var(--primary-glow)",
    transition: "transform 0.15s, box-shadow 0.15s",
  },
  spinner: {
    width: "14px",
    height: "14px",
    border: "2px solid rgba(255, 255, 255, 0.3)",
    borderTopColor: "#fff",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  quickSamples: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexWrap: "wrap",
    fontSize: "0.78rem",
  },
  quickLabel: {
    color: "var(--text-dim)",
  },
  sampleChip: {
    background: "rgba(255, 255, 255, 0.05)",
    border: "1px solid var(--border-subtle)",
    color: "var(--text-muted)",
    padding: "4px 10px",
    borderRadius: "var(--radius-full)",
    fontSize: "0.75rem",
    transition: "background 0.2s, color 0.2s",
  },
  feedbackAlert: {
    padding: "10px 14px",
    borderRadius: "var(--radius-md)",
    fontSize: "0.82rem",
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  successAlert: {
    background: "rgba(16, 185, 129, 0.12)",
    border: "1px solid rgba(16, 185, 129, 0.3)",
    color: "#34d399",
  },
  errorAlert: {
    background: "rgba(239, 68, 68, 0.12)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    color: "#f87171",
  },
};
