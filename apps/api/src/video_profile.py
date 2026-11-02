"""Build deterministic, transcript-grounded discovery profiles for videos."""

import math
import re
from collections import Counter
from typing import Any, Dict, List


_STOPWORDS = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "before", "being", "but", "by", "can", "cannot", "could", "did",
    "do", "does", "doing", "done", "during", "each", "few", "for", "from", "further", "get",
    "got", "had", "has", "have", "having", "he", "her", "here", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "just", "let", "like", "may", "me", "might",
    "more", "most", "my", "need", "no", "not", "now", "of", "off", "on", "once", "one", "only",
    "or", "other", "our", "out", "over", "own", "please", "right", "same", "say", "see", "she",
    "should", "so", "some", "such", "take", "tell", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "thing", "this", "those", "through", "to", "too", "try", "up", "use",
    "used", "using", "very", "want", "was", "we", "well", "were", "what", "when", "where", "which",
    "while", "who", "why", "will", "with", "would", "yeah", "yes", "you", "your", "okay", "ok",
    "guys", "guy", "alright", "actually", "basically", "going", "gonna", "kind", "know", "look",
    "make", "made", "mean", "means", "maybe", "right", "talk", "video", "welcome",
}


def _tokens(text: str) -> List[str]:
    return [word for word in re.findall(r"[\w+#.-]+", text.lower()) if len(word) > 1 and word not in _STOPWORDS]


def build_video_profile(title: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create searchable topics and a timestamped extractive summary from chunks."""
    normalized = []
    document_frequency: Counter[str] = Counter()
    term_frequency: Counter[str] = Counter()
    bigram_frequency: Counter[str] = Counter()

    for chunk in chunks:
        body = str(chunk.get("body") or "").strip()
        terms = _tokens(body)
        if not body or not terms:
            continue
        term_frequency.update(terms)
        document_frequency.update(set(terms))
        bigram_frequency.update(
            f"{left} {right}"
            for left, right in zip(terms, terms[1:])
            if left != right
        )
        normalized.append({**chunk, "body": body, "terms": set(terms)})

    if not normalized:
        return {"summary": title, "topics": [], "key_moments": []}

    chunk_count = len(normalized)
    title_terms = _tokens(title)
    term_scores = {
        term: (1.0 + math.log(count)) * math.log(1.0 + chunk_count / (1 + document_frequency[term]))
        for term, count in term_frequency.items()
    }
    for term in title_terms:
        if term in term_scores:
            term_scores[term] *= 1.35

    phrase_candidates = [
        (phrase, count * 1.4)
        for phrase, count in bigram_frequency.items()
        if count >= 2 and all(word not in _STOPWORDS for word in phrase.split())
    ]
    topics = [phrase for phrase, _ in sorted(phrase_candidates, key=lambda item: item[1], reverse=True)[:8]]
    topic_terms = [term for term, _ in sorted(term_scores.items(), key=lambda item: item[1], reverse=True)[:8]]
    for term in title_terms:
        if term not in topic_terms:
            topic_terms.append(term)
    topic_tags = list(dict.fromkeys(topics + topic_terms))[:12]

    ranked_chunks = []
    for chunk in normalized:
        score = sum(term_scores.get(term, 0.0) for term in chunk["terms"])
        ranked_chunks.append((score, chunk))
    ranked_chunks.sort(key=lambda item: item[0], reverse=True)

    key_moments = []
    chosen_terms: set[str] = set()
    for _, chunk in ranked_chunks:
        new_terms = chunk["terms"] - chosen_terms
        if key_moments and not new_terms:
            continue
        excerpt = re.sub(r"\s+", " ", chunk["body"]).strip()
        if len(excerpt) > 360:
            excerpt = excerpt[:357].rsplit(" ", 1)[0] + "..."
        key_moments.append({
            "chunk_id": chunk.get("chunk_id"),
            "timestamp": chunk.get("timestamp"),
            "start": chunk.get("start", 0),
            "excerpt": excerpt,
        })
        chosen_terms.update(chunk["terms"])
        if len(key_moments) >= 5:
            break

    summary = f"{title}. Main topics: {', '.join(topic_tags[:8])}."
    if key_moments:
        summary += " Key transcript moments: " + " ".join(
            f"[{moment['timestamp']}] {moment['excerpt']}" for moment in key_moments
        )

    return {"summary": summary, "topics": topic_tags, "key_moments": key_moments}
