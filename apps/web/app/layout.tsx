import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "YouTube Lecture RAG — Timestamp-Grounded Retrieval Assistant",
  description: "Ask questions across YouTube video playlists with grounded answers, anti-hallucination guardrails, and in-page timestamp seeking.",
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
