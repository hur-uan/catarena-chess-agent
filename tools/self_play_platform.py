"""Local self-play feedback source for the profile-only learning loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from tools.catarena_platform import CATArenaPlatformRun
from tools.serialization import to_plain_data
from tools.strategy_profile import DEFAULT_STRATEGY_PROFILE_PATH, load_strategy_profile
from tuning.match_runner import MatchConfig, MatchSummary, run_paired_match


class SelfPlayPlatformRun(BaseModel):
    passed: bool
    context_path: str
    contract_path: str
    manifest_path: str
    battle_log_path: str
    ranking_path: str
    error_report_path: str
    official_report_path: str
    games: int
    moves_played: int
    errors: List[str] = Field(default_factory=list)
    feedback_source: str = "self_play"
    aggregate_battle_log_path: str = ""


def run_self_play_learning_round(
    *,
    output_dir: Path = Path("reports/self_play"),
    strategy_profile_path: Path = DEFAULT_STRATEGY_PROFILE_PATH,
    pair_count: int = 8,
    time_limit_ms: int = 40,
    max_plies: int = 60,
    timeout_slack_ms: int = 5,
    timeout_slack_ratio: float = 0.20,
) -> SelfPlayPlatformRun:
    """Generate local self-play logs/ranking that match the optimizer feedback contract."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = output_dir / "battle_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    active_profile = load_strategy_profile(strategy_profile_path)
    config = MatchConfig(
        pair_count=max(1, pair_count),
        time_limit_ms=max(1, time_limit_ms),
        max_plies=max(1, max_plies),
        timeout_slack_ms=max(0, timeout_slack_ms),
        timeout_slack_ratio=max(0.0, timeout_slack_ratio),
        force_internal_engine=True,
    )
    summary = run_paired_match(active_profile, active_profile, config)

    aggregate_log_path = output_dir / "battle.log"
    ranking_path = output_dir / "ranking.csv"
    error_report_path = output_dir / "error_report.json"
    report_path = output_dir / "self_play_report.json"
    context_path = output_dir / "self_play_context.json"
    contract_path = output_dir / "self_play_contract.json"
    manifest_path = output_dir / "self_play_manifest.json"

    errors = _self_play_errors(summary)
    _write_game_logs(logs_dir, summary)
    aggregate_log_path.write_text(_aggregate_log_text(summary), encoding="utf-8")
    ranking_path.write_text(_ranking_csv(summary), encoding="utf-8")
    error_report_path.write_text(
        json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    context_path.write_text(
        json.dumps(
            {
                "feedback_source": "self_play",
                "strategy_profile_path": str(strategy_profile_path),
                "opponent_profile": "active_profile_mirror",
                "force_internal_engine": True,
                "pair_count": config.pair_count,
                "time_limit_ms": config.time_limit_ms,
                "timeout_threshold_ms": config.timeout_threshold_ms(),
                "timeout_slack_ms": config.timeout_slack_ms,
                "timeout_slack_ratio": config.timeout_slack_ratio,
                "max_plies": config.max_plies,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    contract_path.write_text(
        json.dumps(
            {
                "feedback_source": "self_play",
                "log_contract": "battle_logs/*.json, one game per file",
                "ranking_contract": "CATArena-compatible ranking.csv for chess_agent",
                "promotion_contract": "runtime code fixed; profile candidates pass local gates",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            [
                {"path": str(logs_dir), "role": "self_play_game_logs"},
                {"path": str(ranking_path), "role": "self_play_ranking"},
                {"path": str(report_path), "role": "self_play_summary"},
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                "feedback_source": "self_play",
                "summary": to_plain_data(summary),
                "stats": _score_self_play(summary),
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return SelfPlayPlatformRun(
        passed=not errors and summary.games > 0,
        context_path=str(context_path),
        contract_path=str(contract_path),
        manifest_path=str(manifest_path),
        battle_log_path=str(logs_dir),
        ranking_path=str(ranking_path),
        error_report_path=str(error_report_path),
        official_report_path=str(report_path),
        games=summary.games,
        moves_played=summary.player_a_moves + summary.player_b_moves,
        errors=errors,
        aggregate_battle_log_path=str(aggregate_log_path),
    )


def run_self_play_as_catarena_platform_round(**kwargs: Any) -> CATArenaPlatformRun:
    """Compatibility wrapper for call sites that only need the CATArena run shape."""
    run = run_self_play_learning_round(**kwargs)
    return CATArenaPlatformRun(
        passed=run.passed,
        context_path=run.context_path,
        contract_path=run.contract_path,
        manifest_path=run.manifest_path,
        battle_log_path=run.battle_log_path,
        ranking_path=run.ranking_path,
        error_report_path=run.error_report_path,
        official_report_path=run.official_report_path,
        games=run.games,
        moves_played=run.moves_played,
        errors=run.errors,
    )


def _write_game_logs(logs_dir: Path, summary: MatchSummary) -> None:
    for index, game in enumerate(summary.results, start=1):
        payload = {
            "game_id": f"self_play_{index:03d}",
            "feedback_source": "self_play",
            "result": game.result,
            "moves": game.plies,
            "opening_name": game.opening_name,
            "opening_fen": game.opening_fen,
            "player_a_color": game.player_a_color,
            "score_a": game.score_a,
            "adjudicated": game.adjudicated,
            "player_a_timeouts": game.player_a_timeouts,
            "player_b_timeouts": game.player_b_timeouts,
            "player_a_crashes": game.player_a_crashes,
            "player_b_crashes": game.player_b_crashes,
            "response_times_ms": game.response_times_ms,
            "error": game.error,
            "events": _events_for_game(game.model_dump()),
        }
        (logs_dir / f"game_{index:03d}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _aggregate_log_text(summary: MatchSummary) -> str:
    lines = [
        "feedback_source=self_play",
        "opponent=active_profile_mirror",
        f"games={summary.games}",
        f"score_a={summary.score_a}",
        f"mean_score_a={summary.mean_score_a}",
    ]
    for index, game in enumerate(summary.results, start=1):
        lines.append(
            (
                "game_id=self_play_%03d result=%s moves=%d opening=%s opening_fen=%s "
                "player_a_color=%s score_a=%.3f adjudicated=%s"
            )
            % (
                index,
                game.result,
                game.plies,
                game.opening_name,
                game.opening_fen,
                game.player_a_color,
                game.score_a,
                game.adjudicated,
            )
        )
    return "\n".join(lines) + "\n"


def _ranking_csv(summary: MatchSummary) -> str:
    stats = _score_self_play(summary)
    return (
        "agent,rank,games,wins,losses,draws,win_rate\n"
        "chess_agent,{rank},{games},{wins},{losses},{draws},{win_rate}\n"
    ).format(**stats)


def _score_self_play(summary: MatchSummary) -> Dict[str, Any]:
    win_rate = round(summary.mean_score_a, 4) if summary.games else 0.0
    return {
        "rank": 1 if summary.mean_score_a >= 0.5 else 2,
        "games": summary.games,
        "wins": summary.wins_a,
        "losses": summary.losses_a,
        "draws": summary.draws,
        "win_rate": win_rate,
    }


def _self_play_errors(summary: MatchSummary) -> List[str]:
    errors: List[str] = []
    if summary.player_a_crashes:
        errors.append(f"player_a crashes: {summary.player_a_crashes}")
    if summary.player_b_crashes:
        errors.append(f"player_b crashes: {summary.player_b_crashes}")
    return errors


def _events_for_game(game: Dict[str, Any]) -> List[str]:
    events: List[str] = []
    for key in ("player_a_timeouts", "player_b_timeouts"):
        events.extend(["timeout"] * int(game.get(key, 0)))
    for key in ("player_a_crashes", "player_b_crashes"):
        events.extend(["crash"] * int(game.get(key, 0)))
    if game.get("error"):
        events.append(str(game["error"]))
    return events
