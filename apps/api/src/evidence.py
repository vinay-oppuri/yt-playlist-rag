"""Shared transcript-only evidence cutoff used by chat and retrieval evaluation."""

from typing import Any, Dict


def meets_transcript_evidence_cutoff(hit: Dict[str, Any], min_score: float) -> bool:
    """Apply a relevance cutoff with a guarded exact-transcript-match path.

    A short concept query may have weaker dense similarity despite an exact
    transcript match. Lexical overlap can help only when the chunk also clears
    a minimum dense similarity floor; title and profile matches never count.
    """
    confidence = float(hit.get("confidence_score", hit.get("score", 0.0)))
    if confidence >= min_score:
        return True
    lexical_match = float(hit.get("transcript_lexical_score", 0.0))
    semantic_match = float(hit.get("score", 0.0))
    semantic_floor = max(0.20, min_score * 0.4)
    return lexical_match >= 0.80 and semantic_match >= semantic_floor
