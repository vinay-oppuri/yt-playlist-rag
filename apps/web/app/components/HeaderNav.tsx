"use client";

import React from "react";

export type NavTab = "dashboard" | "studio" | "explorer" | "system";

interface HeaderNavProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  onOpenIngestModal: () => void;
  apiStatus: "online" | "checking" | "offline";
  indexedCount: number;
}

export const HeaderNav: React.FC<HeaderNavProps> = ({
  activeTab,
  onTabChange,
  onOpenIngestModal,
  apiStatus,
  indexedCount,
}) => {
  return (
    <header style={styles.header}>
      <div style={styles.leftSection}>
        <div style={styles.brand} onClick={() => onTabChange("dashboard")}>
          <div style={styles.logoIcon}>
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
            <div style={styles.brandTitleRow}>
              <span style={styles.brandTitle} className="gradient-text">YT-RAG</span>
              <span style={styles.versionBadge}>v1.0 Studio</span>
            </div>
            <p style={styles.brandSubtitle}>YouTube Playlist RAG & Grounded Learning</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav style={styles.navTabs}>
          <button
            style={{
              ...styles.tabBtn,
              ...(activeTab === "dashboard" ? styles.tabBtnActive : {}),
            }}
            onClick={() => onTabChange("dashboard")}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="9" />
              <rect x="14" y="3" width="7" height="5" />
              <rect x="14" y="12" width="7" height="9" />
              <rect x="3" y="16" width="7" height="5" />
            </svg>
            <span>Dashboard</span>
            {indexedCount > 0 && (
              <span style={styles.tabBadge}>{indexedCount}</span>
            )}
          </button>

          <button
            style={{
              ...styles.tabBtn,
              ...(activeTab === "studio" ? styles.tabBtnActive : {}),
            }}
            onClick={() => onTabChange("studio")}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            <span>Study Studio</span>
          </button>

          <button
            style={{
              ...styles.tabBtn,
              ...(activeTab === "explorer" ? styles.tabBtnActive : {}),
            }}
            onClick={() => onTabChange("explorer")}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <span>Search Explorer</span>
          </button>

          <button
            style={{
              ...styles.tabBtn,
              ...(activeTab === "system" ? styles.tabBtnActive : {}),
            }}
            onClick={() => onTabChange("system")}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <ellipse cx="12" cy="5" rx="9" ry="3" />
              <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
            </svg>
            <span>Vector DB & Specs</span>
          </button>
        </nav>
      </div>

      <div style={styles.rightSection}>
        {/* API Status Badge */}
        <div style={styles.statusBadge}>
          <span
            className={`live-dot ${
              apiStatus === "online" ? "" : apiStatus === "checking" ? "warning" : "danger"
            }`}
          />
          <span style={styles.statusText}>
            {apiStatus === "online"
              ? "FastAPI :8000 Online"
              : apiStatus === "checking"
              ? "Checking API..."
              : "API Offline"}
          </span>
        </div>

        {/* Quick Ingest Button */}
        <button className="btn-primary" onClick={onOpenIngestModal} style={styles.ingestBtn}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>Ingest URL</span>
        </button>

        {/* Link to Docs (port 3001) */}
        <a
          href="http://localhost:3001"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary"
          style={styles.docsLink}
        >
          <span>Docs & API</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </a>
      </div>
    </header>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "14px 28px",
    background: "rgba(10, 13, 22, 0.95)",
    backdropFilter: "blur(20px)",
    borderBottom: "1px solid var(--border-subtle)",
    position: "sticky",
    top: 0,
    zIndex: 100,
    gap: "16px",
    flexWrap: "wrap",
  },
  leftSection: {
    display: "flex",
    alignItems: "center",
    gap: "28px",
    flexWrap: "wrap",
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    cursor: "pointer",
  },
  logoIcon: {
    width: "38px",
    height: "38px",
    borderRadius: "10px",
    background: "rgba(255, 42, 42, 0.12)",
    border: "1px solid rgba(255, 42, 42, 0.25)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 0 14px rgba(255, 42, 42, 0.2)",
  },
  brandTitleRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  brandTitle: {
    fontSize: "1.15rem",
    fontWeight: 800,
    letterSpacing: "-0.02em",
  },
  versionBadge: {
    fontSize: "0.68rem",
    fontWeight: 700,
    padding: "2px 6px",
    borderRadius: "4px",
    background: "rgba(99, 102, 241, 0.15)",
    color: "#a5b4fc",
    border: "1px solid rgba(99, 102, 241, 0.25)",
  },
  brandSubtitle: {
    fontSize: "0.72rem",
    color: "var(--text-dim)",
    fontWeight: 500,
  },
  navTabs: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    background: "rgba(255, 255, 255, 0.03)",
    padding: "4px",
    borderRadius: "12px",
    border: "1px solid var(--border-subtle)",
  },
  tabBtn: {
    display: "flex",
    alignItems: "center",
    gap: "7px",
    padding: "7px 14px",
    fontSize: "0.82rem",
    fontWeight: 600,
    color: "var(--text-muted)",
    borderRadius: "8px",
    cursor: "pointer",
    transition: "all 0.15s ease",
  },
  tabBtnActive: {
    color: "#ffffff",
    background: "rgba(99, 102, 241, 0.25)",
    border: "1px solid rgba(99, 102, 241, 0.4)",
    boxShadow: "0 2px 8px rgba(99, 102, 241, 0.25)",
  },
  tabBadge: {
    fontSize: "0.65rem",
    padding: "1px 6px",
    borderRadius: "10px",
    background: "rgba(99, 102, 241, 0.4)",
    color: "#fff",
  },
  rightSection: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  statusBadge: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "6px 12px",
    background: "rgba(255, 255, 255, 0.04)",
    border: "1px solid var(--border-subtle)",
    borderRadius: "20px",
  },
  statusText: {
    fontSize: "0.75rem",
    fontWeight: 500,
    color: "var(--text-muted)",
  },
  ingestBtn: {
    padding: "8px 14px",
    fontSize: "0.8rem",
  },
  docsLink: {
    padding: "8px 12px",
    fontSize: "0.8rem",
  },
};
