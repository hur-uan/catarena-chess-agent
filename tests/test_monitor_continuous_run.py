import importlib
import json
from pathlib import Path
from typing import List, Optional


def _write_completed_round(
    round_dir: Path,
    *,
    generation_succeeded: bool = True,
    validator_passed: bool = True,
    changed: bool = True,
    parameter_action: str = "skipped",
    parameter_reason_code: str = "no_active_block",
    effective_changed_paths: Optional[List[str]] = None,
    illegal_moves: int = 0,
    timeouts: int = 0,
) -> None:
    round_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "battle.log",
        "ranking.csv",
        "error_report.json",
        "official_catarena_report.json",
        "catarena_context.json",
        "catarena_contract.json",
        "catarena_manifest.json",
        "strategy_profile_before.json",
        "strategy_profile_after.json",
    ):
        (round_dir / name).write_text("{}", encoding="utf-8")

    (round_dir / "evaluation_record.json").write_text(
        json.dumps(
            {
                "version": {
                    "generation_succeeded": generation_succeeded,
                    "validator_passed": validator_passed,
                    "repair_attempts": 1,
                    "candidate_backend": "profile",
                    "candidate_agent_path": "agents/candidates/fake.json",
                },
                "game_result_statistics": {
                    "rank": 1,
                    "win_rate": 1.0,
                    "games": 2,
                    "wins": 2,
                    "losses": 0,
                    "draws": 0,
                },
                "abnormal_events": {
                    "illegal_moves": illegal_moves,
                    "timeouts": timeouts,
                    "crashes": 0,
                    "runtime_errors": [],
                },
                "core_modification_summary": {
                    "changed": changed,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (round_dir / "parameter_record.json").write_text(
        json.dumps(
            {
                "effective_changed_paths": effective_changed_paths or [],
                "tuning": {
                    "action": parameter_action,
                    "reason_code": parameter_reason_code,
                    "selected_block": "",
                    "promoted_strategy_profile": False,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (round_dir / "round_record.json").write_text(
        json.dumps(
            {
                "version_identifier": {
                    "candidate_agent_promoted": False,
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (round_dir / "optimization_report.json").write_text("{}", encoding="utf-8")


def test_monitor_continuous_run_build_summary_counts_round_states(tmp_path):
    module = importlib.import_module("scripts.monitor_continuous_run")
    reports_dir = tmp_path / "reports"
    completed_dir = reports_dir / "live_profile_002"
    _write_completed_round(
        completed_dir,
        effective_changed_paths=["eval.mobility"],
    )

    in_progress_dir = reports_dir / "live_profile_003"
    in_progress_dir.mkdir(parents=True, exist_ok=True)
    (in_progress_dir / "battle.log").write_text("result win\n", encoding="utf-8")

    memory_path = tmp_path / "memory.jsonl"
    memory_path.write_text(
        json.dumps({"round_id": "live_profile_002"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    payload = module.build_summary(
        reports_dir=reports_dir,
        memory_path=memory_path,
        prefix="live_profile",
        start_round=2,
        round_count=3,
    )

    assert payload["aggregate"]["expected_count"] == 3
    assert payload["aggregate"]["completed_count"] == 1
    assert payload["aggregate"]["incomplete_count"] == 1
    assert payload["aggregate"]["missing_count"] == 1
    assert payload["aggregate"]["generation_succeeded_count"] == 1
    assert payload["aggregate"]["validator_passed_count"] == 1
    assert payload["aggregate"]["changed_candidate_count"] == 1
    assert payload["aggregate"]["effective_profile_change_count"] == 1
    assert payload["aggregate"]["repair_round_count"] == 1
    assert payload["aggregate"]["parameter_action_counts"] == {"skipped": 1}
    assert payload["rounds"][0]["status"] == "completed"
    assert payload["rounds"][0]["memory_seen"] is True
    assert payload["rounds"][1]["status"] == "in_progress"
    assert payload["rounds"][2]["status"] == "missing"


def test_monitor_continuous_run_build_summary_collects_failure_flags(tmp_path):
    module = importlib.import_module("scripts.monitor_continuous_run")
    reports_dir = tmp_path / "reports"
    failed_dir = reports_dir / "live_profile_002"
    _write_completed_round(
        failed_dir,
        generation_succeeded=False,
        validator_passed=False,
        changed=False,
        parameter_action="freeze",
        parameter_reason_code="negative_signal",
        illegal_moves=1,
        timeouts=1,
    )

    payload = module.build_summary(
        reports_dir=reports_dir,
        memory_path=tmp_path / "memory.jsonl",
        prefix="live_profile",
        start_round=2,
        round_count=1,
    )

    assert payload["aggregate"]["completed_count"] == 1
    assert payload["aggregate"]["generation_succeeded_count"] == 0
    assert payload["aggregate"]["validator_passed_count"] == 0
    assert payload["aggregate"]["changed_candidate_count"] == 0
    assert payload["aggregate"]["flag_counts"] == {
        "generation_failed": 1,
        "illegal_moves": 1,
        "timeouts": 1,
        "tuning_freeze_negative_signal": 1,
        "validator_failed": 1,
    }
    assert payload["rounds"][0]["flags"] == [
        "illegal_moves",
        "timeouts",
        "generation_failed",
        "validator_failed",
        "tuning_freeze_negative_signal",
    ]
