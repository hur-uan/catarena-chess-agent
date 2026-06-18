import json
from pathlib import Path

import optimization.meta_agent as meta_agent
from tools.memory_store import read_memory
from tools.opponent_pool import build_historical_profile_pool
from tools.profile_regression import HistoricalRegressionReport
from tools.strategy_profile import load_strategy_profile
from tuning.autonomous_policy import AutonomousTuningReport, AutonomousTuningSeedResult
from tuning.prescreen import PrescreenSummary


def _fake_tuning_report() -> AutonomousTuningReport:
    profile = load_strategy_profile(Path("config/strategy_profile.json"))
    payload = profile.model_dump()
    payload["search"]["tt_move_bonus"] += 1000
    return AutonomousTuningReport(
        enabled=True,
        action="ready",
        reason_code="candidate_ready",
        reason="candidate profile is ready for promotion",
        selected_block="search.history_order",
        gate_cross_count=1,
        positive_inner_count=1,
        negative_inner_count=0,
        positive_acceptance_prescreen_count=1,
        negative_acceptance_prescreen_count=0,
        safe_seed_count=1,
        chosen_seed=1,
        chosen_changed_paths=["search.tt_move_bonus"],
        seeds=[
            AutonomousTuningSeedResult(
                seed=1,
                score_difference=0.10,
                prescreen_score_difference=0.08,
                applied_change_count=1,
                applied_change_paths=["search.tt_move_bonus"],
                acceptance_prescreen_difference=0.05,
                acceptance_mean_score_a=0.55,
                sprt_decision="accept_h1",
                proposed_profile=payload,
            )
        ],
    )


def _install_fast_profile_mocks(monkeypatch):
    monkeypatch.setattr(
        meta_agent,
        "run_autonomous_tuning_round",
        lambda **kwargs: _fake_tuning_report(),
    )
    monkeypatch.setattr(
        meta_agent,
        "_run_feedback_prescreen",
        lambda **kwargs: PrescreenSummary(
            positions=1,
            mean_score_a=0.60,
            mean_score_b=0.40,
            score_difference=0.20,
        ),
    )
    monkeypatch.setattr(
        meta_agent,
        "run_historical_regression",
        lambda *args, **kwargs: HistoricalRegressionReport(
            enabled=True,
            total_profiles=0,
            passed_profiles=0,
            failed_profiles=0,
            passed=True,
            notes=["no historical profiles selected"],
        ),
    )


def test_optimization_round_writes_report_and_memory(tmp_path, monkeypatch):
    _install_fast_profile_mocks(monkeypatch)
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(meta_agent, "DEFAULT_STRATEGY_PROFILE_PATH", strategy_path)

    log_path = tmp_path / "game.log"
    log_path.write_text("result 1-0\nmoves e2e4 e7e5\n", encoding="utf-8")
    ranking_path = tmp_path / "ranking.csv"
    ranking_path.write_text("agent,rank,games,wins,losses,draws,win_rate\nchess_agent,1,1,1,0,0,1.0\n")
    report_path = tmp_path / "report.json"
    memory_path = tmp_path / "memory.jsonl"
    candidate_path = tmp_path / "candidate_profile.json"

    report = meta_agent.run_optimization_round(
        round_id="round_001",
        logs=log_path,
        ranking=ranking_path,
        memory_path=memory_path,
        report_path=report_path,
        next_agent_path=candidate_path,
    )

    assert report.round_id == "round_001"
    assert report.backend == "profile"
    assert report.log_report.total_games == 1
    assert report.ranking_summary.rank == 1
    assert report.validator_passed is True
    assert report.promotion_gate.passed is True
    assert report.generated_agent.path == str(candidate_path)
    assert candidate_path.exists()
    assert report_path.exists()
    assert read_memory(memory_path)[0]["round_id"] == "round_001"
    assert report.artifact_paths["round_record_path"]
    assert Path(report.artifact_paths["round_record_path"]).exists()
    assert Path(report.artifact_paths["evaluation_record_path"]).exists()
    assert Path(report.artifact_paths["parameter_record_path"]).exists()
    assert Path(report.artifact_paths["candidate_profile_path"]).exists()
    assert Path(report.artifact_paths["feedback_fen_suite_path"]).exists()

    round_record = json.loads(Path(report.artifact_paths["round_record_path"]).read_text(encoding="utf-8"))
    evaluation_record = json.loads(
        Path(report.artifact_paths["evaluation_record_path"]).read_text(encoding="utf-8")
    )
    parameter_record = json.loads(
        Path(report.artifact_paths["parameter_record_path"]).read_text(encoding="utf-8")
    )

    assert round_record["round_id"] == "round_001"
    assert round_record["optimization_mode"] == "profile_only"
    assert round_record["runtime_policy"] == "formal_internal_only"
    assert round_record["formal_execution_backend"] == "internal_engine"
    assert evaluation_record["game_result_statistics"]["rank"] == 1
    assert evaluation_record["optimization_mode"] == "profile_only"
    assert evaluation_record["runtime_policy"] == "formal_internal_only"
    assert evaluation_record["promotion_gate"]["passed"] is True
    assert parameter_record["optimization_mode"] == "profile_only"
    assert parameter_record["runtime_policy"] == "formal_internal_only"
    assert parameter_record["candidate_artifact"]["effective_changed_paths"] == [
        "search.tt_move_bonus"
    ]
    assert read_memory(memory_path)[0]["optimization_mode"] == "profile_only"
    assert read_memory(memory_path)[0]["runtime_policy"] == "formal_internal_only"


def test_optimization_round_can_promote_profile(tmp_path, monkeypatch):
    _install_fast_profile_mocks(monkeypatch)
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(meta_agent, "DEFAULT_STRATEGY_PROFILE_PATH", strategy_path)

    report = meta_agent.run_optimization_round(
        round_id="round_promote",
        memory_path=tmp_path / "memory.jsonl",
        next_agent_path=tmp_path / "candidate_profile.json",
        promote_profile=True,
    )

    payload = json.loads(strategy_path.read_text(encoding="utf-8"))
    assert report.generated_agent.promoted is True
    assert report.tuning_report.promoted_strategy_profile is True
    assert payload["search"]["tt_move_bonus"] == 51000


def test_optimization_round_persists_failed_profile_generation(tmp_path, monkeypatch):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(meta_agent, "DEFAULT_STRATEGY_PROFILE_PATH", strategy_path)
    monkeypatch.setattr(
        meta_agent,
        "run_autonomous_tuning_round",
        lambda **kwargs: (_ for _ in ()).throw(TimeoutError("simulated orchestration timeout")),
    )

    report = meta_agent.run_optimization_round(
        round_id="round_profile_failed",
        memory_path=tmp_path / "memory.jsonl",
        report_path=tmp_path / "optimization_report.json",
        next_agent_path=tmp_path / "candidate_profile.json",
    )

    assert report.generation_succeeded is False
    assert report.generated_agent.path == str(tmp_path / "candidate_profile.json")
    assert report.validator_passed is True
    assert "TimeoutError: simulated orchestration timeout" == report.generation_error
    assert Path(report.artifact_paths["candidate_profile_path"]).exists()


def test_optimization_round_creates_default_round_artifacts_near_logs(tmp_path, monkeypatch):
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

    report = meta_agent.run_optimization_round(
        round_id="round_default_artifacts",
        logs=log_path,
        ranking=ranking_path,
        memory_path=tmp_path / "memory.jsonl",
        next_agent_path=tmp_path / "candidate_profile.json",
    )

    assert (tmp_path / "optimization_report.json").exists()
    assert (tmp_path / "round_record.json").exists()
    assert (tmp_path / "evaluation_record.json").exists()
    assert (tmp_path / "parameter_record.json").exists()
    assert report.artifact_paths["optimization_report_path"] == str(
        tmp_path / "optimization_report.json"
    )


def test_historical_profile_pool_skips_legacy_rounds(tmp_path):
    legacy_profile = tmp_path / "legacy_strategy_profile_after.json"
    legacy_profile.write_text("{}", encoding="utf-8")
    legacy_eval = tmp_path / "legacy_evaluation_record.json"
    legacy_eval.write_text(
        json.dumps({"backend": "openai"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    legacy_param = tmp_path / "legacy_parameter_record.json"
    legacy_param.write_text("{}", encoding="utf-8")

    current_profile = tmp_path / "current_strategy_profile_after.json"
    current_profile.write_text("{}", encoding="utf-8")
    current_eval = tmp_path / "current_evaluation_record.json"
    current_eval.write_text(
        json.dumps(
            {
                "optimization_mode": "profile_only",
                "runtime_policy": "formal_internal_only",
                "formal_execution_backend": "internal_engine",
                "backend": "profile",
                "version": {"candidate_profile_path": "agents/candidates/current_profile.json"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    current_param = tmp_path / "current_parameter_record.json"
    current_param.write_text(
        json.dumps(
            {
                "optimization_mode": "profile_only",
                "runtime_policy": "formal_internal_only",
                "formal_execution_backend": "internal_engine",
                "candidate_artifact": {"backend": "profile"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    pool = build_historical_profile_pool(
        [
            {
                "round_id": "live_openai_safe_099",
                "artifact_paths": {
                    "strategy_profile_after_path": str(legacy_profile),
                    "evaluation_record_path": str(legacy_eval),
                    "parameter_record_path": str(legacy_param),
                },
            },
            {
                "round_id": "live_profile_001",
                "optimization_mode": "profile_only",
                "artifact_paths": {
                    "strategy_profile_after_path": str(current_profile),
                    "candidate_profile_path": "agents/candidates/current_profile.json",
                    "evaluation_record_path": str(current_eval),
                    "parameter_record_path": str(current_param),
                },
            },
        ],
        current_round_id="live_profile_002",
        limit=5,
    )

    assert [entry.round_id for entry in pool.selected_profiles] == ["live_profile_001"]
    assert any("skipped 1 legacy rounds" in note for note in pool.notes)
