import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "YT-RAG — Ask Questions About Any YouTube Playlist",
  description:
    "Paste a YouTube playlist URL, ingest it in seconds, and ask AI questions grounded in exact timestamps. Powered by FastAPI, Qdrant, yt-dlp, and Next.js.",
  openGraph: {
    title: "YT-RAG — YouTube Playlist AI Assistant",
    description:
      "Timestamp-grounded RAG for YouTube playlists. Multi-language captions, vector search, 3-tier hallucination guardrails.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
