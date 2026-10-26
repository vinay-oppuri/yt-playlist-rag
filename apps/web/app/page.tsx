"use client";

import React, { useState, useRef, useEffect } from "react";
import { HeaderNav, type NavTab } from "./components/HeaderNav";
import { DashboardView } from "./components/DashboardView";
import { StudioView } from "./components/StudioView";
import { SearchExplorerView } from "./components/SearchExplorerView";
import { SystemHealthView } from "./components/SystemHealthView";
import { IngestModal } from "./components/IngestModal";
import { type YouTubePlayerRef } from "./components/YouTubePlayer";
import { type IngestedVideo } from "./components/IngestionBar";

export default function Home() {
  const playerRef = useRef<YouTubePlayerRef>(null);

  // Active top navigation tab
  const [activeTab, setActiveTab] = useState<NavTab>("dashboard");

  // Ingestion modal state
  const [isIngestModalOpen, setIsIngestModalOpen] = useState(false);

  // Backend API status
  const [apiStatus, setApiStatus] = useState<"online" | "checking" | "offline">("checking");

  // Initial video knowledge base
  const [playlistVideos, setPlaylistVideos] = useState<IngestedVideo[]>([
    {
      video_id: "A9Q0DrxgLrk",
      title: "Sorry HackerR**k 😈 I Built a product That Takes Your Real Interview",
      chunks: 24,
      status: "success",
    },
    {
      video_id: "dQw4w9WgXcQ",
      title: "Rick Astley - Never Gonna Give You Up (Official Video)",
      chunks: 8,
      status: "success",
    },
    {
      video_id: "47YClVMlthI",
      title: "Justin Bieber - Confident ft. Chance The Rapper",
      chunks: 12,
      status: "success",
    },
  ]);

  // Active player video in Studio
  const [activeVideoId, setActiveVideoId] = useState("A9Q0DrxgLrk");
  const [activeVideoTitle, setActiveVideoTitle] = useState(
    "Sorry HackerR**k 😈 I Built a product That Takes Your Real Interview"
  );

  // Query handoff to Explorer tab
  const [explorerQuery, setExplorerQuery] = useState("");
  const [explorerVideoId, setExplorerVideoId] = useState("");

  // Check backend health & fetch registered videos on mount
  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/health")
      .then((res) => {
        if (res.ok) {
          setApiStatus("online");
          fetch("http://127.0.0.1:8000/api/videos")
            .then((r) => r.json())
            .then((data) => {
              if (Array.isArray(data.videos) && data.videos.length > 0) {
                setPlaylistVideos(
                  data.videos.map((v: any) => ({
                    video_id: v.video_id,
                    title: v.title,
                    chunks: v.chunks_count || 0,
                    status: v.is_transcribed ? "success" : v.status || "registered",
                  }))
                );
              }
            })
            .catch(() => {});
        } else {
          setApiStatus("offline");
        }
      })
      .catch(() => setApiStatus("offline"));
  }, []);

  const handleSeek = (videoId: string, startSec: number, videoTitle: string) => {
    if (videoId !== activeVideoId) {
      setActiveVideoId(videoId);
      setActiveVideoTitle(videoTitle);
      playerRef.current?.loadVideo(videoId, startSec);
    } else {
      playerRef.current?.seekTo(startSec);
    }
  };

  const handleSelectVideoForStudio = (videoId: string, title: string) => {
    setActiveVideoId(videoId);
    setActiveVideoTitle(title);
    playerRef.current?.loadVideo(videoId, 0);
    setActiveTab("studio");
  };

  const handleJumpToStudioFromSearch = (videoId: string, startSec: number, title: string) => {
    setActiveVideoId(videoId);
    setActiveVideoTitle(title);
    setActiveTab("studio");
    setTimeout(() => {
      playerRef.current?.loadVideo(videoId, startSec);
    }, 100);
  };

  const handleOpenExplorerWithQuery = (query: string, videoId?: string) => {
    setExplorerQuery(query);
    setExplorerVideoId(videoId || "");
    setActiveTab("explorer");
  };

  const handleIngestionSuccess = (newVideos: IngestedVideo[]) => {
    setPlaylistVideos((prev) => {
      // Merge unique by video_id
      const existingIds = new Set(prev.map((v) => v.video_id));
      const filteredNew = newVideos.filter((v) => !existingIds.has(v.video_id));
      return [...filteredNew, ...prev];
    });

    const valid = newVideos.find((v) => v.status === "success") || newVideos[0];
    if (valid) {
      setActiveVideoId(valid.video_id);
      setActiveVideoTitle(valid.title);
      playerRef.current?.loadVideo(valid.video_id, 0);
    }
  };

  return (
    <div style={styles.page}>
      {/* ── Top Header Navigation ──────────────────────────────────── */}
      <HeaderNav
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onOpenIngestModal={() => setIsIngestModalOpen(true)}
        apiStatus={apiStatus}
        indexedCount={playlistVideos.length}
      />

      {/* ── Main Content Area ─────────────────────────────────────── */}
      <main style={styles.main}>
        {activeTab === "dashboard" && (
          <DashboardView
            videos={playlistVideos}
            onSelectVideoForStudio={handleSelectVideoForStudio}
            onOpenExplorerWithQuery={handleOpenExplorerWithQuery}
            onOpenIngestModal={() => setIsIngestModalOpen(true)}
            apiBaseUrl="http://127.0.0.1:8000"
          />
        )}

        {activeTab === "studio" && (
          <StudioView
            playerRef={playerRef}
            activeVideoId={activeVideoId}
            activeVideoTitle={activeVideoTitle}
            playlistVideos={playlistVideos}
            onSelectVideo={(id, title) => {
              setActiveVideoId(id);
              setActiveVideoTitle(title);
              playerRef.current?.loadVideo(id, 0);
            }}
            onSeek={handleSeek}
            apiBaseUrl="http://127.0.0.1:8000"
          />
        )}

        {activeTab === "explorer" && (
          <SearchExplorerView
            videos={playlistVideos}
            initialQuery={explorerQuery}
            initialVideoId={explorerVideoId}
            onJumpToStudio={handleJumpToStudioFromSearch}
            apiBaseUrl="http://127.0.0.1:8000"
          />
        )}

        {activeTab === "system" && (
          <SystemHealthView apiBaseUrl="http://127.0.0.1:8000" />
        )}
      </main>

      {/* ── Global Quick Ingestion Modal ──────────────────────────── */}
      <IngestModal
        isOpen={isIngestModalOpen}
        onClose={() => setIsIngestModalOpen(false)}
        apiBaseUrl="http://127.0.0.1:8000"
        onIngestSuccess={handleIngestionSuccess}
      />
    </div>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  page: {
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    backgroundColor: "var(--bg-deep)",
  },
  main: {
    flex: 1,
    padding: "24px 28px",
    maxWidth: "1600px",
    width: "100%",
    margin: "0 auto",
  },
};
