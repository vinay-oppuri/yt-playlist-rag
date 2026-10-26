"""
Retrieval Evaluation Script — Hit Rate @ K
==========================================
Measures how accurately the vector search retrieves the correct video
and timestamp for hand-crafted golden Q&A pairs.

Usage:
    cd apps/api
    uv run python eval/eval_retrieval.py [--k 5] [--collection yt_transcripts] [--golden eval/golden.json]

A retrieval is a HIT if:
  - The expected video_id is in the top-K results, AND
  - The retrieved start_sec is within ±tolerance_sec of expected_around_sec
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running from project root or apps/api
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.vector_store import get_vector_store


def run_eval(golden_path: str, top_k: int, collection: str) -> None:
    golden_file = Path(golden_path)
    if not golden_file.exists():
        print(f"[ERROR] Golden file not found: {golden_path}", file=sys.stderr)
        sys.exit(1)

    with open(golden_file, encoding="utf-8") as f:
        cases = json.load(f)

    # Filter to only entries that have been filled in
    runnable = [
        c for c in cases
        if c.get("expected_video_id") is not None and c.get("expected_around_sec") is not None
    ]

    if not runnable:
        print(
            "[WARN] No runnable test cases found.\n"
            "       Fill in 'expected_video_id' and 'expected_around_sec' in eval/golden.json\n"
            "       after ingesting your playlist, then re-run."
        )
        return

    store = get_vector_store()
    hits = 0
    total = len(runnable)

    print(f"\nRunning {total} eval cases against collection '{collection}' (top_k={top_k})\n")
    print(f"{'#':<4} {'HIT':<5} {'Score':<8} {'Question':<55} {'Expected'}")
    print("-" * 110)

    for idx, case in enumerate(runnable, start=1):
        question = case["question"]
        expected_vid = case["expected_video_id"]
        expected_sec = int(case["expected_around_sec"])
        tolerance = int(case.get("tolerance_sec", 60))

        results = store.search(query=question, collection_name=collection, limit=top_k)

        is_hit = False
        best_score = 0.0
        for r in results:
            best_score = max(best_score, r.get("score", 0.0))
            if r.get("video_id") == expected_vid:
                retrieved_sec = int(r.get("start", r.get("link_sec", 0)))
                if abs(retrieved_sec - expected_sec) <= tolerance:
                    is_hit = True
                    break

        if is_hit:
            hits += 1

        hit_label = "✅" if is_hit else "❌"
        q_short = question[:52] + "..." if len(question) > 55 else question
        print(f"{idx:<4} {hit_label:<5} {best_score:<8.4f} {q_short:<55} {expected_vid}@{expected_sec}s")

    hit_rate = hits / total * 100
    print("-" * 110)
    print(f"\nHit Rate @ {top_k}: {hits}/{total} = {hit_rate:.1f}%\n")

    if hit_rate >= 80:
        print("🟢 Retrieval quality is GOOD (≥80%)")
    elif hit_rate >= 60:
        print("🟡 Retrieval quality is FAIR (60–79%). Consider tuning chunk size or overlap.")
    else:
        print("🔴 Retrieval quality needs work (<60%). Try larger chunks, different embedding model, or review golden set.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate retrieval Hit Rate @ K")
    parser.add_argument("--k", type=int, default=5, help="Top-K results to check (default: 5)")
    parser.add_argument("--collection", type=str, default="yt_transcripts", help="Qdrant collection name")
    parser.add_argument("--golden", type=str, default="eval/golden.json", help="Path to golden.json")
    args = parser.parse_args()

    run_eval(golden_path=args.golden, top_k=args.k, collection=args.collection)
