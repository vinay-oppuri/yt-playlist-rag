"use client";

import React, { useState, useEffect } from "react";
import { IngestedVideo } from "./IngestionBar";

interface SearchResultHit {
  score: number;
  text: string;
  video_id: string;
  video_title: string;
  timestamp: string;
  start_sec: number;
  video_url: string;
}

interface SearchExplorerViewProps {
  videos: IngestedVideo[];
  initialQuery?: string;
  initialVideoId?: string;
  onJumpToStudio: (videoId: string, startSec: number, title: string) => void;
  apiBaseUrl?: string;
}

export const SearchExplorerView: React.FC<SearchExplorerViewProps> = ({
  videos,
  initialQuery = "",
  initialVideoId = "",
  onJumpToStudio,
  apiBaseUrl = "http://127.0.0.1:8000",
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [selectedVideoId, setSelectedVideoId] = useState(initialVideoId);
  const [scoreThreshold, setScoreThreshold] = useState<number>(0.30);
  const [limit, setLimit] = useState<number>(8);
  const [results, setResults] = useState<SearchResultHit[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const executeSearch = async (q = query) => {
    if (!q.trim()) return;
    setIsLoading(true);
    setErrorMsg(null);
    setSearched(true);

    try {
      const response = await fetch(`${apiBaseUrl}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q.trim(),
          collection_name: "yt_transcripts",
          limit: limit,
          video_id: selectedVideoId ? selectedVideoId : null,
          score_threshold: scoreThreshold > 0 ? scoreThreshold : null,
        }),
      });

      if (!response.ok) {
        throw new Error(`Search request failed with status ${response.status}`);
      }

      const data = await response.json();
      setResults(data.results || []);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to search vector store.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (initialQuery) {
      setQuery(initialQuery);
      executeSearch(initialQuery);
    }
  }, [initialQuery]);

  return (
    <div style={styles.container}>
      {/* ── Search Controls Header ───────────────────────────────── */}
      <div className="glass-panel" style={styles.controlsPanel}>
        <div style={styles.searchBarRow}>
          <div style={styles.inputWrapper}>
            <svg style={styles.searchIcon} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              placeholder="Ask or search topic (e.g. 'how does quicksort work', 'binary search complexity')..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && executeSearch()}
              className="input-field"
              style={{ paddingLeft: "42px", fontSize: "0.95rem" }}
            />
          </div>
          <button
            className="btn-primary"
            onClick={() => executeSearch()}
            disabled={isLoading || !query.trim()}
            style={{ padding: "10px 24px" }}
          >
            {isLoading ? "Searching..." : "Vector Search"}
          </button>
        </div>

        {/* Filters & Threshold Sliders */}
        <div style={styles.filtersRow}>
          {/* Video Filter Dropdown */}
          <div style={styles.filterItem}>
            <label style={styles.filterLabel}>Filter to Video:</label>
            <select
              value={selectedVideoId}
              onChange={(e) => setSelectedVideoId(e.target.value)}
              style={styles.select}
            >
              <option value="">All Videos ({videos.length})</option>
              {videos.map((v) => (
                <option key={v.video_id} value={v.video_id}>
                  {v.title.slice(0, 45)}... ({v.video_id})
                </option>
              ))}
            </select>
          </div>

          {/* Min Similarity Score Slider */}
          <div style={styles.filterItem}>
            <div style={styles.sliderLabelRow}>
              <span style={styles.filterLabel}>Min Similarity Cutoff:</span>
              <span style={styles.sliderValue}>{Math.round(scoreThreshold * 100)}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={0.9}
              step={0.05}
              value={scoreThreshold}
              onChange={(e) => setScoreThreshold(parseFloat(e.target.value))}
              style={styles.rangeInput}
            />
          </div>

          {/* Max Hits Limit Slider */}
          <div style={styles.filterItem}>
            <div style={styles.sliderLabelRow}>
              <span style={styles.filterLabel}>Max Chunks:</span>
              <span style={styles.sliderValue}>{limit}</span>
            </div>
            <input
              type="range"
              min={1}
              max={20}
              step={1}
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value))}
              style={styles.rangeInput}
            />
          </div>
        </div>
      </div>

      {/* ── Search Results List ──────────────────────────────────── */}
      {errorMsg && (
        <div className="glass-panel" style={{ ...styles.alert, color: "#fca5a5" }}>
          ⚠️ {errorMsg}
        </div>
      )}

      {searched && !isLoading && results.length === 0 && !errorMsg && (
        <div className="glass-panel" style={styles.emptyState}>
          <p style={{ color: "var(--text-muted)" }}>
            No transcript chunks matched &ldquo;{query}&rdquo; above {Math.round(scoreThreshold * 100)}% similarity.
          </p>
          <p style={{ fontSize: "0.8rem", color: "var(--text-dim)", marginTop: "6px" }}>
            Try lowering the similarity cutoff slider or ingesting the video containing this topic.
          </p>
        </div>
      )}

      {results.length > 0 && (
        <div style={styles.resultsContainer}>
          <div style={styles.resultsHeader}>
            <span style={styles.resultsCount}>
              Found <strong>{results.length}</strong> matching transcript windows (Ranked by Cosine Similarity)
            </span>
          </div>

          <div style={styles.resultsList}>
            {results.map((hit, idx) => {
              const scorePct = Math.round(hit.score * 100);
              const scoreColor = scorePct >= 70 ? "#34d399" : scorePct >= 50 ? "#818cf8" : "#fbbf24";
              return (
                <div key={idx} className="glass-panel" style={styles.hitCard}>
                  {/* Card Top: Rank, Score Badge, Timestamp */}
                  <div style={styles.hitTop}>
                    <div style={styles.hitRankBox}>
                      <span style={styles.hitRank}>#{idx + 1}</span>
                      <span style={{ ...styles.hitScoreBadge, borderColor: scoreColor, color: scoreColor }}>
                        {scorePct}% Match
                      </span>
                    </div>

                    <div style={styles.hitTimeActions}>
                      <span style={styles.hitTimeBadge}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <polygon points="5 3 19 12 5 21 5 3" fill="currentColor" />
                        </svg>
                        {hit.timestamp}
                      </span>
                      <button
                        className="btn-primary"
                        style={styles.hitJumpBtn}
                        onClick={() => onJumpToStudio(hit.video_id, hit.start_sec, hit.video_title)}
                      >
                        <span>Jump in Studio</span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="9 18 15 12 9 6" />
                        </svg>
                      </button>
                      <a
                        href={hit.video_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn-ghost"
                        style={styles.hitYtBtn}
                        title="Open on YouTube at timestamp"
                      >
                        YouTube ↗
                      </a>
                    </div>
                  </div>

                  {/* Video Title */}
                  <div style={styles.hitVideoTitle}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polygon points="23 7 16 12 23 17 23 7" />
                      <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                    </svg>
                    <span>{hit.video_title}</span>
                    <span style={styles.hitId}>({hit.video_id})</span>
                  </div>

                  {/* Transcript Content */}
                  <div style={styles.hitTextBox}>
                    <p style={styles.hitText}>{hit.text}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
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
  controlsPanel: {
    padding: "24px",
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  searchBarRow: {
    display: "flex",
    gap: "12px",
  },
  inputWrapper: {
    position: "relative",
    flex: 1,
  },
  searchIcon: {
    position: "absolute",
    left: "14px",
    top: "50%",
    transform: "translateY(-50%)",
    color: "var(--text-dim)",
    pointerEvents: "none",
  },
  filtersRow: {
    display: "flex",
    gap: "24px",
    alignItems: "center",
    flexWrap: "wrap",
    paddingTop: "6px",
    borderTop: "1px solid var(--border-subtle)",
  },
  filterItem: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    minWidth: "180px",
  },
  filterLabel: {
    fontSize: "0.72rem",
    fontWeight: 600,
    color: "var(--text-muted)",
  },
  select: {
    background: "rgba(10, 13, 22, 0.8)",
    border: "1px solid var(--border-subtle)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text-main)",
    padding: "8px 12px",
    fontSize: "0.82rem",
    outline: "none",
  },
  sliderLabelRow: {
    display: "flex",
    justifyContent: "space-between",
  },
  sliderValue: {
    fontSize: "0.72rem",
    fontFamily: "var(--font-mono)",
    color: "#a5b4fc",
    fontWeight: 700,
  },
  rangeInput: {
    accentColor: "#6366f1",
    cursor: "pointer",
  },
  resultsContainer: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  resultsHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  resultsCount: {
    fontSize: "0.85rem",
    color: "var(--text-muted)",
  },
  resultsList: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  hitCard: {
    padding: "18px 20px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  hitTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "10px",
  },
  hitRankBox: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  hitRank: {
    fontSize: "0.85rem",
    fontWeight: 800,
    color: "var(--text-dim)",
    fontFamily: "var(--font-mono)",
  },
  hitScoreBadge: {
    fontSize: "0.72rem",
    fontWeight: 700,
    padding: "2px 8px",
    borderRadius: "4px",
    border: "1px solid",
    background: "rgba(0, 0, 0, 0.3)",
    fontFamily: "var(--font-mono)",
  },
  hitTimeActions: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  hitTimeBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: "5px",
    padding: "4px 8px",
    borderRadius: "4px",
    background: "rgba(255, 255, 255, 0.05)",
    fontSize: "0.75rem",
    fontFamily: "var(--font-mono)",
    color: "#a5b4fc",
  },
  hitJumpBtn: {
    padding: "6px 12px",
    fontSize: "0.75rem",
  },
  hitYtBtn: {
    fontSize: "0.75rem",
    padding: "6px 10px",
  },
  hitVideoTitle: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "0.82rem",
    fontWeight: 600,
    color: "var(--text-main)",
  },
  hitId: {
    fontFamily: "var(--font-mono)",
    fontSize: "0.72rem",
    color: "var(--text-dim)",
  },
  hitTextBox: {
    padding: "12px 14px",
    background: "rgba(0, 0, 0, 0.3)",
    borderRadius: "var(--radius-sm)",
    borderLeft: "3px solid #6366f1",
  },
  hitText: {
    fontSize: "0.85rem",
    lineHeight: 1.6,
    color: "var(--text-muted)",
  },
  emptyState: {
    padding: "48px 24px",
    textAlign: "center",
  },
  alert: {
    padding: "16px 20px",
    background: "rgba(239, 68, 68, 0.12)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
  },
};
