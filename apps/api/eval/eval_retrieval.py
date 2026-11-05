"""Measure retrieval rank, timestamp accuracy, and retrieval cutoff behavior.

Usage from apps/api:
    uv run python eval/eval_retrieval.py --playlist-id YOUR_PLAYLIST_ID

By default it does not JIT transcribe missing videos or stop a running
background playlist ingestion job. Retrieval may still initialize the profile
collection and load the configured local reranker on its first use.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running from project root or apps/api.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.vector_store import get_vector_store


def _is_timestamp_hit(result: Dict[str, Any], expected_sec: int, tolerance_sec: int) -> bool:
    """Count a hit when the retrieved chunk overlaps the allowed time window."""
    start = float(result.get("start", result.get("link_sec", 0)))
    end = float(result.get("end", start))
    return start <= expected_sec + tolerance_sec and end >= expected_sec - tolerance_sec


def _is_runnable(case: Dict[str, Any]) -> bool:
    if not str(case.get("question", "")).strip():
        return False
    if case.get("expect_refusal") is True:
        return True
    expected_videos = case.get("expected_video_ids") or [case.get("expected_video_id")]
    if isinstance(expected_videos, str):
        expected_videos = [expected_videos]
    return bool(
        any(expected_videos)
        and case.get("expected_around_sec") is not None
    )


def run_eval(
    golden_path: str,
    top_k: int,
    collection: str,
    videos_collection: str,
    group: Optional[str],
    playlist_id: Optional[str],
    min_score: float,
    enable_jit: bool,
    disable_reranker: bool,
    json_out: Optional[str],
    strict: bool,
    min_hit_rate: float,
) -> int:
    golden_file = Path(golden_path)
    if not golden_file.exists():
        print(f"[ERROR] Golden file not found: {golden_path}", file=sys.stderr)
        return 2

    try:
        cases = json.loads(golden_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[ERROR] Could not read golden set: {exc}", file=sys.stderr)
        return 2
    if not isinstance(cases, list):
        print("[ERROR] Golden set must be a JSON list of cases.", file=sys.stderr)
        return 2

    available_groups = sorted({
        str(case["group"])
        for case in cases
        if isinstance(case, dict) and case.get("group")
    })
    if group and group not in available_groups:
        print(
            f"[ERROR] Unknown group '{group}'. Available groups: "
            f"{', '.join(available_groups) or '(none)'}",
            file=sys.stderr,
        )
        return 2

    selected_cases = [
        case for case in cases
        if isinstance(case, dict) and (group is None or case.get("group") == group)
    ]
    runnable = [case for case in selected_cases if _is_runnable(case)]
    skipped = len(selected_cases) - len(runnable)
    if not runnable:
        print(
            "[WARN] No complete evaluation cases found. Add expected_video_id(s) and "
            "expected_around_sec, or set expect_refusal=true. Check --group if one was selected."
        )
        return 0

    store = get_vector_store()
    if disable_reranker:
        store._reranker_model_name = "none"

    relevant_cases = 0
    refusal_cases = 0
    timestamp_hits = 0
    video_hits = 0
    reciprocal_ranks: List[float] = []
    refusal_correct = 0
    reports: List[Dict[str, Any]] = []
    language_metrics: Dict[str, Dict[str, Any]] = {}

    print(
        f"\nEvaluating {len(runnable)} cases against '{collection}' "
        f"(top_k={top_k}, group={group or 'all'}, JIT={'on' if enable_jit else 'off'})\n"
    )
    print(f"{'#':<4} {'RESULT':<9} {'RANK':<6} {'QUESTION':<58} EXPECTED")
    print("-" * 112)

    for index, case in enumerate(runnable, start=1):
        question = str(case.get("question", "")).strip()
        case_playlist = case.get("playlist_id") or playlist_id
        results = store.search(
            query=question,
            collection_name=collection,
            videos_collection=videos_collection,
            limit=top_k,
            filter_video_id=case.get("video_id"),
            filter_playlist_id=case_playlist,
            enable_jit=enable_jit,
            interrupt_background_ingest=False,
        )

        max_confidence = max(
            (float(hit.get("confidence_score", hit.get("score", 0.0))) for hit in results),
            default=0.0,
        )
        expected_refusal = case.get("expect_refusal") is True
        predicted_refusal = not any(
            float(hit.get("confidence_score", hit.get("score", 0.0))) >= min_score
            for hit in results
        )

        if expected_refusal:
            refusal_cases += 1
            case_passed = predicted_refusal
            refusal_correct += int(case_passed)
            result_label = "PASS" if case_passed else "FAIL"
            rank_label = "—"
            expected_label = "refuse"
        else:
            relevant_cases += 1
            query_language = str(case.get("query_language", "en")).strip().lower() or "unspecified"
            language_bucket = language_metrics.setdefault(
                query_language, {"cases": 0, "timestamp_hits": 0, "video_hits": 0, "reciprocal_ranks": []}
            )
            language_bucket["cases"] += 1
            expected_videos = case.get("expected_video_ids") or [case.get("expected_video_id")]
            if isinstance(expected_videos, str):
                expected_videos = [expected_videos]
            expected_videos = {str(video_id) for video_id in expected_videos if video_id}
            expected_sec = int(case["expected_around_sec"])
            tolerance = int(case.get("tolerance_sec", 60))
            video_rank = next(
                (rank for rank, hit in enumerate(results, start=1)
                 if str(hit.get("video_id")) in expected_videos),
                None,
            )
            timestamp_rank = next(
                (rank for rank, hit in enumerate(results, start=1)
                 if str(hit.get("video_id")) in expected_videos
                 and _is_timestamp_hit(hit, expected_sec, tolerance)),
                None,
            )
            if video_rank is not None:
                video_hits += 1
                language_bucket["video_hits"] += 1
            if timestamp_rank is not None:
                timestamp_hits += 1
                reciprocal_ranks.append(1.0 / timestamp_rank)
                language_bucket["timestamp_hits"] += 1
                language_bucket["reciprocal_ranks"].append(1.0 / timestamp_rank)
            else:
                reciprocal_ranks.append(0.0)
                language_bucket["reciprocal_ranks"].append(0.0)
            case_passed = timestamp_rank is not None
            result_label = "HIT" if case_passed else "MISS"
            rank_label = str(timestamp_rank) if timestamp_rank is not None else "—"
            expected_label = f"{','.join(sorted(expected_videos))}@{expected_sec}s"

        short_question = question[:55] + "..." if len(question) > 58 else question
        print(f"{index:<4} {result_label:<9} {rank_label:<6} {short_question:<58} {expected_label}")
        reports.append({
            "question": question,
            "query_language": case.get("query_language", "en"),
            "passed": case_passed,
            "expected_refusal": expected_refusal,
            "predicted_refusal": predicted_refusal,
            "expected_video_ids": sorted(expected_videos) if not expected_refusal else [],
            "expected_around_sec": case.get("expected_around_sec"),
            "video_rank": video_rank if not expected_refusal else None,
            "timestamp_rank": timestamp_rank if not expected_refusal else None,
            "max_confidence": round(max_confidence, 4),
            "results": [
                {
                    "video_id": hit.get("video_id"),
                    "video_title": hit.get("video_title"),
                    "start": hit.get("start"),
                    "end": hit.get("end"),
                    "score": hit.get("score"),
                    "confidence_score": hit.get("confidence_score"),
                    "rerank_score": hit.get("rerank_score"),
                }
                for hit in results
            ],
        })

    print("-" * 112)
    hit_rate = timestamp_hits / relevant_cases if relevant_cases else 0.0
    video_hit_rate = video_hits / relevant_cases if relevant_cases else 0.0
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    refusal_accuracy = refusal_correct / refusal_cases if refusal_cases else None
    metrics_by_language = {
        language: {
            "cases": values["cases"],
            "timestamp_hit_rate_at_k": values["timestamp_hits"] / values["cases"],
            "video_hit_rate_at_k": values["video_hits"] / values["cases"],
            "timestamp_mrr_at_k": sum(values["reciprocal_ranks"]) / values["cases"],
        }
        for language, values in sorted(language_metrics.items())
    }
    print(f"Timestamp Hit@{top_k}: {timestamp_hits}/{relevant_cases} ({hit_rate:.1%})")
    print(f"Video Hit@{top_k}:     {video_hits}/{relevant_cases} ({video_hit_rate:.1%})")
    print(f"Timestamp MRR@{top_k}:  {mrr:.3f}")
    for language, metrics in metrics_by_language.items():
        print(
            f"  {language}: timestamp Hit@{top_k}={metrics['timestamp_hit_rate_at_k']:.1%}, "
            f"video Hit@{top_k}={metrics['video_hit_rate_at_k']:.1%}, "
            f"MRR={metrics['timestamp_mrr_at_k']:.3f} (n={metrics['cases']})"
        )
    if refusal_accuracy is not None:
        print(f"Retrieval cutoff accuracy: {refusal_correct}/{refusal_cases} ({refusal_accuracy:.1%})")
    if skipped:
        print(f"Skipped incomplete golden cases: {skipped}")

    report = {
        "collection": collection,
        "group": group,
        "top_k": top_k,
        "min_score": min_score,
        "playlist_id": playlist_id,
        "jit_enabled": enable_jit,
        "reranker_disabled": disable_reranker,
        "metrics": {
            "timestamp_hit_rate_at_k": hit_rate,
            "video_hit_rate_at_k": video_hit_rate,
            "timestamp_mrr_at_k": mrr,
            "retrieval_cutoff_accuracy": refusal_accuracy,
            "relevant_cases": relevant_cases,
            "refusal_cases": refusal_cases,
            "skipped_cases": skipped,
            "by_query_language": metrics_by_language,
        },
        "cases": reports,
    }
    if json_out:
        output_path = Path(json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Detailed report saved to {output_path}")

    if strict and relevant_cases and hit_rate < min_hit_rate:
        print(f"[FAIL] Timestamp Hit@{top_k} is below required {min_hit_rate:.1%}.")
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate retrieval rank, timestamps, and cutoff behavior")
    parser.add_argument("--k", type=int, default=5, help="Number of transcript chunks to retrieve")
    parser.add_argument("--collection", default="yt_transcripts", help="Transcript collection")
    parser.add_argument("--videos-collection", default="yt_videos", help="Video registry collection")
    parser.add_argument("--group", help="Run only this golden-set group, such as strivers_a2z")
    parser.add_argument("--playlist-id", help="Limit all cases to a playlist")
    parser.add_argument("--golden", default="eval/golden.json", help="Golden JSON file")
    parser.add_argument("--min-score", type=float, default=0.50, help="Confidence cutoff for expected-refusal cases")
    parser.add_argument("--enable-jit", action="store_true", help="Allow evaluation to transcribe missing videos")
    parser.add_argument("--disable-reranker", action="store_true", help="Use rank fusion without cross-encoder reranking")
    parser.add_argument("--json-out", help="Write per-case results and metrics to this JSON file")
    parser.add_argument("--strict", action="store_true", help="Exit with an error when Hit@K is below the target")
    parser.add_argument("--min-hit-rate", type=float, default=0.80, help="Required Hit@K when --strict is set")
    args = parser.parse_args()

    if args.k < 1 or not 0.0 <= args.min_score <= 1.0 or not 0.0 <= args.min_hit_rate <= 1.0:
        parser.error("--k must be positive and score values must be between 0 and 1")
    raise SystemExit(run_eval(
        golden_path=args.golden,
        top_k=args.k,
        collection=args.collection,
        videos_collection=args.videos_collection,
        group=args.group,
        playlist_id=args.playlist_id,
        min_score=args.min_score,
        enable_jit=args.enable_jit,
        disable_reranker=args.disable_reranker,
        json_out=args.json_out,
        strict=args.strict,
        min_hit_rate=args.min_hit_rate,
    ))
