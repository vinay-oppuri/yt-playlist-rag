"""Generate answer examples and save a report for human grounding review.

Running this script may make one request per case to the configured LLM when
retrieval passes the evidence cutoff. It does not JIT transcribe videos or stop
background ingestion by default.
Automated checks validate grounding metadata and citation location, not factual
entailment; reviewers must check each claim in the saved JSON report.

Run from apps/api:
    uv run python eval/eval_answers.py --group campusx_fastapi
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.generator import generate_answer
from src.vector_store import get_vector_store


def citation_matches(case: Dict[str, Any], citations: List[Dict[str, Any]]) -> bool:
    expected_video_id = case.get("expected_video_id")
    expected_second = case.get("expected_around_sec")
    tolerance = int(case.get("tolerance_sec", 60))
    if not expected_video_id or expected_second is None:
        return bool(citations)
    return any(
        citation.get("video_id") == expected_video_id
        and abs(int(citation.get("start_sec", 0)) - int(expected_second)) <= tolerance
        for citation in citations
    )


def run_eval(
    golden_path: str,
    output_path: str,
    group: Optional[str],
    playlist_id: Optional[str],
    collection: str,
    videos_collection: str,
    top_k: int,
    min_score: float,
    enable_jit: bool,
    disable_reranker: bool,
    strict: bool,
) -> int:
    source = Path(golden_path)
    try:
        cases = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Could not load answer cases: {exc}", file=sys.stderr)
        return 2
    if not isinstance(cases, list):
        print("[ERROR] Answer cases must be a JSON list.", file=sys.stderr)
        return 2

    available_groups = sorted({
        str(case["group"])
        for case in cases if isinstance(case, dict) and case.get("group")
    })
    if group and group not in available_groups:
        print(f"[ERROR] Unknown group '{group}'. Available groups: {', '.join(available_groups)}", file=sys.stderr)
        return 2
    selected = [
        case for case in cases
        if isinstance(case, dict) and case.get("question")
        and (group is None or case.get("group") == group)
    ]
    if not selected:
        print("[WARN] No answer cases selected.")
        return 0

    store = get_vector_store()
    if disable_reranker:
        store._reranker_model_name = "none"

    reports: List[Dict[str, Any]] = []
    automated_passes = 0
    print(f"\nRunning {len(selected)} answer cases (group={group or 'all'})\n")
    for index, case in enumerate(selected, start=1):
        question = str(case["question"]).strip()
        try:
            result = generate_answer(
                question=question,
                collection_name=collection,
                videos_collection=videos_collection,
                top_k=top_k,
                min_score=min_score,
                filter_playlist_id=case.get("playlist_id") or playlist_id,
                enable_jit=enable_jit,
                interrupt_background_ingest=False,
            )
            citations = result.get("citations", [])
            citation_match = citation_matches(case, citations)
            automated_pass = bool(
                result.get("provider") not in (None, "none")
                and result.get("grounded")
                and not result.get("refused")
                and citation_match
            )
            automated_passes += int(automated_pass)
            report_case = {
                "question": question,
                "group": case.get("group"),
                "answer": result.get("answer", ""),
                "provider": result.get("provider"),
                "model": result.get("model"),
                "grounded": result.get("grounded"),
                "refused": result.get("refused"),
                "automated_citation_match": citation_match,
                "automated_pass": automated_pass,
                "expected_video_id": case.get("expected_video_id"),
                "expected_around_sec": case.get("expected_around_sec"),
                "expected_claims": case.get("expected_claims", []),
                "citations": citations,
                "human_review": {
                    "factual_support": None,
                    "citation_support": None,
                    "notes": "",
                },
            }
            print(f"{index}: {'PASS' if automated_pass else 'REVIEW'} | {question}")
        except Exception as exc:
            report_case = {
                "question": question,
                "group": case.get("group"),
                "automated_pass": False,
                "error": str(exc),
                "expected_claims": case.get("expected_claims", []),
                "human_review": {
                    "factual_support": None,
                    "citation_support": None,
                    "notes": "",
                },
            }
            print(f"{index}: ERROR | {question} | {exc}")
        reports.append(report_case)

    report = {
        "group": group,
        "playlist_id": playlist_id,
        "collection": collection,
        "top_k": top_k,
        "min_score": min_score,
        "jit_enabled": enable_jit,
        "case_count": len(selected),
        "automated_passes": automated_passes,
        "cases": reports,
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Automated checks passed: {automated_passes}/{len(selected)}")
    print(f"Human-review report saved to {target}")
    print("Review factual support and citation entailment manually.")
    return int(strict and automated_passes != len(selected))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review generated answer grounding and citations")
    parser.add_argument("--golden", default="eval/golden_answers.json")
    parser.add_argument("--json-out", default="eval/answer_report.json")
    parser.add_argument("--group")
    parser.add_argument("--playlist-id")
    parser.add_argument("--collection", default="yt_transcripts")
    parser.add_argument("--videos-collection", default="yt_videos")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=0.50)
    parser.add_argument("--enable-jit", action="store_true")
    parser.add_argument("--disable-reranker", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.top_k < 1 or not 0 <= args.min_score <= 1:
        parser.error("--top-k must be positive and --min-score must be between 0 and 1")
    raise SystemExit(run_eval(
        golden_path=args.golden,
        output_path=args.json_out,
        group=args.group,
        playlist_id=args.playlist_id,
        collection=args.collection,
        videos_collection=args.videos_collection,
        top_k=args.top_k,
        min_score=args.min_score,
        enable_jit=args.enable_jit,
        disable_reranker=args.disable_reranker,
        strict=args.strict,
    ))
