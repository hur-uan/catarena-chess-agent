from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from optimization.meta_agent import run_optimization_round
from tools.catarena_platform import run_official_catarena_chess_round
from tools.memory_store import DEFAULT_MEMORY_PATH
from tools.self_play_platform import run_self_play_learning_round
from tools.serialization import to_plain_data


def _execution_backend(_: str) -> str:
    return "profile"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run multiple self-play-backed rounds using the profile-only optimizer."
    )
    parser.add_argument("--start-round", type=int, default=1)
    parser.add_argument("--round-count", type=int, default=5)
    parser.add_argument("--round-prefix", default="auto_round")
    parser.add_argument(
        "--backend",
        choices=["rule", "openai", "profile"],
        default="profile",
        help="Compatibility alias. All values execute the same profile-only optimizer.",
    )
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/catarena_platform"))
    parser.add_argument("--memory", type=Path, default=DEFAULT_MEMORY_PATH)
    parser.add_argument("--max-plies", type=int, default=80)
    parser.add_argument(
        "--feedback-source",
        choices=["self-play", "catarena"],
        default="self-play",
        help="Feedback generator for each learning round. Defaults to local self-play.",
    )
    parser.add_argument("--self-play-pairs", type=int, default=8)
    parser.add_argument("--self-play-time-limit-ms", type=int, default=40)
    parser.add_argument("--self-play-timeout-slack-ms", type=int, default=5)
    parser.add_argument("--self-play-timeout-slack-ratio", type=float, default=0.20)
    parser.add_argument("--optimizer-match-timeout-slack-ms", type=int, default=5)
    parser.add_argument("--optimizer-match-timeout-slack-ratio", type=float, default=0.20)
    parser.add_argument(
        "--tuning-block",
        default="",
        help="Optional active tuning block override for controlled experiments.",
    )
    parser.add_argument(
        "--max-repair-attempts",
        type=int,
        default=0,
        help="Deprecated compatibility flag. Code-repair loops are disabled.",
    )
    parser.add_argument(
        "--promote-agent",
        action="store_true",
        help="Deprecated compatibility flag; runtime agent code is no longer promoted.",
    )
    parser.add_argument("--promote-profile", action="store_true")
    args = parser.parse_args()

    rounds = []
    for offset in range(max(0, args.round_count)):
        round_number = args.start_round + offset
        round_id = f"{args.round_prefix}_{round_number:03d}"
        round_dir = args.reports_dir / round_id
        if args.feedback_source == "catarena":
            platform_run = run_official_catarena_chess_round(
                output_dir=round_dir,
                max_plies=args.max_plies,
            )
            strict_catarena = True
        else:
            platform_run = run_self_play_learning_round(
                output_dir=round_dir,
                pair_count=args.self_play_pairs,
                time_limit_ms=args.self_play_time_limit_ms,
                max_plies=args.max_plies,
                timeout_slack_ms=args.self_play_timeout_slack_ms,
                timeout_slack_ratio=args.self_play_timeout_slack_ratio,
            )
            strict_catarena = False
        round_payload: Dict[str, Any] = {
            "round_id": round_id,
            "feedback_source": args.feedback_source,
            "platform_run": to_plain_data(platform_run),
        }
        try:
            optimization_report = run_optimization_round(
                round_id=round_id,
                backend=args.backend,
                logs=Path(platform_run.battle_log_path),
                ranking=Path(platform_run.ranking_path),
                memory_path=args.memory,
                report_path=round_dir / "optimization_report.json",
                next_agent_path=Path("agents/candidates") / f"strategy_profile_{round_id}.json",
                strict_catarena=strict_catarena,
                max_repair_attempts=args.max_repair_attempts,
                promote_agent=args.promote_agent,
                promote_profile=args.promote_profile,
                optimizer_match_timeout_slack_ms=args.optimizer_match_timeout_slack_ms,
                optimizer_match_timeout_slack_ratio=args.optimizer_match_timeout_slack_ratio,
                tuning_block=args.tuning_block or None,
            )
            round_payload["optimization_report"] = to_plain_data(optimization_report)
        except Exception as exc:  # noqa: BLE001 - keep continuous runs alive across failed rounds.
            round_payload["optimization_failed"] = True
            round_payload["optimization_error"] = _format_exception(exc)
        rounds.append(round_payload)

    print(
        json.dumps(
            {
                "backend": _execution_backend(args.backend),
                "requested_backend": args.backend,
                "feedback_source": args.feedback_source,
                "memory_path": str(args.memory),
                "round_count": len(rounds),
                "promote_agent": args.promote_agent,
                "promote_profile": args.promote_profile,
                "rounds": rounds,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


if __name__ == "__main__":
    main()
