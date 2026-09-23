import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from src.vector_store import get_vector_store

# Load environment variables from apps/api/.env or workspace root .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()  # fallback to current working directory

REFUSAL_MESSAGE = "This topic was not covered in the indexed video lectures."
MIN_SIMILARITY_SCORE = float(os.getenv("MIN_SIMILARITY_SCORE", "0.50"))

SYSTEM_PROMPT = f"""You are an AI teaching assistant answering questions about YouTube video lectures using ONLY the transcript excerpts provided below.

Rules:
1. Answer using ONLY facts explicitly mentioned in the excerpts.
2. If the excerpts do not contain sufficient information to answer the question accurately, respond with EXACTLY:
   "{REFUSAL_MESSAGE}"
3. Cite your sources inline using [1], [2], etc., corresponding to the excerpt numbers provided.
4. Keep your answer concise, direct, and well-grounded (3 to 6 sentences maximum).
5. Match the language style of the user's question (e.g. if the user asks in Hinglish, respond in natural Hinglish).
6. Never invent a fact, timestamp, or video title."""

_CITATION_REGEX = re.compile(r"\[(\d+)\]")


def _call_gemini(system: str, prompt: str, model_name: str, api_key: str) -> str:
    """Call Google Gemini API via official google-genai SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
        ),
    )
    return (response.text or "").strip()


def _call_groq(system: str, prompt: str, model_name: str, api_key: str) -> str:
    """Call Groq API using groq client."""
    from groq import Groq

    client = Groq(api_key=api_key)
    chat_completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return (chat_completion.choices[0].message.content or "").strip()


def dispatch_llm(system: str, prompt: str) -> tuple[str, str, str]:
    """
    Route request to configured LLM provider (Gemini or Groq).
    Returns tuple: (response_text, provider_name, model_name)
    """
    provider = os.getenv("LLM_PROVIDER", "").lower()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    # Determine provider based on setting or available keys
    if provider == "groq" or (not gemini_key and groq_key):
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        text = _call_groq(system, prompt, model, groq_key)
        return text, "groq", model
    elif gemini_key:
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        text = _call_gemini(system, prompt, model, gemini_key)
        return text, "gemini", model
    elif groq_key:
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        text = _call_groq(system, prompt, model, groq_key)
        return text, "groq", model
    else:
        # Graceful fallback when no LLM key is configured
        fallback_msg = (
            "[API Key Note: No GEMINI_API_KEY or GROQ_API_KEY found in apps/api/.env. "
            "Showing top retrieved timestamps and excerpts below.]"
        )
        return fallback_msg, "none", "none"


def build_excerpts_context(hits: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into numbered excerpts for LLM grounding."""
    blocks = []
    for idx, hit in enumerate(hits, start=1):
        title = hit.get("video_title", "Video")
        time_str = hit.get("timestamp") or f"{int(hit.get('start', 0))}s"
        text = hit.get("text", "")
        blocks.append(f'[{idx}] "{title}" @ {time_str}\n{text}')
    return "\n\n".join(blocks)


def filter_and_renumber_citations(
    llm_output: str, hits: List[Dict[str, Any]]
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Keep ONLY the citations the model actually referenced in its answer,
    and renumber them sequentially (1..N).
    Prevents overwhelming the user with unused links and ensures strict grounding.
    """
    referenced_indices: List[int] = []
    for match in _CITATION_REGEX.finditer(llm_output):
        idx = int(match.group(1))
        if 1 <= idx <= len(hits) and idx not in referenced_indices:
            referenced_indices.append(idx)

    if not referenced_indices:
        return llm_output, []

    # Map original excerpt index to new sequential index: {2: 1, 4: 2, ...}
    remap = {old_idx: new_idx for new_idx, old_idx in enumerate(referenced_indices, start=1)}

    # Rewrite [2], [4] in text to [1], [2]
    rewritten_text = _CITATION_REGEX.sub(
        lambda m: f"[{remap[int(m.group(1))]}]" if int(m.group(1)) in remap else m.group(0),
        llm_output,
    )

    filtered_citations = []
    for old_idx in referenced_indices:
        hit = hits[old_idx - 1]
        filtered_citations.append(
            {
                "citation_index": remap[old_idx],
                "video_title": hit.get("video_title"),
                "timestamp": hit.get("timestamp"),
                "start_sec": hit.get("link_sec", int(hit.get("start", 0))),
                "video_id": hit.get("video_id"),
                "video_url": hit.get("video_url"),
                "score": hit.get("score"),
                "preview": (hit.get("body") or hit.get("text", ""))[:180].strip(),
            }
        )

    return rewritten_text, filtered_citations


def generate_answer(
    question: str,
    collection_name: str = "yt_transcripts",
    top_k: int = 5,
    min_score: float = MIN_SIMILARITY_SCORE,
    filter_video_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full Grounded RAG Generation Pipeline:
    1. Retrieves top-k semantically relevant chunks from Qdrant.
    2. Guardrail 1: If no chunks meet the min_score cutoff, refuse immediately without calling LLM.
    3. Builds grounded context and dispatches to LLM with strict system constraints.
    4. Guardrail 2: Checks if LLM produced the refusal string.
    5. Guardrail 3: Filters and renumbers only the citations the LLM explicitly referenced.
    """
    clean_question = question.strip()
    if not clean_question:
        return {
            "answer": REFUSAL_MESSAGE,
            "citations": [],
            "grounded": False,
            "refused": True,
            "retrieved_count": 0,
        }

    store = get_vector_store()
    raw_hits = store.search(
        query=clean_question,
        collection_name=collection_name,
        limit=top_k,
        filter_video_id=filter_video_id,
    )

    # Filter by minimum similarity score
    qualifying_hits = [h for h in raw_hits if h.get("score", 0.0) >= min_score]

    # GUARD 1: No retrieved chunks survived the score threshold -> Refuse immediately
    if not qualifying_hits:
        return {
            "answer": REFUSAL_MESSAGE,
            "citations": [],
            "grounded": False,
            "refused": True,
            "retrieved_count": len(raw_hits),
            "qualifying_count": 0,
            "reason": "No retrieved video segments met the minimum relevance threshold.",
        }

    # Format context for LLM
    context_str = build_excerpts_context(qualifying_hits)
    user_prompt = f"EXCERPTS:\n{context_str}\n\nQUESTION: {clean_question}"

    raw_answer, provider, model = dispatch_llm(SYSTEM_PROMPT, user_prompt)

    # If in fallback mode (no keys), return excerpts directly as citations
    if provider == "none":
        default_citations = [
            {
                "citation_index": i + 1,
                "video_title": h.get("video_title"),
                "timestamp": h.get("timestamp"),
                "start_sec": h.get("link_sec", int(h.get("start", 0))),
                "video_id": h.get("video_id"),
                "video_url": h.get("video_url"),
                "score": h.get("score"),
                "preview": (h.get("body") or h.get("text", ""))[:180].strip(),
            }
            for i, h in enumerate(qualifying_hits)
        ]
        return {
            "answer": raw_answer,
            "citations": default_citations,
            "grounded": False,
            "refused": False,
            "retrieved_count": len(raw_hits),
            "provider": provider,
            "model": model,
        }

    # GUARD 2: Did the LLM output the refusal message?
    if REFUSAL_MESSAGE.lower() in raw_answer.lower():
        return {
            "answer": REFUSAL_MESSAGE,
            "citations": [],
            "grounded": False,
            "refused": True,
            "retrieved_count": len(raw_hits),
            "provider": provider,
            "model": model,
        }

    # GUARD 3: Keep only citations actually cited by the LLM and renumber them
    final_answer, citations = filter_and_renumber_citations(raw_answer, qualifying_hits)

    return {
        "answer": final_answer,
        "citations": citations,
        "grounded": bool(citations),
        "refused": False,
        "retrieved_count": len(raw_hits),
        "qualifying_count": len(qualifying_hits),
        "provider": provider,
        "model": model,
    }


if __name__ == "__main__":
    q = input("Ask a question about the indexed videos: ").strip()
    if not q:
        q = "What is the message of the song?"
    res = generate_answer(q)
    print("\n--- Answer ---")
    print(res["answer"])
    print(f"\nGrounded: {res['grounded']} | Refused: {res['refused']}")
    print(f"Citations ({len(res['citations'])}):")
    for c in res["citations"]:
        print(f"  [{c['citation_index']}] {c['video_title']} @ {c['timestamp']} -> {c['video_url']}")
