"use client";

import React, { useEffect, useRef, useState, useImperativeHandle, forwardRef } from "react";

export interface YouTubePlayerRef {
  seekTo: (seconds: number) => void;
  loadVideo: (videoId: string, startSeconds?: number) => void;
}

interface YouTubePlayerProps {
  initialVideoId?: string;
  videoTitle?: string;
  onTimeUpdate?: (seconds: number) => void;
}

declare global {
  interface Window {
    YT: any;
    onYouTubeIframeAPIReady: () => void;
  }
}

export const YouTubePlayer = forwardRef<YouTubePlayerRef, YouTubePlayerProps>(
  ({ initialVideoId = "dQw4w9WgXcQ", videoTitle = "Active Video", onTimeUpdate }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const playerRef = useRef<any>(null);
    const [isReady, setIsReady] = useState(false);
    const [currentVideoId, setCurrentVideoId] = useState(initialVideoId);
    const [lastJumpTime, setLastJumpTime] = useState<number | null>(null);
    const [jumpNotice, setJumpNotice] = useState<string | null>(null);

    // Expose seekTo and loadVideo to parent component
    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        if (playerRef.current && typeof playerRef.current.seekTo === "function") {
          playerRef.current.seekTo(seconds, true);
          playerRef.current.playVideo();
          setLastJumpTime(seconds);
          const mins = Math.floor(seconds / 60);
          const secs = Math.floor(seconds % 60);
          setJumpNotice(`Jumped to ${mins}:${secs < 10 ? "0" : ""}${secs} (-5s lead-in applied)`);
          setTimeout(() => setJumpNotice(null), 4000);
        }
      },
      loadVideo: (videoId: string, startSeconds = 0) => {
        setCurrentVideoId(videoId);
        if (playerRef.current && typeof playerRef.current.loadVideoById === "function") {
          playerRef.current.loadVideoById({
            videoId,
            startSeconds,
          });
          playerRef.current.playVideo();
          setLastJumpTime(startSeconds);
          const mins = Math.floor(startSeconds / 60);
          const secs = Math.floor(startSeconds % 60);
          setJumpNotice(`Switched video & jumped to ${mins}:${secs < 10 ? "0" : ""}${secs}`);
          setTimeout(() => setJumpNotice(null), 4000);
        }
      },
    }));

    useEffect(() => {
      // 1. Load YouTube IFrame API Script if not already loaded
      if (!window.YT) {
        const tag = document.createElement("script");
        tag.src = "https://www.youtube.com/iframe_api";
        const firstScriptTag = document.getElementsByTagName("script")[0];
        firstScriptTag?.parentNode?.insertBefore(tag, firstScriptTag);
      }

      const initPlayer = () => {
        if (!containerRef.current || playerRef.current) return;
        playerRef.current = new window.YT.Player(containerRef.current, {
          height: "100%",
          width: "100%",
          videoId: currentVideoId,
          playerVars: {
            autoplay: 0,
            modestbranding: 1,
            rel: 0,
            enablejsapi: 1,
            origin: window.location.origin,
          },
          events: {
            onReady: () => {
              setIsReady(true);
            },
          },
        });
      };

      if (window.YT && window.YT.Player) {
        initPlayer();
      } else {
        window.onYouTubeIframeAPIReady = initPlayer;
      }

      return () => {
        if (playerRef.current && typeof playerRef.current.destroy === "function") {
          playerRef.current.destroy();
          playerRef.current = null;
        }
      };
    }, [currentVideoId]);

    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <div style={styles.titleWrapper}>
            <div className="live-dot" />
            <h2 style={styles.videoTitle} title={videoTitle}>
              {videoTitle}
            </h2>
          </div>
          {jumpNotice && (
            <div style={styles.jumpBadge}>
              <span style={{ color: "var(--accent-yt)" }}>▸</span> {jumpNotice}
            </div>
          )}
        </div>

        <div style={styles.videoFrameWrapper}>
          <div ref={containerRef} style={styles.iframeTarget} />
        </div>

        <div style={styles.footerBar}>
          <span style={styles.hintText}>
            ⚡ <strong>The In-Page Jump:</strong> Clicking any citation timestamp in the chat jumps the video player right here without opening a new tab.
          </span>
        </div>
      </div>
    );
  }
);

YouTubePlayer.displayName = "YouTubePlayer";

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: "flex",
    flexDirection: "column",
    background: "var(--bg-card)",
    borderRadius: "var(--radius-lg)",
    border: "1px solid var(--border-subtle)",
    overflow: "hidden",
    boxShadow: "var(--shadow-md)",
    backdropFilter: "blur(16px)",
  },
  header: {
    padding: "16px 20px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottom: "1px solid var(--border-subtle)",
    gap: "12px",
    flexWrap: "wrap",
  },
  titleWrapper: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  videoTitle: {
    fontSize: "0.95rem",
    fontWeight: 600,
    color: "var(--text-main)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  jumpBadge: {
    fontSize: "0.75rem",
    fontWeight: 600,
    background: "rgba(255, 42, 42, 0.15)",
    border: "1px solid rgba(255, 42, 42, 0.4)",
    color: "#ff7b7b",
    padding: "4px 10px",
    borderRadius: "var(--radius-full)",
    display: "flex",
    alignItems: "center",
    gap: "6px",
    animation: "pulseGlow 2s infinite",
  },
  videoFrameWrapper: {
    position: "relative",
    width: "100%",
    paddingTop: "56.25%", // 16:9 Aspect Ratio
    background: "#000",
  },
  iframeTarget: {
    position: "absolute",
    top: 0,
    left: 0,
    width: "100%",
    height: "100%",
  },
  footerBar: {
    padding: "12px 20px",
    background: "rgba(0, 0, 0, 0.2)",
    borderTop: "1px solid var(--border-subtle)",
  },
  hintText: {
    fontSize: "0.78rem",
    color: "var(--text-muted)",
    lineHeight: 1.4,
  },
};
