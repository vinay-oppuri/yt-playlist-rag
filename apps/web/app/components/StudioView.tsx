"use client";

import React from "react";
import { YouTubePlayer, type YouTubePlayerRef } from "./YouTubePlayer";
import { ChatPanel } from "./ChatPanel";
import { IngestedVideo } from "./IngestionBar";

interface StudioViewProps {
  playerRef: React.RefObject<YouTubePlayerRef | null>;
  activeVideoId: string;
  activeVideoTitle: string;
  playlistVideos: IngestedVideo[];
  onSelectVideo: (videoId: string, title: string) => void;
  onSeek: (videoId: string, startSec: number, videoTitle: string) => void;
  apiBaseUrl?: string;
  initialChatScope?: string;
}

export const StudioView: React.FC<StudioViewProps> = ({
  playerRef,
  activeVideoId,
  activeVideoTitle,
  playlistVideos,
  onSelectVideo,
  onSeek,
  apiBaseUrl = "http://127.0.0.1:8000",
  initialChatScope,
}) => {
  return (
    <div style={styles.grid}>
      {/* Left Column: Embedded YouTube Player & Video Playlist Selector */}
      <div style={styles.leftCol}>
        <div className="glass-panel" style={styles.playerWrapper}>
          <YouTubePlayer
            ref={playerRef}
            initialVideoId={activeVideoId}
            videoTitle={activeVideoTitle}
          />
        </div>

        {/* Playlist Video Selector */}
        {playlistVideos.length > 0 && (
          <details className="glass-panel" style={styles.playlistBox}>
            <summary style={styles.playlistHeader}>
              <div style={styles.playlistTitleRow}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="12 2 2 7 12 12 22 7 12 2" />
                  <polyline points="2 17 12 22 22 17" />
                  <polyline points="2 12 12 17 22 12" />
                </svg>
                <span style={styles.playlistTitle}>
                  Playlist queue ({playlistVideos.length})
                </span>
              </div>
              <span style={styles.playlistHint}>Click to switch active player video</span>
            </summary>

            <div style={styles.videoList}>
              {playlistVideos.map((vid) => {
                const isSelected = vid.video_id === activeVideoId;
                return (
                  <button
                    key={vid.video_id}
                    style={{
                      ...styles.videoItem,
                      ...(isSelected ? styles.videoItemSelected : {}),
                    }}
                    onClick={() => onSelectVideo(vid.video_id, vid.title)}
                  >
                    <img
                      src={`https://img.youtube.com/vi/${vid.video_id}/mqdefault.jpg`}
                      alt=""
                      style={styles.videoThumbnail}
                    />
                    <div style={styles.videoItemText}>
                      <span style={styles.videoItemTitle}>{vid.title}</span>
                      <span style={styles.videoItemMeta}>
                        {isSelected ? "Now playing" : "Play next"} · {vid.chunks || 0} chunks
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </details>
        )}
      </div>

      {/* Right Column: Grounded Conversational Q&A */}
      <div style={styles.rightCol}>
        <ChatPanel
          apiBaseUrl={apiBaseUrl}
          onSeek={onSeek}
          onSelectVideo={onSelectVideo}
          activeVideoId={activeVideoId}
          playlistVideos={playlistVideos}
          initialScope={initialChatScope}
        />
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  grid: {
    display: "grid",
    gridTemplateColumns: "1.05fr 0.95fr",
    gap: "24px",
    alignItems: "start",
  },
  leftCol: {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  playerWrapper: {
    padding: "16px",
    borderRadius: "var(--radius-lg)",
  },
  rightCol: {
    height: "calc(100vh - 140px)",
    minHeight: "640px",
  },
  playlistBox: {
    padding: "16px",
    borderRadius: "var(--radius-lg)",
  },
  playlistHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "12px",
    paddingBottom: "8px",
    borderBottom: "1px solid var(--border-subtle)",
    cursor: "pointer",
    listStyle: "none",
  },
  playlistTitleRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    color: "var(--text-main)",
  },
  playlistTitle: {
    fontSize: "0.85rem",
    fontWeight: 700,
  },
  playlistHint: {
    fontSize: "0.72rem",
    color: "var(--text-dim)",
  },
  videoList: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    maxHeight: "300px",
    overflowY: "auto",
  },
  videoItem: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "8px 12px",
    borderRadius: "var(--radius-sm)",
    background: "rgba(255, 255, 255, 0.02)",
    border: "1px solid transparent",
    textAlign: "left",
    cursor: "pointer",
    transition: "all 0.15s ease",
  },
  videoItemSelected: {
    background: "rgba(99, 102, 241, 0.15)",
    border: "1px solid rgba(99, 102, 241, 0.35)",
  },
  videoItemIcon: {
    width: "24px",
    height: "24px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "var(--text-dim)",
  },
  videoThumbnail: {
    width: "112px",
    aspectRatio: "16 / 9",
    objectFit: "cover",
    borderRadius: "6px",
    flexShrink: 0,
    background: "#111",
  },
  videoItemText: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    overflow: "hidden",
  },
  videoItemTitle: {
    fontSize: "0.8rem",
    fontWeight: 600,
    color: "var(--text-main)",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  videoItemMeta: {
    fontSize: "0.7rem",
    color: "var(--text-dim)",
    fontFamily: "var(--font-mono)",
  },
};
