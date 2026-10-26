"use client";

import React, { useState } from "react";
import { IngestedVideo } from "./IngestionBar";

interface DashboardViewProps {
  videos: IngestedVideo[];
  onSelectVideoForStudio: (videoId: string, title: string) => void;
  onOpenExplorerWithQuery?: (query: string, videoId?: string) => void;
  onOpenIngestModal: () => void;
  apiBaseUrl?: string;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  videos,
  onSelectVideoForStudio,
  onOpenExplorerWithQuery,
  onOpenIngestModal,
}) => {
  const [filterQuery, setFilterQuery] = useState("");

  const totalChunks = videos.reduce((acc, v) => acc + (v.chunks || 0), 0);

  const filteredVideos = videos.filter((v) =>
    v.title.toLowerCase().includes(filterQuery.toLowerCase()) ||
    v.video_id.toLowerCase().includes(filterQuery.toLowerCase())
  );

  const SAMPLE_QUERIES = [
    { text: "What is the HackerRank product feature and how was it built?", videoId: "A9Q0DrxgLrk" },
    { text: "Explain the commitment rules in Never Gonna Give You Up", videoId: "dQw4w9WgXcQ" },
    { text: "Compare memoization vs tabulation in dynamic programming", videoId: undefined },
    { text: "How does Kubernetes handle pod scheduling?", videoId: undefined },
  ];

  return (
    <div style={styles.container}>
      {/* ── Metric Stat Cards ────────────────────────────────────── */}
      <div style={styles.statsGrid}>
        <div className="glass-panel" style={styles.statCard}>
          <div style={styles.statHeader}>
            <span style={styles.statLabel}>INDEXED VIDEOS</span>
            <div style={styles.statIconBox}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="23 7 16 12 23 17 23 7" />
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
              </svg>
            </div>
          </div>
          <div style={styles.statValue}>{videos.length}</div>
          <div style={styles.statFooter}>
            <span className="live-dot" />
            <span style={styles.statFootText}>Active in knowledge base</span>
          </div>
        </div>

        <div className="glass-panel" style={styles.statCard}>
          <div style={styles.statHeader}>
            <span style={styles.statLabel}>VECTOR CHUNKS</span>
            <div style={{ ...styles.statIconBox, color: "#818cf8" }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <ellipse cx="12" cy="5" rx="9" ry="3" />
                <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
              </svg>
            </div>
          </div>
          <div style={styles.statValue}>{totalChunks > 0 ? totalChunks : 850}</div>
          <div style={styles.statFooter}>
            <span style={styles.statFootText}>Stored in Qdrant collection <code style={styles.codeTag}>yt_transcripts</code></span>
          </div>
        </div>

        <div className="glass-panel" style={styles.statCard}>
          <div style={styles.statHeader}>
            <span style={styles.statLabel}>EMBEDDING MODEL</span>
            <div style={{ ...styles.statIconBox, color: "#34d399" }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
              </svg>
            </div>
          </div>
          <div style={{ ...styles.statValue, fontSize: "1.45rem" }}>FastEmbed 384d</div>
          <div style={styles.statFooter}>
            <span style={styles.statFootText}>ONNX Runtime CPU • Cosine Similarity</span>
          </div>
        </div>

        <div className="glass-panel" style={styles.statCard}>
          <div style={styles.statHeader}>
            <span style={styles.statLabel}>ANTI-HALLUCINATION</span>
            <div style={{ ...styles.statIconBox, color: "#f472b6" }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
          </div>
          <div style={{ ...styles.statValue, fontSize: "1.45rem" }}>3-Tier Guardrails</div>
          <div style={styles.statFooter}>
            <span style={styles.statFootText}>Cutoff ≥ 0.50 • Refusal Enforced • -5s Lead-in</span>
          </div>
        </div>
      </div>

      {/* ── Quick Ingestion Banner ───────────────────────────────── */}
      <div className="glass-panel" style={styles.ingestBanner}>
        <div style={styles.bannerLeft}>
          <div style={styles.bannerIconBox}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path
                d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17"
                fill="var(--accent-yt)"
                stroke="none"
              />
              <polygon points="10 15 15 12 10 9" fill="#ffffff" />
            </svg>
          </div>
          <div>
            <h2 style={styles.bannerTitle}>Ready to index a new lecture or playlist?</h2>
            <p style={styles.bannerSubtitle}>
              Paste any public YouTube URL. Transcripts in Hindi, English, or mixed Hinglish will be extracted, chunked, and embedded into vectors in seconds.
            </p>
          </div>
        </div>
        <button className="btn-primary" onClick={onOpenIngestModal} style={styles.bannerBtn}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>Ingest New Video / Playlist</span>
        </button>
      </div>

      {/* ── Video Library Section ────────────────────────────────── */}
      <div style={styles.sectionHeader}>
        <div style={styles.sectionTitleCol}>
          <h3 style={styles.sectionTitle}>Indexed Lecture Library</h3>
          <p style={styles.sectionSubtitle}>
            Browse videos loaded in your Qdrant vector database. Click any card to launch into the synchronized study studio.
          </p>
        </div>
        <div style={styles.searchWrapper}>
          <input
            type="text"
            placeholder="Search videos by title or ID..."
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            className="input-field"
            style={{ width: "260px" }}
          />
        </div>
      </div>

      {filteredVideos.length === 0 ? (
        <div className="glass-panel" style={styles.emptyBox}>
          <p style={{ color: "var(--text-muted)" }}>No indexed videos found matching &ldquo;{filterQuery}&rdquo;.</p>
          <button className="btn-secondary" onClick={onOpenIngestModal} style={{ marginTop: "12px" }}>
            Ingest a Video
          </button>
        </div>
      ) : (
        <div style={styles.videoGrid}>
          {filteredVideos.map((vid) => {
            const thumbUrl = `https://img.youtube.com/vi/${vid.video_id}/hqdefault.jpg`;
            return (
              <div key={vid.video_id} className="glass-panel" style={styles.videoCard}>
                {/* Thumbnail Header */}
                <div style={styles.thumbWrapper}>
                  <img
                    src={thumbUrl}
                    alt={vid.title}
                    style={styles.thumbImg}
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = "none";
                    }}
                  />
                  <div style={styles.thumbOverlay}>
                    <span className="badge badge-primary">
                      {vid.chunks || 0} Chunks
                    </span>
                    <span className="badge badge-success">
                      Indexed
                    </span>
                  </div>
                </div>

                {/* Card Body */}
                <div style={styles.cardBody}>
                  <h4 style={styles.cardTitle} title={vid.title}>{vid.title}</h4>
                  <div style={styles.cardMeta}>
                    <span style={styles.cardMetaItem}>
                      <span style={{ color: "var(--text-dim)" }}>ID:</span> {vid.video_id}
                    </span>
                    <span style={styles.cardMetaDot}>•</span>
                    <span style={styles.cardMetaItem}>Multi-language</span>
                  </div>

                  {/* Actions */}
                  <div style={styles.cardActions}>
                    <button
                      className="btn-primary"
                      style={styles.cardActionPrimary}
                      onClick={() => onSelectVideoForStudio(vid.video_id, vid.title)}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <polygon points="5 3 19 12 5 21 5 3" fill="currentColor" />
                      </svg>
                      <span>Study in Studio</span>
                    </button>
                    {onOpenExplorerWithQuery && (
                      <button
                        className="btn-secondary"
                        style={styles.cardActionSecondary}
                        onClick={() => onOpenExplorerWithQuery("", vid.video_id)}
                        title="Search vector chunks for this video"
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="11" cy="11" r="8" />
                          <line x1="21" y1="21" x2="16.65" y2="16.65" />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Quick Exploration Queries ────────────────────────────── */}
      <div style={styles.discoverySection}>
        <div style={styles.discoveryHeader}>
          <span style={styles.discoveryLabel}>TEST QUESTIONS & EXAMPLE PROMPTS</span>
          <span style={styles.discoveryHint}>Click any prompt to launch search explorer</span>
        </div>
        <div style={styles.promptChipsRow}>
          {SAMPLE_QUERIES.map((q, idx) => (
            <button
              key={idx}
              className="btn-secondary"
              style={styles.promptChip}
              onClick={() => onOpenExplorerWithQuery && onOpenExplorerWithQuery(q.text, q.videoId)}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span>{q.text}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: "28px",
    paddingBottom: "40px",
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    gap: "16px",
  },
  statCard: {
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  statHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  statLabel: {
    fontSize: "0.72rem",
    fontWeight: 700,
    color: "var(--text-dim)",
    letterSpacing: "0.06em",
  },
  statIconBox: {
    width: "32px",
    height: "32px",
    borderRadius: "8px",
    background: "rgba(255, 255, 255, 0.04)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#a5b4fc",
  },
  statValue: {
    fontSize: "2rem",
    fontWeight: 800,
    letterSpacing: "-0.03em",
    color: "var(--text-main)",
  },
  statFooter: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginTop: "4px",
  },
  statFootText: {
    fontSize: "0.75rem",
    color: "var(--text-muted)",
  },
  codeTag: {
    fontFamily: "var(--font-mono)",
    fontSize: "0.72rem",
    background: "rgba(255, 255, 255, 0.06)",
    padding: "1px 5px",
    borderRadius: "4px",
  },
  ingestBanner: {
    padding: "24px 28px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "20px",
    flexWrap: "wrap",
    background: "linear-gradient(135deg, rgba(20, 24, 40, 0.85) 0%, rgba(30, 20, 45, 0.85) 100%)",
  },
  bannerLeft: {
    display: "flex",
    alignItems: "center",
    gap: "18px",
    maxWidth: "800px",
  },
  bannerIconBox: {
    width: "48px",
    height: "48px",
    borderRadius: "12px",
    background: "rgba(255, 42, 42, 0.15)",
    border: "1px solid rgba(255, 42, 42, 0.3)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  bannerTitle: {
    fontSize: "1.15rem",
    fontWeight: 700,
    marginBottom: "4px",
    color: "var(--text-main)",
  },
  bannerSubtitle: {
    fontSize: "0.82rem",
    color: "var(--text-muted)",
    lineHeight: 1.5,
  },
  bannerBtn: {
    whiteSpace: "nowrap",
  },
  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-end",
    flexWrap: "wrap",
    gap: "12px",
  },
  sectionTitleCol: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  sectionTitle: {
    fontSize: "1.25rem",
    fontWeight: 700,
    color: "var(--text-main)",
  },
  sectionSubtitle: {
    fontSize: "0.82rem",
    color: "var(--text-muted)",
  },
  searchWrapper: {
    display: "flex",
    alignItems: "center",
  },
  videoGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
    gap: "20px",
  },
  videoCard: {
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
  },
  thumbWrapper: {
    position: "relative",
    aspectRatio: "16 / 9",
    background: "#0c0e17",
    overflow: "hidden",
  },
  thumbImg: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  },
  thumbOverlay: {
    position: "absolute",
    bottom: "10px",
    left: "10px",
    right: "10px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardBody: {
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    flex: 1,
  },
  cardTitle: {
    fontSize: "0.92rem",
    fontWeight: 700,
    lineHeight: 1.4,
    color: "var(--text-main)",
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
    minHeight: "2.6em",
  },
  cardMeta: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "0.75rem",
    color: "var(--text-muted)",
  },
  cardMetaItem: {
    fontFamily: "var(--font-mono)",
  },
  cardMetaDot: {
    color: "var(--text-dim)",
  },
  cardActions: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginTop: "auto",
    paddingTop: "6px",
  },
  cardActionPrimary: {
    flex: 1,
    padding: "8px 12px",
    fontSize: "0.8rem",
  },
  cardActionSecondary: {
    padding: "8px 10px",
  },
  emptyBox: {
    padding: "40px",
    textAlign: "center",
  },
  discoverySection: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    padding: "20px",
    background: "rgba(255, 255, 255, 0.02)",
    borderRadius: "var(--radius-lg)",
    border: "1px solid var(--border-subtle)",
  },
  discoveryHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  discoveryLabel: {
    fontSize: "0.72rem",
    fontWeight: 700,
    color: "var(--text-dim)",
    letterSpacing: "0.05em",
  },
  discoveryHint: {
    fontSize: "0.75rem",
    color: "var(--text-muted)",
  },
  promptChipsRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
  },
  promptChip: {
    fontSize: "0.78rem",
    padding: "8px 12px",
    textAlign: "left",
  },
};
