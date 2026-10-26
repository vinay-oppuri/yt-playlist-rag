"use client";

import React, { useState, useRef, useEffect } from "react";

export interface Citation {
  citation_index: number;
  video_title: string;
  timestamp: string;
  start_sec: number;
  video_id: string;
  video_url: string;
  score: number;
  preview: string;
}

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  citations?: Citation[];
  grounded?: boolean;
  refused?: boolean;
  provider?: string;
  model?: string;
}

interface ChatPanelProps {
  apiBaseUrl?: string;
  onSeek: (videoId: string, startSec: number, videoTitle: string) => void;
  activeVideoId?: string;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  apiBaseUrl = "http://127.0.0.1:8000",
  onSeek,
  activeVideoId,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      sender: "assistant",
      text: "👋 Welcome to YouTube Lecture RAG! Ask any question about your indexed lectures or videos. Every answer is strictly grounded in the transcript, with clickable timestamps that jump to the exact second.",
      grounded: true,
    },
  ]);
  const [inputQuestion, setInputQuestion] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSubmitting]);

  const handleSend = async (customQuestion?: string) => {
    const q = customQuestion || inputQuestion;
    if (!q.trim() || isSubmitting) return;

    const userMsgId = `user-${Date.now()}`;
    const userMsg: ChatMessage = {
      id: userMsgId,
      sender: "user",
      text: q.trim(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuestion("");
    setIsSubmitting(true);

    try {
      const response = await fetch(`${apiBaseUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q.trim(),
          collection_name: "yt_transcripts",
          top_k: 5,
          min_score: 0.50,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const data = await response.json();
      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: "assistant",
        text: data.answer || "No response generated.",
        citations: data.citations || [],
        grounded: data.grounded,
        refused: data.refused,
        provider: data.provider,
        model: data.model,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          sender: "assistant",
          text: `⚠️ Could not reach the API backend at ${apiBaseUrl}. Please ensure FastAPI is running with 'uv run main.py'.`,
          grounded: false,
        },
      ]);
    } finally {
      setIsSubmitting(false);
    }
  };

  const samplePrompts = [
    "What are the rules of love?",
    "Where is commitment mentioned?",
    "How does Kubernetes pod scheduling work?", // off-topic test for refusal
  ];

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.headerTitleWrapper}>
          <div style={styles.chatIcon}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div>
            <h2 style={styles.headerTitle}>Grounded Lecture Q&A</h2>
            <p style={styles.headerSubtitle}>Zero hallucinations • Strict timestamp citations</p>
          </div>
        </div>
      </div>

      <div style={styles.messageList}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              ...styles.messageRow,
              justifyContent: msg.sender === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                ...styles.messageBubble,
                ...(msg.sender === "user" ? styles.userBubble : styles.assistantBubble),
              }}
            >
              {msg.refused && (
                <div style={styles.refusalBadge}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                    <line x1="12" y1="9" x2="12" y2="13" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                  </svg>
                  <span>Anti-Hallucination Guardrail Active: Topic Not In Lectures</span>
                </div>
              )}

              <p style={styles.messageText}>{msg.text}</p>

              {msg.citations && msg.citations.length > 0 && (
                <div style={styles.citationSection}>
                  <div style={styles.citationHeader}>
                    <span>VERIFIED TIMESTAMP SOURCES (Click to Jump In-Page):</span>
                  </div>
                  <div style={styles.citationGrid}>
                    {msg.citations.map((c) => (
                      <button
                        key={`${c.video_id}-${c.citation_index}`}
                        style={styles.citationCard}
                        onClick={() => onSeek(c.video_id, c.start_sec, c.video_title)}
                        title={`Click to jump to ${c.timestamp} in video player`}
                      >
                        <div style={styles.citationCardTop}>
                          <span style={styles.citationIndexBadge}>[{c.citation_index}]</span>
                          <span style={styles.timestampBadge}>
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                              <polygon points="5 3 19 12 5 21 5 3" fill="currentColor" />
                            </svg>
                            {c.timestamp}
                          </span>
                          <span style={styles.leadInTag}>-5s lead-in</span>
                          <span style={styles.scoreTag}>Score: {Math.round(c.score * 100)}%</span>
                        </div>
                        <div style={styles.citationVideoTitle}>{c.video_title}</div>
                        {c.preview && <div style={styles.citationPreview}>&ldquo;{c.preview}...&rdquo;</div>}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {isSubmitting && (
          <div style={styles.loadingRow}>
            <div style={styles.loadingBubble}>
              <div style={styles.typingDot} />
              <div style={{ ...styles.typingDot, animationDelay: "0.2s" }} />
              <div style={{ ...styles.typingDot, animationDelay: "0.4s" }} />
              <span style={styles.loadingText}>Searching vector embeddings & checking guardrails...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div style={styles.inputArea}>
        <div style={styles.sampleChipsContainer}>
          <span style={styles.sampleLabel}>Suggested:</span>
          {samplePrompts.map((p, idx) => (
            <button
              key={idx}
              style={styles.sampleChip}
              onClick={() => handleSend(p)}
              disabled={isSubmitting}
            >
              {p}
            </button>
          ))}
        </div>

        <div style={styles.inputForm}>
          <input
            id="chat-input"
            type="text"
            style={styles.chatInput}
            placeholder="Ask a question about the lectures... (e.g. 'What was explained about tabulation?')"
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            disabled={isSubmitting}
          />
          <button
            id="chat-submit-button"
            style={{
              ...styles.sendButton,
              opacity: isSubmitting || !inputQuestion.trim() ? 0.6 : 1,
            }}
            disabled={isSubmitting || !inputQuestion.trim()}
            onClick={() => handleSend()}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" fill="currentColor" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    background: "var(--bg-card)",
    borderRadius: "var(--radius-lg)",
    border: "1px solid var(--border-subtle)",
    overflow: "hidden",
    boxShadow: "var(--shadow-md)",
    backdropFilter: "blur(16px)",
  },
  header: {
    padding: "16px 20px",
    borderBottom: "1px solid var(--border-subtle)",
    background: "rgba(0, 0, 0, 0.15)",
  },
  headerTitleWrapper: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  chatIcon: {
    width: "32px",
    height: "32px",
    borderRadius: "var(--radius-md)",
    background: "rgba(99, 102, 241, 0.15)",
    border: "1px solid rgba(99, 102, 241, 0.3)",
    color: "var(--primary)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: "0.95rem",
    fontWeight: 700,
    color: "#fff",
  },
  headerSubtitle: {
    fontSize: "0.75rem",
    color: "var(--text-muted)",
  },
  messageList: {
    flex: 1,
    overflowY: "auto",
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    maxHeight: "560px",
    minHeight: "400px",
  },
  messageRow: {
    display: "flex",
    width: "100%",
  },
  messageBubble: {
    maxWidth: "88%",
    borderRadius: "var(--radius-lg)",
    padding: "14px 18px",
    fontSize: "0.9rem",
    lineHeight: 1.6,
  },
  userBubble: {
    background: "linear-gradient(135deg, var(--primary) 0%, var(--primary-hover) 100%)",
    color: "#fff",
    borderBottomRightRadius: "4px",
    boxShadow: "0 4px 12px var(--primary-glow)",
  },
  assistantBubble: {
    background: "var(--bg-surface)",
    border: "1px solid var(--border-subtle)",
    color: "var(--text-main)",
    borderBottomLeftRadius: "4px",
    boxShadow: "var(--shadow-sm)",
  },
  messageText: {
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  refusalBadge: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "6px 12px",
    marginBottom: "10px",
    background: "rgba(245, 158, 11, 0.15)",
    border: "1px solid rgba(245, 158, 11, 0.4)",
    borderRadius: "var(--radius-sm)",
    color: "#fbbf24",
    fontSize: "0.76rem",
    fontWeight: 600,
  },
  citationSection: {
    marginTop: "14px",
    paddingTop: "12px",
    borderTop: "1px solid var(--border-subtle)",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  citationHeader: {
    fontSize: "0.72rem",
    fontWeight: 700,
    letterSpacing: "0.04em",
    color: "var(--text-dim)",
  },
  citationGrid: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  citationCard: {
    textAlign: "left",
    background: "rgba(255, 255, 255, 0.03)",
    border: "1px solid var(--border-subtle)",
    borderRadius: "var(--radius-md)",
    padding: "10px 12px",
    display: "flex",
    flexDirection: "column",
    gap: "5px",
    transition: "background 0.2s, border-color 0.2s, transform 0.15s",
  },
  citationCardTop: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexWrap: "wrap",
  },
  citationIndexBadge: {
    fontSize: "0.75rem",
    fontWeight: 700,
    color: "var(--primary)",
  },
  timestampBadge: {
    fontSize: "0.76rem",
    fontWeight: 700,
    background: "var(--accent-yt)",
    color: "#fff",
    padding: "2px 8px",
    borderRadius: "var(--radius-full)",
    display: "flex",
    alignItems: "center",
    gap: "4px",
    boxShadow: "0 2px 6px var(--accent-yt-glow)",
  },
  leadInTag: {
    fontSize: "0.7rem",
    color: "var(--text-dim)",
    background: "rgba(255, 255, 255, 0.05)",
    padding: "2px 6px",
    borderRadius: "var(--radius-sm)",
  },
  scoreTag: {
    fontSize: "0.7rem",
    color: "var(--success)",
    fontWeight: 600,
  },
  citationVideoTitle: {
    fontSize: "0.82rem",
    fontWeight: 600,
    color: "var(--text-main)",
  },
  citationPreview: {
    fontSize: "0.75rem",
    color: "var(--text-muted)",
    fontStyle: "italic",
    lineHeight: 1.3,
  },
  loadingRow: {
    display: "flex",
  },
  loadingBubble: {
    background: "var(--bg-surface)",
    border: "1px solid var(--border-subtle)",
    borderRadius: "var(--radius-lg)",
    padding: "12px 16px",
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  typingDot: {
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    background: "var(--primary)",
    animation: "liveDot 1.4s infinite ease-in-out",
  },
  loadingText: {
    fontSize: "0.78rem",
    color: "var(--text-muted)",
  },
  inputArea: {
    padding: "16px 20px",
    borderTop: "1px solid var(--border-subtle)",
    background: "rgba(0, 0, 0, 0.2)",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  sampleChipsContainer: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    flexWrap: "wrap",
    fontSize: "0.75rem",
  },
  sampleLabel: {
    color: "var(--text-dim)",
  },
  sampleChip: {
    background: "rgba(255, 255, 255, 0.04)",
    border: "1px solid var(--border-subtle)",
    color: "var(--text-muted)",
    padding: "3px 10px",
    borderRadius: "var(--radius-full)",
    fontSize: "0.74rem",
    transition: "background 0.2s, color 0.2s",
  },
  inputForm: {
    display: "flex",
    gap: "10px",
  },
  chatInput: {
    flex: 1,
    padding: "12px 16px",
    background: "var(--bg-deep)",
    border: "1px solid var(--border-subtle)",
    borderRadius: "var(--radius-md)",
    color: "var(--text-main)",
    fontSize: "0.88rem",
    outline: "none",
  },
  sendButton: {
    width: "44px",
    height: "44px",
    borderRadius: "var(--radius-md)",
    background: "linear-gradient(135deg, var(--primary) 0%, var(--primary-hover) 100%)",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 2px 10px var(--primary-glow)",
  },
};
