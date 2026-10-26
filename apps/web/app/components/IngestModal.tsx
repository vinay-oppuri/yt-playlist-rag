"use client";

import React, { useState } from "react";
import { IngestedVideo } from "./IngestionBar";

interface IngestModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl?: string;
  onIngestSuccess: (videos: IngestedVideo[]) => void;
}

export const IngestModal: React.FC<IngestModalProps> = ({
  isOpen,
  onClose,
  apiBaseUrl = "http://127.0.0.1:8000",
  onIngestSuccess,
}) => {
  const [url, setUrl] = useState("");
  const [targetWords, setTargetWords] = useState(180);
  const [overlapWords, setOverlapWords] = useState(35);
  const [collectionName, setCollectionName] = useState("yt_transcripts");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [ingestMode, setIngestMode] = useState<"video" | "playlist">("video");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const hasVideoParam = url.includes("v=");
  const hasPlaylistParam = url.includes("list=");

  if (!isOpen) return null;

  const handleIngest = async (targetUrl?: string) => {
    const finalUrl = (targetUrl || url).trim();
    if (!finalUrl) return;

    setIsLoading(true);
    setResult(null);

    const isPlaylistMode = finalUrl.includes("list=") && (ingestMode === "playlist" || !finalUrl.includes("v="));

    try {
      const response = await fetch(`${apiBaseUrl}/api/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: finalUrl,
          collection_name: collectionName,
          target_words: targetWords,
          overlap_words: overlapWords,
          force_playlist: isPlaylistMode,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Ingestion request failed" }));
        throw new Error(err.detail || `Server error (${response.status})`);
      }

      const data = await response.json();
      const isHierarchical = data.mode === "hierarchical";
      setResult({
        type: "success",
        text: isHierarchical
          ? `⚡ Registered all ${data.videos_total} playlist videos instantly! (${data.total_chunks_stored} chunks ready for lecture playback). Remaining lecture transcripts will index on-demand.`
          : `Successfully indexed ${data.videos_indexed} of ${data.videos_total} video(s) • ${data.total_chunks_stored} vector embeddings created.`,
      });

      if (Array.isArray(data.details)) {
        onIngestSuccess(data.details);
      }
    } catch (err: any) {
      setResult({
        type: "error",
        text: err.message || "Could not reach FastAPI backend at :8000. Ensure 'uv run main.py' is running.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const PRESETS = [
    {
      title: "HackerRank Product (Hinglish/Hindi)",
      url: "https://www.youtube.com/watch?v=A9Q0DrxgLrk",
      desc: "Tests multi-language caption priority (hi-orig)",
    },
    {
      title: "Rick Astley - Never Gonna Give You Up",
      url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      desc: "Verified English lyric transcripts",
    },
    {
      title: "Justin Bieber - Confident ft. Chance",
      url: "https://www.youtube.com/watch?v=47YClVMlthI",
      desc: "Music video subtitles test",
    },
  ];

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.titleWrapper}>
            <div style={styles.iconBox}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path
                  d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17"
                  fill="var(--accent-yt)"
                  stroke="none"
                />
                <polygon points="10 15 15 12 10 9" fill="#ffffff" />
              </svg>
            </div>
            <div>
              <h3 style={styles.title}>Ingest YouTube Video or Playlist</h3>
              <p style={styles.subtitle}>Extract captions, chunk timestamps, embed & index in Qdrant</p>
            </div>
          </div>
          <button style={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        {/* URL Input */}
        <div style={styles.body}>
          <label style={styles.label}>YouTube Video or Playlist URL</label>
          <div style={styles.inputRow}>
            <input
              type="text"
              placeholder="https://www.youtube.com/watch?v=... or playlist?list=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="input-field"
              disabled={isLoading}
            />
            <button
              className="btn-primary"
              onClick={() => handleIngest()}
              disabled={isLoading || !url.trim()}
              style={{ whiteSpace: "nowrap" }}
            >
              {isLoading ? (
                <>
                  <span className="live-dot warning" />
                  <span>Ingesting...</span>
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                  <span>Start Ingest</span>
                </>
              )}
            </button>
          </div>

          {/* Mode Selector for URLs with both video and playlist */}
          {hasVideoParam && hasPlaylistParam && (
            <div style={styles.scopeBox}>
              <span style={styles.scopeNotice}>
                Detected video inside a playlist. Choose ingestion scope:
              </span>
              <div style={styles.scopeButtons}>
                <button
                  type="button"
                  style={{
                    ...styles.scopeBtn,
                    ...(ingestMode === "video" ? styles.scopeBtnActive : {}),
                  }}
                  onClick={() => setIngestMode("video")}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="5 3 19 12 5 21 5 3" fill="currentColor" />
                  </svg>
                  <span>This Video Only</span>
                </button>
                <button
                  type="button"
                  style={{
                    ...styles.scopeBtn,
                    ...(ingestMode === "playlist" ? styles.scopeBtnActive : {}),
                  }}
                  onClick={() => setIngestMode("playlist")}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="12 2 2 7 12 12 22 7 12 2" />
                    <polyline points="2 17 12 22 22 17" />
                    <polyline points="2 12 12 17 22 12" />
                  </svg>
                  <span>Entire Playlist</span>
                </button>
              </div>
            </div>
          )}

          {/* Quick Presets */}
          <div style={styles.presetsBox}>
            <span style={styles.presetsLabel}>QUICK TEST PRESETS:</span>
            <div style={styles.presetGrid}>
              {PRESETS.map((p) => (
                <button
                  key={p.url}
                  style={styles.presetItem}
                  onClick={() => {
                    setUrl(p.url);
                    handleIngest(p.url);
                  }}
                  disabled={isLoading}
                >
                  <div style={styles.presetTitle}>{p.title}</div>
                  <div style={styles.presetDesc}>{p.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Advanced Settings Toggle */}
          <div>
            <button
              style={styles.advancedToggle}
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <span>{showAdvanced ? "▼ Hide Chunking Configuration" : "▶ Advanced Chunking & Qdrant Options"}</span>
            </button>

            {showAdvanced && (
              <div style={styles.advancedBox}>
                <div style={styles.advancedRow}>
                  <div style={{ flex: 1 }}>
                    <label style={styles.subLabel}>Target Words / Chunk</label>
                    <input
                      type="number"
                      value={targetWords}
                      onChange={(e) => setTargetWords(Number(e.target.value))}
                      className="input-field"
                      min={50}
                      max={1000}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={styles.subLabel}>Overlap Words</label>
                    <input
                      type="number"
                      value={overlapWords}
                      onChange={(e) => setOverlapWords(Number(e.target.value))}
                      className="input-field"
                      min={0}
                      max={200}
                    />
                  </div>
                  <div style={{ flex: 1.5 }}>
                    <label style={styles.subLabel}>Qdrant Collection</label>
                    <input
                      type="text"
                      value={collectionName}
                      onChange={(e) => setCollectionName(e.target.value)}
                      className="input-field"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Result Alert */}
          {result && (
            <div
              style={{
                ...styles.alert,
                ...(result.type === "success" ? styles.alertSuccess : styles.alertError),
              }}
            >
              <span className={`live-dot ${result.type === "success" ? "" : "danger"}`} />
              <span style={{ fontSize: "0.85rem", lineHeight: 1.4 }}>{result.text}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0, 0, 0, 0.75)",
    backdropFilter: "blur(8px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
    padding: "20px",
  },
  modal: {
    width: "100%",
    maxWidth: "680px",
    background: "rgba(14, 18, 30, 0.98)",
    border: "1px solid var(--border-hover)",
    borderRadius: "var(--radius-lg)",
    boxShadow: "0 20px 50px rgba(0, 0, 0, 0.8), 0 0 30px rgba(99, 102, 241, 0.2)",
    overflow: "hidden",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "20px 24px",
    borderBottom: "1px solid var(--border-subtle)",
    background: "rgba(255, 255, 255, 0.02)",
  },
  titleWrapper: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
  },
  iconBox: {
    width: "40px",
    height: "40px",
    borderRadius: "10px",
    background: "rgba(255, 42, 42, 0.15)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    border: "1px solid rgba(255, 42, 42, 0.25)",
  },
  title: {
    fontSize: "1.05rem",
    fontWeight: 700,
    color: "var(--text-main)",
  },
  subtitle: {
    fontSize: "0.78rem",
    color: "var(--text-muted)",
  },
  closeBtn: {
    fontSize: "1.1rem",
    color: "var(--text-dim)",
    padding: "6px 10px",
    borderRadius: "6px",
  },
  body: {
    padding: "24px",
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  label: {
    fontSize: "0.82rem",
    fontWeight: 600,
    color: "var(--text-main)",
  },
  inputRow: {
    display: "flex",
    gap: "10px",
  },
  presetsBox: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  presetsLabel: {
    fontSize: "0.7rem",
    fontWeight: 700,
    color: "var(--text-dim)",
    letterSpacing: "0.05em",
  },
  presetGrid: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: "6px",
  },
  presetItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    padding: "10px 14px",
    background: "rgba(255, 255, 255, 0.03)",
    border: "1px solid var(--border-subtle)",
    borderRadius: "var(--radius-sm)",
    textAlign: "left",
    cursor: "pointer",
    transition: "all 0.15s ease",
  },
  presetTitle: {
    fontSize: "0.82rem",
    fontWeight: 600,
    color: "#a5b4fc",
  },
  presetDesc: {
    fontSize: "0.72rem",
    color: "var(--text-muted)",
  },
  advancedToggle: {
    fontSize: "0.75rem",
    fontWeight: 600,
    color: "var(--text-dim)",
    padding: "4px 0",
    cursor: "pointer",
  },
  advancedBox: {
    padding: "14px",
    background: "rgba(0, 0, 0, 0.3)",
    border: "1px solid var(--border-subtle)",
    borderRadius: "var(--radius-md)",
    marginTop: "8px",
  },
  advancedRow: {
    display: "flex",
    gap: "12px",
  },
  subLabel: {
    fontSize: "0.72rem",
    fontWeight: 500,
    color: "var(--text-muted)",
    display: "block",
    marginBottom: "4px",
  },
  alert: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "12px 16px",
    borderRadius: "var(--radius-md)",
  },
  alertSuccess: {
    background: "rgba(16, 185, 129, 0.12)",
    border: "1px solid rgba(16, 185, 129, 0.3)",
    color: "#6ee7b7",
  },
  alertError: {
    background: "rgba(239, 68, 68, 0.12)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    color: "#fca5a5",
  },
  scopeBox: {
    padding: "10px 14px",
    background: "rgba(99, 102, 241, 0.08)",
    border: "1px solid rgba(99, 102, 241, 0.2)",
    borderRadius: "var(--radius-sm)",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  scopeNotice: {
    fontSize: "0.75rem",
    color: "#c7d2fe",
    fontWeight: 500,
  },
  scopeButtons: {
    display: "flex",
    gap: "8px",
  },
  scopeBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    padding: "6px 12px",
    fontSize: "0.75rem",
    fontWeight: 600,
    borderRadius: "6px",
    background: "rgba(255, 255, 255, 0.04)",
    border: "1px solid var(--border-subtle)",
    color: "var(--text-muted)",
    cursor: "pointer",
    transition: "all 0.15s ease",
  },
  scopeBtnActive: {
    background: "rgba(99, 102, 241, 0.3)",
    borderColor: "#818cf8",
    color: "#ffffff",
    boxShadow: "0 2px 8px rgba(99, 102, 241, 0.25)",
  },
};
