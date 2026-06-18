"""Run one strategy-iteration round using self-play or official CATArena feedback."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optimization.meta_agent import run_optimization_round
from tools.catarena_platform import run_official_catarena_chess_round
from tools.memory_store import DEFAULT_MEMORY_PATH
from tools.self_play_platform import run_self_play_learning_round
from tools.serialization import to_plain_data


def _execution_backend(_: str) -> str:
    return "profile"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one self-play-backed round with the profile-only optimizer."
    )
    parser.add_argument("--round-id", required=True)
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
        help="Feedback generator for this learning round. Defaults to local self-play.",
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
        "--promote",
        action="store_true",
        help="Legacy compatibility flag: promote the strategy profile.",
    )
    parser.add_argument(
        "--promote-agent",
        action="store_true",
        help="Deprecated compatibility flag; runtime agent code is no longer promoted.",
    )
    parser.add_argument("--promote-profile", action="store_true")
    args = parser.parse_args()

    round_dir = args.reports_dir / args.round_id
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
    optimization_report = run_optimization_round(
        round_id=args.round_id,
        backend=args.backend,
        logs=Path(platform_run.battle_log_path),
        ranking=Path(platform_run.ranking_path),
        memory_path=args.memory,
        report_path=round_dir / "optimization_report.json",
        next_agent_path=Path("agents/candidates") / f"strategy_profile_{args.round_id}.json",
        strict_catarena=strict_catarena,
        max_repair_attempts=args.max_repair_attempts,
        promote_agent=args.promote_agent,
        promote_profile=args.promote_profile,
        promote=args.promote,
        optimizer_match_timeout_slack_ms=args.optimizer_match_timeout_slack_ms,
        optimizer_match_timeout_slack_ratio=args.optimizer_match_timeout_slack_ratio,
        tuning_block=args.tuning_block or None,
    )
    print(
        json.dumps(
            {
                "backend": _execution_backend(args.backend),
                "requested_backend": args.backend,
                "feedback_source": args.feedback_source,
                "memory_path": str(args.memory),
                "platform_run": to_plain_data(platform_run),
                "optimization_report": to_plain_data(optimization_report),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
