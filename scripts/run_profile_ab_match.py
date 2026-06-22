from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.serialization import to_plain_data
from tools.strategy_profile import StrategyProfile, load_strategy_profile
from tuning.match_runner import MatchConfig, MatchSummary, OpeningPosition, run_paired_match


def summarize_match(summary: MatchSummary) -> Dict[str, Any]:
    scores = list(summary.game_scores_a)
    mean_score = float(summary.mean_score_a)
    score_stddev = statistics.pstdev(scores) if len(scores) > 1 else 0.0
    score_stderr = score_stddev / math.sqrt(len(scores)) if scores else 0.0
    ci95_half_width = 1.96 * score_stderr
    response_times = [
        float(elapsed)
        for game in summary.results
        for elapsed in game.response_times_ms
    ]
    return {
        "games": summary.games,
        "wins_a": summary.wins_a,
        "losses_a": summary.losses_a,
        "draws": summary.draws,
        "score_a": summary.score_a,
        "mean_score_a": mean_score,
        "score_stddev": score_stddev,
        "score_stderr": score_stderr,
        "score_ci95_low": max(0.0, mean_score - ci95_half_width),
        "score_ci95_high": min(1.0, mean_score + ci95_half_width),
        "elo_estimate_a": score_to_elo(mean_score),
        "player_a_moves": summary.player_a_moves,
        "player_b_moves": summary.player_b_moves,
        "player_a_timeouts": summary.player_a_timeouts,
        "player_b_timeouts": summary.player_b_timeouts,
        "player_a_crashes": summary.player_a_crashes,
        "player_b_crashes": summary.player_b_crashes,
        "timeout_rate_a": summary.timeout_rate_a(),
        "timeout_rate_b": summary.timeout_rate_b(),
        "average_response_ms": _mean(response_times),
        "p95_response_ms": _percentile(response_times, 0.95),
        "p99_response_ms": _percentile(response_times, 0.99),
        "max_response_ms": max(response_times) if response_times else 0.0,
        "adjudicated_games": sum(1 for game in summary.results if game.adjudicated),
        "error_games": sum(1 for game in summary.results if game.error),
        "by_opening": summarize_by_opening(summary),
    }


def summarize_by_opening(summary: MatchSummary) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[float]] = {}
    for game in summary.results:
        buckets.setdefault(game.opening_name, []).append(float(game.score_a))
    rows = []
    for opening_name in sorted(buckets):
        scores = buckets[opening_name]
        rows.append(
            {
                "opening_name": opening_name,
                "games": len(scores),
                "mean_score_a": _mean(scores),
                "wins_a": sum(1 for score in scores if score >= 0.99),
                "losses_a": sum(1 for score in scores if score <= 0.01),
                "draws": sum(1 for score in scores if 0.01 < score < 0.99),
            }
        )
    return rows


def score_to_elo(score: float) -> float:
    clipped = min(0.999, max(0.001, float(score)))
    return -400.0 * math.log10((1.0 / clipped) - 1.0)


def write_games_csv(path: Path, summary: MatchSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "game_index",
                "opening_name",
                "player_a_color",
                "result",
                "score_a",
                "plies",
                "adjudicated",
                "player_a_timeouts",
                "player_b_timeouts",
                "player_a_crashes",
                "player_b_crashes",
                "error",
            ],
        )
        writer.writeheader()
        for index, game in enumerate(summary.results, start=1):
            writer.writerow(
                {
                    "game_index": index,
                    "opening_name": game.opening_name,
                    "player_a_color": game.player_a_color,
                    "result": game.result,
                    "score_a": game.score_a,
                    "plies": game.plies,
                    "adjudicated": game.adjudicated,
                    "player_a_timeouts": game.player_a_timeouts,
                    "player_b_timeouts": game.player_b_timeouts,
                    "player_a_crashes": game.player_a_crashes,
                    "player_b_crashes": game.player_b_crashes,
                    "error": game.error,
                }
            )


def load_openings_file(path: Path) -> List[OpeningPosition]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_positions: Any
    if isinstance(payload, dict) and isinstance(payload.get("positions"), list):
        raw_positions = payload["positions"]
    elif isinstance(payload, list):
        raw_positions = payload
    else:
        raise ValueError("openings file must be a list or an object with a positions list")
    openings: List[OpeningPosition] = []
    for index, item in enumerate(raw_positions, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"opening #{index} is not an object")
        fen = str(item.get("fen", "")).strip()
        if not fen:
            raise ValueError(f"opening #{index} has no fen")
        name = str(item.get("name") or item.get("id") or f"opening_{index:03d}")
        openings.append(OpeningPosition(name=name, fen=fen))
    return openings


def apply_profile_overrides(
    profile: StrategyProfile,
    assignments: Iterable[str],
) -> StrategyProfile:
    payload = profile.model_dump()
    for assignment in assignments:
        key, separator, value = assignment.partition("=")
        if not separator:
            raise ValueError(f"profile override must be key=value: {assignment}")
        parts = [part for part in key.strip().split(".") if part]
        if not parts:
            raise ValueError(f"profile override has empty key: {assignment}")
        target: Dict[str, Any] = payload
        for part in parts[:-1]:
            child = target.get(part)
            if not isinstance(child, dict):
                raise ValueError(f"profile override path is not an object: {key}")
            target = child
        target[parts[-1]] = _parse_override_value(value)
    return StrategyProfile.model_validate(payload)


def _parse_override_value(value: str) -> Any:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        return stripped


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _percentile(values: Iterable[float], percentile: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, math.ceil(len(values) * percentile) - 1))
    return float(values[index])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a direct profile-vs-profile paired match.")
    parser.add_argument("--profile-a", type=Path, required=True)
    parser.add_argument("--profile-b", type=Path, required=True)
    parser.add_argument("--profile-a-set", action="append", default=[])
    parser.add_argument("--profile-b-set", action="append", default=[])
    parser.add_argument("--label-a", default="profile_a")
    parser.add_argument("--label-b", default="profile_b")
    parser.add_argument("--pair-count", type=int, default=32)
    parser.add_argument("--time-limit-ms", type=int, default=200)
    parser.add_argument("--timeout-slack-ms", type=int, default=5)
    parser.add_argument("--timeout-slack-ratio", type=float, default=5.0)
    parser.add_argument("--max-plies", type=int, default=20)
    parser.add_argument("--adjudication-cp", type=int, default=250)
    parser.add_argument(
        "--openings-file",
        type=Path,
        help="Optional JSON list, or feedback_fen_suite object with positions[].",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    profile_a = apply_profile_overrides(
        load_strategy_profile(args.profile_a),
        args.profile_a_set,
    )
    profile_b = apply_profile_overrides(
        load_strategy_profile(args.profile_b),
        args.profile_b_set,
    )
    openings = load_openings_file(args.openings_file) if args.openings_file else []
    config = MatchConfig(
        pair_count=args.pair_count,
        time_limit_ms=args.time_limit_ms,
        max_plies=args.max_plies,
        adjudication_cp=args.adjudication_cp,
        timeout_slack_ms=max(0, args.timeout_slack_ms),
        timeout_slack_ratio=max(0.0, args.timeout_slack_ratio),
        openings=openings,
    )
    summary = run_paired_match(profile_a, profile_b, config)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    games_csv_path = output_dir / "games.csv"
    write_games_csv(games_csv_path, summary)
    report = {
        "profile_a_path": str(args.profile_a),
        "profile_b_path": str(args.profile_b),
        "profile_a_overrides": list(args.profile_a_set),
        "profile_b_overrides": list(args.profile_b_set),
        "label_a": args.label_a,
        "label_b": args.label_b,
        "match_config": config.model_dump(),
        "summary": summarize_match(summary),
        "games_csv_path": str(games_csv_path),
        "raw_match_summary": to_plain_data(summary),
    }
    report_path = output_dir / "profile_ab_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
