import json
import subprocess
from pathlib import Path

import optimization.meta_agent as meta_agent
from tools.profile_regression import HistoricalRegressionReport
from tuning.autonomous_policy import AutonomousTuningReport, AutonomousTuningSeedResult
from tuning.prescreen import PrescreenSummary


def _install_fast_profile_mocks(monkeypatch):
    payload = json.loads(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    payload["search"]["tt_move_bonus"] += 1000
    monkeypatch.setattr(
        meta_agent,
        "run_autonomous_tuning_round",
        lambda **kwargs: AutonomousTuningReport(
            enabled=True,
            action="ready",
            reason_code="candidate_ready",
            reason="candidate ready",
            selected_block="search.history_order",
            gate_cross_count=1,
            positive_inner_count=1,
            safe_seed_count=1,
            chosen_seed=1,
            chosen_changed_paths=["search.tt_move_bonus"],
            seeds=[
                AutonomousTuningSeedResult(
                    seed=1,
                    score_difference=0.1,
                    prescreen_score_difference=0.1,
                    applied_change_count=1,
                    applied_change_paths=["search.tt_move_bonus"],
                    acceptance_prescreen_difference=0.05,
                    acceptance_mean_score_a=0.55,
                    sprt_decision="accept_h1",
                    proposed_profile=payload,
                )
            ],
        ),
    )
    monkeypatch.setattr(
        meta_agent,
        "_run_feedback_prescreen",
        lambda **kwargs: PrescreenSummary(
            positions=1,
            mean_score_a=0.6,
            mean_score_b=0.4,
            score_difference=0.2,
        ),
    )
    monkeypatch.setattr(
        meta_agent,
        "run_historical_regression",
        lambda *args, **kwargs: HistoricalRegressionReport(
            enabled=True,
            passed=True,
            notes=["no historical profiles selected"],
        ),
    )


def test_inspect_rounds_lists_recent_rounds(tmp_path, monkeypatch):
    _install_fast_profile_mocks(monkeypatch)
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(meta_agent, "DEFAULT_STRATEGY_PROFILE_PATH", strategy_path)

    log_path = tmp_path / "battle.log"
    log_path.write_text("result win\nelapsed_ms=12.5 depth=4 cp=22\n", encoding="utf-8")
    ranking_path = tmp_path / "ranking.csv"
    ranking_path.write_text(
        "agent,rank,games,wins,losses,draws,win_rate\nchess_agent,1,1,1,0,0,1.0\n",
        encoding="utf-8",
    )
    memory_path = tmp_path / "memory.jsonl"

    meta_agent.run_optimization_round(
        round_id="round_inspect_001",
        logs=log_path,
        ranking=ranking_path,
        memory_path=memory_path,
        next_agent_path=tmp_path / "candidate_profile.json",
    )

    output = subprocess.run(
        [
            str(Path(".venv/bin/python")),
            "scripts/inspect_rounds.py",
            "--memory",
            str(memory_path),
            "--limit",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    payload = json.loads(output.stdout)

    assert payload["mode"] == "list"
    assert payload["count"] == 1
    assert payload["rounds"][0]["round_id"] == "round_inspect_001"
    assert "artifact_paths" in payload["rounds"][0]
    assert "round_summary" in payload["rounds"][0]


def test_inspect_rounds_flags_suspicious_rounds(tmp_path):
    artifact_dir = tmp_path / "reports" / "round_x"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "round_record.json").write_text(
        json.dumps(
            {
                "round_id": "round_flagged",
                "version_identifier": {"candidate_agent_promoted": False},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (artifact_dir / "evaluation_record.json").write_text(
        json.dumps(
            {
                "game_result_statistics": {"rank": 2, "win_rate": 0.0, "games": 1},
                "version": {
                    "generation_succeeded": False,
                    "generation_error": "TimeoutError: simulated orchestration timeout",
                    "validator_passed": False,
                },
                "abnormal_events": {
                    "illegal_moves": 1,
                    "timeouts": 0,
                    "crashes": 0,
                    "runtime_errors": [],
                },
                "key_failure_positions": [],
                "next_round_revision_plan": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (artifact_dir / "parameter_record.json").write_text(
        json.dumps(
            {
                "effective_changed_paths": [],
                "tuning": {
                    "action": "freeze",
                    "reason_code": "no_gate_cross",
                    "selected_block": "search.history_order",
                    "promoted_strategy_profile": False,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    memory_path = tmp_path / "memory.jsonl"
    memory_path.write_text(
        json.dumps(
            {
                "round_id": "round_flagged",
                "artifact_paths": {
                    "round_record_path": str(artifact_dir / "round_record.json"),
                    "evaluation_record_path": str(artifact_dir / "evaluation_record.json"),
                    "parameter_record_path": str(artifact_dir / "parameter_record.json"),
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    output = subprocess.run(
        [
            str(Path(".venv/bin/python")),
            "scripts/inspect_rounds.py",
            "--memory",
            str(memory_path),
            "--mode",
            "flag",
            "--limit",
            "5",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    payload = json.loads(output.stdout)

    assert payload["mode"] == "flag"
    assert payload["count"] == 1
    flags = payload["rounds"][0]["flags"]
    assert "illegal_moves" in flags
    assert "generation_failed" in flags
    assert "validator_failed" in flags
    assert "tuning_freeze_no_gate_cross" in flags
