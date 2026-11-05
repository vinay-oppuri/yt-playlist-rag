# YT-RAG Project Context and Accuracy Roadmap

This is the current working context for future development. It supplements the historical notes in `LEARNINGS_FROM_YTRAG.md`; if an older checklist there conflicts with the implementation described here, inspect the code and follow this document's current-state notes.

## Product goal

YT-RAG helps a learner ask questions about one video or an entire YouTube playlist and receive concise answers grounded in transcript excerpts with timestamps. A useful result must identify the right video and the moment where the explanation occurs. A refusal is better than a confident answer supported by unrelated text.

## Current architecture

- **Playlist registry:** `yt_videos` stores titles and metadata for fast routing across large playlists.
- **Transcript evidence:** `yt_transcripts` stores segment-aligned, timestamped chunks. These chunks are the only factual answer source.
- **Video profiles:** `yt_video_profiles` stores extractive summaries, topic tags and key moments for video discovery. Profiles may affect retrieval order, but must never be treated as answer evidence.
- **Retrieval:** query-aware FastEmbed vectors, Qdrant dense search, exact-token lexical candidates, video-profile ranks and reciprocal rank fusion form the candidate list. A local FastEmbed cross-encoder reranks the shortlist. A lexical MMR pass reduces near-duplicate transcript windows.
- **Grounded chat:** recent chat history may resolve references but is not evidence. The answer prompt requires transcript support and citations. Answers without valid excerpt citations fail closed.
- **Playlist ingestion:** titles are registered quickly; transcripts are loaded on demand. The durable queue for very large playlists remains deferred as requested.
- **Operations:** `RERANKER_MODEL` controls the local reranker. Its model downloads on first use; set it to `none` to use rank fusion without the cross-encoder.

## Accuracy rules

1. Keep playlist and video filters attached to every retrieval channel, including profile lookup.
2. Do not let profile rank, chat history, video titles or model knowledge satisfy the transcript evidence cutoff.
3. Cite every factual answer sentence. Refuse if an answer has no valid citations or references excerpts that were not provided.
4. Keep citation timestamps tied to the exact retrieved chunk. Preserve segment boundaries and the short player lead-in.
5. Rank fusion and cross-encoder scores order candidates; they are not calibrated probabilities. The answer cutoff must use transcript relevance signals and should be tuned against labeled cases.
6. Keep evaluation non-disruptive by default: no JIT transcription and no interruption of an active background ingestion job.

## Quality evaluation

Use `apps/api/eval/eval_retrieval.py` with `apps/api/eval/golden.json`. The current golden set has 20 timestamp labels sourced from cached FastAPI and Striver transcripts: 2 in `campusx_fastapi` and 18 in `strivers_a2z`. Five Striver cases are Hinglish queries against English lecture captions; `query_language` labels the query, not the caption. This is a useful seed, not enough evidence to claim production accuracy; grow each group to at least 20 reviewed questions. The evaluator reports:

- Timestamp Hit@K: correct video and an overlapping expected timestamp window.
- Video Hit@K: correct video appears in the top K.
- Timestamp MRR@K: rewards placing the correct timestamp near the top.
- Retrieval cutoff accuracy for cases marked `expect_refusal: true`. This measures the pre-LLM confidence guard, not the LLM refusal prompt.
- Optional per-case JSON output for comparing retrieval settings.
- Timestamp Hit@K, video Hit@K and MRR grouped by `query_language` (defaults to `en`).

Example case format:

```json
{
  "question": "Where does the lecture explain Pydantic validation?",
  "expected_video_id": "VIDEO_ID",
  "expected_around_sec": 767,
  "tolerance_sec": 90,
  "group": "campusx_fastapi",
  "playlist_id": "PLAYLIST_ID"
}
```

```json
{
  "question": "What is the capital of France?",
  "expect_refusal": true,
  "playlist_id": "PLAYLIST_ID"
}
```

Run from `apps/api` after indexing the videos in the selected group:

```powershell
uv run python eval/eval_retrieval.py --group strivers_a2z --playlist-id PLAYLIST_ID --json-out eval/results.json
```

The cases are grounded in cached transcripts, but each target video must also be indexed in the selected Qdrant collection before its case can pass. Expand each group with manually verified paraphrases, follow-ups, details and refusal cases before claiming broad accuracy or tuning cutoffs and ranking weights.

Generated-answer review cases live in `apps/api/eval/golden_answers.json`. Run `apps/api/eval/eval_answers.py` to generate answers and create a report with answer text, cited timestamps, expected claim checklist and blank human-review fields. Retrieval may call the configured LLM provider once per case when evidence passes the cutoff. The automatic pass only checks that the answer is marked grounded and cites the expected video/time. A person must review whether each claim is supported and whether its citation proves it.

```powershell
uv run python eval/eval_answers.py --group campusx_fastapi --json-out eval/answer_report.json
```

This command may make external LLM calls. JIT transcription and interruption of background ingestion are disabled by default. The referenced videos still need transcript vectors in Qdrant before the cases can produce useful results.

## Recommended next phases

### 1. Build a trustworthy golden set

- Label at least 20 answerable questions per representative playlist with the correct video and timestamp range.
- Add off-topic and in-playlist-but-uncovered questions for refusal checks.
- Record alternate acceptable videos or time ranges when the lecture repeats a topic.
- Compare Hit@K, MRR and refusal accuracy before changing ranking weights.

### 2. Expand generated-answer review

- Add more answer cases from each playlist and review generated reports with a person.
- Check factual support, citation correctness, timestamp precision and correct refusal separately.
- Test prompt injection in transcripts and follow-up history.
- Do not use citation presence alone as proof that every sentence is supported.

### 3. Improve language coverage

- The seed set now contains five Hinglish queries with transcript-checked expected video/time labels. Add Hindi-script queries only after reviewing suitable Hindi-captioned source videos; the current cached examples have English captions and do not measure Hindi-caption retrieval.
- Use the per-query-language metrics to measure English and Hinglish separately; grow each language slice before drawing conclusions.
- Compare candidate multilingual embeddings and rerankers against the same golden set before changing defaults.
- The configured cross-encoder defaults to `Xenova/ms-marco-MiniLM-L-6-v2`, an English MS MARCO reranker. Treat Hinglish results as a model coverage risk and compare multilingual candidates before changing defaults.
- Keep licensing, model size, first-query latency and re-embedding requirements in the decision.

### 4. Revisit durable ingestion later

When the deferred large-playlist work resumes, move sequential in-memory jobs to durable per-video jobs with retries, bounded concurrency, restart recovery and observable progress. Keep chat/JIT work independent so an interactive query cannot cancel an entire playlist job.

### 5. Add GraphRAG only when evidence calls for it

The existing per-video summaries and topic tags are a simpler first routing layer. Add a graph only when users need relationship queries across videos that profiles and transcript retrieval cannot answer, and evaluate graph routing against the same golden questions.

## Working conventions

- Treat transcripts as the source of truth; profiles and titles are routing metadata.
- Keep expensive model loading lazy and expose its configured/loaded/fallback state in health diagnostics.
- Avoid silently changing embeddings or thresholds without checking the evaluation report.
- Keep large-playlist durability deferred until explicitly resumed; improve retrieval and answer grounding first.
