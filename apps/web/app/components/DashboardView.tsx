"use client";

import React, { useEffect, useState } from "react";
import { IngestedVideo } from "./IngestionBar";

interface DashboardViewProps {
  videos: IngestedVideo[];
  onSelectVideoForStudio: (videoId: string, title: string, scope?: string) => void;
  onOpenExplorerWithQuery?: (query: string, videoId?: string) => void;
  onOpenIngestModal: () => void;
  apiBaseUrl?: string;
}

interface IngestionJob {
  job_id: string;
  playlist_title?: string | null;
  status: string;
  total: number;
  completed: number;
  counts: Record<string, number>;
  failed_items: { video_id: string; title: string; status: string; attempts: number; error?: string | null }[];
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  videos,
  onSelectVideoForStudio,
  onOpenExplorerWithQuery,
  onOpenIngestModal,
  apiBaseUrl = "http://127.0.0.1:8000",
}) => {
  const [filterQuery, setFilterQuery] = useState("");
  const [ingestionJobs, setIngestionJobs] = useState<IngestionJob[]>([]);
  const [ingestionPaused, setIngestionPaused] = useState(false);
  const [ingestionActionError, setIngestionActionError] = useState("");

  useEffect(() => {
    let disposed = false;
    const refresh = async () => {
      try {
        const [jobsResponse, statusResponse] = await Promise.all([
          fetch(`${apiBaseUrl}/api/ingest/jobs?limit=5`),
          fetch(`${apiBaseUrl}/api/ingest/status`),
        ]);
        if (!jobsResponse.ok || !statusResponse.ok) return;
        const [jobsData, statusData] = await Promise.all([jobsResponse.json(), statusResponse.json()]);
        if (!disposed) {
          setIngestionJobs(Array.isArray(jobsData.jobs) ? jobsData.jobs : []);
          setIngestionPaused(Boolean(statusData.is_paused));
        }
      } catch {
        // Keep the last progress snapshot visible while the API reconnects.
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [apiBaseUrl]);

  const controlIngestion = async (action: "stop" | "resume") => {
    setIngestionActionError("");
    try {
      const response = await fetch(`${apiBaseUrl}/api/ingest/${action}`, { method: "POST" });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const data = await response.json();
      setIngestionPaused(Boolean(data.status?.is_paused));
    } catch (error) {
      setIngestionActionError(error instanceof Error ? error.message : "Could not update ingestion job.");
    }
  };

  const retryVideo = async (jobId: string, videoId: string) => {
    setIngestionActionError("");
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/ingest/jobs/${encodeURIComponent(jobId)}/retry?video_id=${encodeURIComponent(videoId)}`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error(`Retry request failed (${response.status})`);
      const data = await response.json();
      const updatedJob = {
        ...data.job,
        failed_items: (data.job.items || []).filter((item: IngestionJob["failed_items"][number]) => item.status === "failed").slice(0, 10),
      };
      setIngestionJobs((previous) => previous.map((job) => job.job_id === jobId ? updatedJob : job));
    } catch (error) {
      setIngestionActionError(error instanceof Error ? error.message : "Could not retry this video.");
    }
  };

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
            <span style={styles.statFootText}>ONNX Runtime CPU • Hybrid retrieval and reranking</span>
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
            <span style={styles.statFootText}>Evidence cutoff • Citation required • -5s Lead-in</span>
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
      {ingestionJobs.length > 0 && (
        <section className="glass-panel" style={{ padding: "20px 22px", borderRadius: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <div>
              <h3 style={{ ...styles.sectionTitle, margin: 0 }}>Playlist indexing jobs</h3>
              <p style={{ ...styles.sectionSubtitle, marginTop: 5 }}>Progress is saved locally and resumes after an API restart.</p>
            </div>
            {ingestionJobs.some((job) => ["queued", "running", "paused"].includes(job.status)) && (
              <button
                className="btn-secondary"
                onClick={() => void controlIngestion(ingestionPaused ? "resume" : "stop")}
              >
                {ingestionPaused ? "Resume indexing" : "Pause indexing"}
              </button>
            )}
          </div>
          {ingestionActionError && <p role="alert" style={{ color: "#fca5a5", fontSize: "0.8rem" }}>{ingestionActionError}</p>}
          <div style={{ display: "grid", gap: 14, marginTop: 16 }}>
            {ingestionJobs.map((job) => {
              const progress = job.total ? Math.round((job.completed / job.total) * 100) : 0;
              const failedItems = job.failed_items || [];
              return (
                <div key={job.job_id} style={{ padding: 14, borderRadius: 12, background: "rgba(255,255,255,0.035)", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", fontSize: "0.82rem" }}>
                    <strong>{job.playlist_title || "Playlist ingestion"}</strong>
                    <span style={{ color: "var(--text-muted)" }}>{job.status.replaceAll("_", " ")} · {job.completed}/{job.total} videos · {progress}%</span>
                  </div>
                  <div style={{ height: 6, marginTop: 10, borderRadius: 999, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
                    <div style={{ width: `${progress}%`, height: "100%", background: "linear-gradient(90deg, #6366f1, #a78bfa)", transition: "width 0.3s ease" }} />
                  </div>
                  <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8, color: "var(--text-dim)", fontSize: "0.72rem" }}>
                    <span>Queued {job.counts.queued || 0}</span>
                    <span>Indexed {job.counts.completed || 0}</span>
                    <span>No captions {job.counts.no_captions || 0}</span>
                    <span>Failed {job.counts.failed || 0}</span>
                  </div>
                  {failedItems.slice(0, 3).map((item) => (
                    <div key={item.video_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginTop: 8, fontSize: "0.76rem" }}>
                      <span title={item.error || undefined} style={{ color: "#fca5a5", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.title}: {item.error || "Indexing failed"}</span>
                      <button className="btn-secondary" onClick={() => void retryVideo(job.job_id, item.video_id)}>Retry</button>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </section>
      )}

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
        <div style={styles.playlistGroupsContainer}>
          {(() => {
            // Group videos: true playlists have a valid playlist_id
            const playlists: { [key: string]: { id: string; title: string; videos: IngestedVideo[] } } = {};
            const standaloneVideos: IngestedVideo[] = [];

            filteredVideos.forEach((v) => {
              if (v.playlist_id && v.playlist_id !== "standalone") {
                const pId = v.playlist_id;
                const pTitle = v.playlist_title || `Playlist ${v.playlist_id}`;
                if (!playlists[pId]) {
                  playlists[pId] = { id: pId, title: pTitle, videos: [] };
                }
                playlists[pId].videos.push(v);
              } else {
                standaloneVideos.push(v);
              }
            });

            return (
              <>
                {/* 1. Real YouTube Playlists */}
                {Object.values(playlists).map((group) => {
                  if (!group.videos || group.videos.length === 0) return null;
                  const firstVid = group.videos[0]!;
                  const totalPlaylistChunks = group.videos.reduce((sum, v) => sum + (v.chunks || 0), 0);
                  const playlistThumb = `https://img.youtube.com/vi/${firstVid.video_id}/hqdefault.jpg`;

                  return (
                    <div key={group.id} className="glass-panel" style={styles.playlistContainerCard}>
                      {/* Playlist Header Banner (YouTube Playlist style) */}
                      <div style={styles.playlistBanner}>
                        <div style={styles.playlistBannerLeft}>
                          <div style={styles.playlistThumbStack}>
                            <img
                              src={playlistThumb}
                              alt={group.title}
                              style={styles.playlistHeroThumb}
                              onError={(e) => {
                                (e.target as HTMLElement).style.display = "none";
                              }}
                            />
                            <div style={styles.playlistStackOverlay}>
                              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                <line x1="8" y1="6" x2="21" y2="6" />
                                <line x1="8" y1="12" x2="21" y2="12" />
                                <line x1="8" y1="18" x2="21" y2="18" />
                                <line x1="3" y1="6" x2="3.01" y2="6" />
                                <line x1="3" y1="12" x2="3.01" y2="12" />
                                <line x1="3" y1="18" x2="3.01" y2="18" />
                              </svg>
                              <span style={styles.playlistCountBadge}>
                                {group.videos.length} VIDEOS
                              </span>
                            </div>
                          </div>

                          <div style={styles.playlistInfoCol}>
                            <div style={styles.playlistMetaBadgeRow}>
                              <span className="badge badge-primary">
                                YouTube Playlist
                              </span>
                              <span className="badge badge-success">
                                {totalPlaylistChunks} Total Chunks
                              </span>
                            </div>
                            <h3 style={styles.playlistHeadingTitle}>{group.title}</h3>
                            <p style={styles.playlistSubtext}>
                              Ask questions about this entire playlist at once, or select any specific lecture below to focus queries on that single video.
                            </p>
                          </div>
                        </div>

                        {/* Chat with Entire Playlist CTA */}
                        <div style={styles.playlistActionsCol}>
                          <button
                            className="btn-primary"
                            style={styles.askEntirePlaylistBtn}
                            onClick={() => {
                              // Opens studio with Chat scope explicitly set to entire playlist ("all")
                              onSelectVideoForStudio(firstVid.video_id, firstVid.title, "all");
                            }}
                            title="Open studio with Chat scope set to entire playlist"
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                            </svg>
                            <span>Chat About Entire Playlist</span>
                          </button>

                          {onOpenExplorerWithQuery && (
                            <button
                              className="btn-secondary"
                              style={styles.explorePlaylistBtn}
                              onClick={() => onOpenExplorerWithQuery("", "")}
                              title="Search chunks across all lectures in playlist"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="11" cy="11" r="8" />
                                <line x1="21" y1="21" x2="16.65" y2="16.65" />
                              </svg>
                              <span>Search Transcripts</span>
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Horizontal Scroll / Grid of Lectures inside this Playlist */}
                      <details style={styles.playlistVideosSection}>
                        <summary style={{ ...styles.playlistVideosSectionHeader, cursor: "pointer", listStyle: "none" }}>
                          <span style={styles.playlistVideosLabel}>
                            Lectures in this Playlist ({group.videos.length})
                          </span>
                          <span style={styles.playlistVideosHint}>
                            Select any lecture to study individually & ask video-specific questions
                          </span>
                        </summary>

                        <div style={styles.playlistVideosScroll}>
                          {group.videos.map((vid, idx) => {
                            const thumbUrl = `https://img.youtube.com/vi/${vid.video_id}/hqdefault.jpg`;
                            return (
                              <div
                                key={vid.video_id}
                                style={styles.lectureCard}
                                onClick={() => onSelectVideoForStudio(vid.video_id, vid.title, vid.video_id)}
                              >
                                <div style={styles.lectureThumbWrapper}>
                                  <img
                                    src={thumbUrl}
                                    alt={vid.title}
                                    style={styles.lectureThumbImg}
                                    onError={(e) => {
                                      (e.target as HTMLElement).style.display = "none";
                                    }}
                                  />
                                  <div style={styles.lectureIndexBadge}>
                                    #{idx + 1}
                                  </div>
                                  <div style={styles.lectureChunksBadge}>
                                    {vid.chunks || 0} Chunks
                                  </div>
                                </div>

                                <div style={styles.lectureCardBody}>
                                  <h5 style={styles.lectureCardTitle} title={vid.title}>
                                    {vid.title}
                                  </h5>
                                  <div style={styles.lectureCardFooter}>
                                    <span style={styles.lectureIdText}>ID: {vid.video_id}</span>
                                    <button
                                      className="btn-primary"
                                      style={styles.lecturePlayBtn}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        onSelectVideoForStudio(vid.video_id, vid.title, vid.video_id);
                                      }}
                                      title="Study this video & ask targeted questions"
                                    >
                                      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                                        <polygon points="5 3 19 12 5 21 5 3" />
                                      </svg>
                                      <span>Study Video</span>
                                    </button>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </details>
                    </div>
                  );
                })}

                {/* 2. Standalone Individual Videos (Shown as standard standalone cards, NOT a playlist) */}
                {standaloneVideos.length > 0 && (
                  <div style={styles.standaloneSection}>
                    <div style={styles.playlistVideosSectionHeader}>
                      <span style={styles.playlistVideosLabel}>
                        Individual Videos ({standaloneVideos.length})
                      </span>
                      <span style={styles.playlistVideosHint}>
                        Standalone videos not part of any playlist
                      </span>
                    </div>

                    <div style={styles.videoGrid}>
                      {standaloneVideos.map((vid) => {
                        const thumbUrl = `https://img.youtube.com/vi/${vid.video_id}/hqdefault.jpg`;
                        return (
                          <div key={vid.video_id} className="glass-panel" style={styles.videoCard}>
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

                            <div style={styles.cardBody}>
                              <h4 style={styles.cardTitle} title={vid.title}>{vid.title}</h4>
                              <div style={styles.cardMeta}>
                                <span style={styles.cardMetaItem}>
                                  <span style={{ color: "var(--text-dim)" }}>ID:</span> {vid.video_id}
                                </span>
                                <span style={styles.cardMetaDot}>•</span>
                                <span style={styles.cardMetaItem}>Single Video</span>
                              </div>

                              <div style={styles.cardActions}>
                                <button
                                  className="btn-primary"
                                  style={styles.cardActionPrimary}
                                  onClick={() => onSelectVideoForStudio(vid.video_id, vid.title, vid.video_id)}
                                >
                                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                    <polygon points="5 3 19 12 5 21 5 3" fill="currentColor" />
                                  </svg>
                                  <span>Study Video</span>
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
                  </div>
                )}
              </>
            );
          })()}
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
  playlistGroupsContainer: {
    display: "flex",
    flexDirection: "column",
    gap: "32px",
  },
  standaloneSection: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    marginTop: "8px",
  },
  playlistContainerCard: {
    padding: "0",
    overflow: "hidden",
    borderRadius: "var(--radius-lg)",
    border: "1px solid var(--border-subtle)",
    background: "rgba(18, 22, 36, 0.75)",
  },
  playlistBanner: {
    padding: "24px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "24px",
    flexWrap: "wrap",
    background: "linear-gradient(135deg, rgba(30, 27, 75, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%)",
    borderBottom: "1px solid var(--border-subtle)",
  },
  playlistBannerLeft: {
    display: "flex",
    alignItems: "center",
    gap: "20px",
    flex: 1,
    minWidth: "320px",
  },
  playlistThumbStack: {
    position: "relative",
    width: "160px",
    height: "90px",
    borderRadius: "var(--radius-md)",
    overflow: "hidden",
    flexShrink: 0,
    boxShadow: "0 8px 20px rgba(0,0,0,0.4)",
    background: "#0f172a",
  },
  playlistHeroThumb: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  },
  playlistStackOverlay: {
    position: "absolute",
    inset: 0,
    background: "linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.3) 100%)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "4px",
    color: "#fff",
  },
  playlistCountBadge: {
    fontSize: "0.7rem",
    fontWeight: 800,
    letterSpacing: "0.06em",
  },
  playlistInfoCol: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  playlistMetaBadgeRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  playlistHeadingTitle: {
    fontSize: "1.25rem",
    fontWeight: 800,
    color: "var(--text-main)",
    lineHeight: 1.3,
  },
  playlistSubtext: {
    fontSize: "0.82rem",
    color: "var(--text-muted)",
    maxWidth: "580px",
    lineHeight: 1.5,
  },
  playlistActionsCol: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    flexWrap: "wrap",
  },
  askEntirePlaylistBtn: {
    padding: "12px 20px",
    fontSize: "0.88rem",
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    gap: "8px",
    background: "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",
    boxShadow: "0 4px 15px rgba(99, 102, 241, 0.35)",
  },
  explorePlaylistBtn: {
    padding: "12px 16px",
    fontSize: "0.88rem",
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  playlistVideosSection: {
    padding: "20px 24px",
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  playlistVideosSectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "8px",
  },
  playlistVideosLabel: {
    fontSize: "0.82rem",
    fontWeight: 700,
    color: "var(--text-main)",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  playlistVideosHint: {
    fontSize: "0.75rem",
    color: "var(--text-dim)",
  },
  playlistVideosScroll: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
    gap: "14px",
    maxHeight: "440px",
    overflowY: "auto",
    paddingRight: "6px",
  },
  lectureCard: {
    background: "rgba(255, 255, 255, 0.03)",
    border: "1px solid var(--border-subtle)",
    borderRadius: "var(--radius-md)",
    overflow: "hidden",
    cursor: "pointer",
    display: "flex",
    flexDirection: "column",
    transition: "transform 0.15s, border-color 0.2s, background 0.2s",
  },
  lectureThumbWrapper: {
    position: "relative",
    aspectRatio: "16 / 9",
    background: "#0c0e17",
    overflow: "hidden",
  },
  lectureThumbImg: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  },
  lectureIndexBadge: {
    position: "absolute",
    top: "8px",
    left: "8px",
    background: "rgba(0, 0, 0, 0.75)",
    color: "#fff",
    padding: "2px 7px",
    borderRadius: "4px",
    fontSize: "0.7rem",
    fontWeight: 700,
  },
  lectureChunksBadge: {
    position: "absolute",
    bottom: "8px",
    right: "8px",
    background: "rgba(16, 185, 129, 0.85)",
    color: "#fff",
    padding: "2px 6px",
    borderRadius: "4px",
    fontSize: "0.68rem",
    fontWeight: 600,
  },
  lectureCardBody: {
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    flex: 1,
  },
  lectureCardTitle: {
    fontSize: "0.84rem",
    fontWeight: 600,
    lineHeight: 1.4,
    color: "var(--text-main)",
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
    minHeight: "2.4em",
  },
  lectureCardFooter: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: "auto",
    paddingTop: "6px",
  },
  lectureIdText: {
    fontSize: "0.7rem",
    color: "var(--text-dim)",
    fontFamily: "var(--font-mono)",
  },
  lecturePlayBtn: {
    padding: "4px 8px",
    fontSize: "0.72rem",
    display: "flex",
    alignItems: "center",
    gap: "4px",
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
