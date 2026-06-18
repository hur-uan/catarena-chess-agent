"""Profile-only optimization orchestrator for CATArena chess rounds."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from agents.engine import analyze_with_stockfish
from tools.black_numba_config import black_numba_config_snapshot
from tools.catarena import check_catarena
from tools.catarena_platform import collect_catarena_platform_context
from tools.code_validator import validate_agent
from tools.failure_classifier import FailureReport, classify_failure
from tools.fen_suite import FenSuiteReport, build_feedback_fen_suite
from tools.log_parser import GameLogReport, parse_logs
from tools.memory_store import DEFAULT_MEMORY_PATH, append_memory, read_memory
from tools.opponent_pool import OpponentPoolReport, build_historical_profile_pool
from tools.opponent_reader import OpponentCodeReport, read_opponents
from tools.pipeline_metadata import (
    FORMAL_EXECUTION_BACKEND,
    OPTIMIZATION_MODE,
    PIPELINE_VERSION,
    RUNTIME_POLICY,
)
from tools.profile_regression import HistoricalRegressionReport, run_historical_regression
from tools.proposal_metrics import (
    EvolutionMetrics,
    ReliabilityMetrics,
    compute_evolution_metrics,
    compute_reliability_metrics,
)
from tools.ranking_analyzer import RankingSummary, analyze_ranking
from tools.serialization import to_plain_data
from tools.strategy_profile import (
    DEFAULT_STRATEGY_PROFILE_PATH,
    StrategyProfile,
    load_strategy_profile,
    strategy_profile_snapshot,
)
from tuning.autonomous_policy import AutonomousTuningReport, run_autonomous_tuning_round
from tuning.parameter_registry import load_tuning_registry
from tuning.prescreen import PrescreenConfig, PrescreenSummary, run_fen_prescreen

ProgressCallback = Callable[[str, str], None]
STABILITY_FIRST_FAILURES = {"interface_error", "illegal_move", "timeout"}
BACKEND_ALIASES = {
    "profile": "profile",
    "rule": "profile",
    "openai": "profile",
}
class CandidateArtifact(BaseModel):
    path: str = ""
    summary: str = ""
    changed: bool = False
    backend: str = "profile"
    promoted: bool = False
    archived_path: str = ""
    selected_block: str = ""
    effective_changed_paths: list[str] = Field(default_factory=list)


class PromotionGateReport(BaseModel):
    passed: bool = False
    reasons: list[str] = Field(default_factory=list)
    tuning_ready: bool = False
    feedback_prescreen_passed: bool = False
    historical_regression_passed: bool = False
    validator_passed: bool = False
    candidate_changed: bool = False


class OptimizationReport(BaseModel):
    round_id: str
    backend: str
    catarena_ready: bool
    catarena_message: str
    log_report: GameLogReport
    ranking_summary: RankingSummary
    opponent_report: OpponentCodeReport
    failure_report: FailureReport
    reliability_metrics: ReliabilityMetrics
    evolution_metrics: EvolutionMetrics
    generated_agent: CandidateArtifact = Field(default_factory=CandidateArtifact)
    generation_succeeded: bool = True
    generation_error: str = ""
    validator_passed: bool
    repair_attempts: int = 0
    improvement_summary: str
    patch_plan: str
    memory_records_seen: int
    state_summary: Dict[str, Any] = Field(default_factory=dict)
    stockfish_diagnostics: Dict[str, Any] = Field(default_factory=dict)
    engine_runtime_config: Dict[str, Any] = Field(default_factory=dict)
    catarena_source_files_seen: int = 0
    catarena_missing_required_files: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    tuning_report: AutonomousTuningReport = Field(default_factory=AutonomousTuningReport)
    feedback_fen_suite: FenSuiteReport = Field(default_factory=FenSuiteReport)
    feedback_prescreen: PrescreenSummary = Field(default_factory=PrescreenSummary)
    historical_profile_pool: OpponentPoolReport = Field(default_factory=OpponentPoolReport)
    historical_regression: HistoricalRegressionReport = Field(
        default_factory=HistoricalRegressionReport
    )
    promotion_gate: PromotionGateReport = Field(default_factory=PromotionGateReport)
    artifact_paths: Dict[str, str] = Field(default_factory=dict)


def run_optimization_round(
    round_id: str,
    logs: Optional[Path] = None,
    ranking: Optional[Path] = None,
    opponents: Optional[Path] = None,
    agent_path: Path = Path("agents/chess_agent.py"),
    memory_path: Path = DEFAULT_MEMORY_PATH,
    report_path: Optional[Path] = None,
    next_agent_path: Optional[Path] = None,
    strict_catarena: bool = False,
    backend: str = "profile",
    max_repair_attempts: int = 0,
    promote_agent: bool = False,
    promote_profile: bool = False,
    promote: Optional[bool] = None,
    optimizer_match_timeout_slack_ms: int = 5,
    optimizer_match_timeout_slack_ratio: float = 0.20,
    tuning_block: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> OptimizationReport:
    if promote is not None:
        promote_profile = promote_profile or promote

    _progress(progress_callback, "reading_feedback", "Reading logs, ranking, memory, and profile")
    strategy_profile_before = strategy_profile_snapshot(DEFAULT_STRATEGY_PROFILE_PATH)
    active_profile = load_strategy_profile(DEFAULT_STRATEGY_PROFILE_PATH)
    memory_records = read_memory(memory_path)

    catarena_status = check_catarena()
    if strict_catarena and not catarena_status.has_chessgame:
        raise RuntimeError(catarena_status.message)

    catarena_platform = None
    if catarena_status.has_chessgame:
        _progress(progress_callback, "reading_feedback", "Reading official CATArena files")
        catarena_platform = collect_catarena_platform_context()

    log_report = parse_logs(logs)
    ranking_summary = analyze_ranking(ranking, memory_path)
    opponent_report = read_opponents(opponents)

    _progress(progress_callback, "validating", "Validating active playing agent interface")
    validator_report = validate_agent(agent_path, run_pytest=False, run_ruff=True)
    failure_report = classify_failure(log_report, ranking_summary, validator_report.passed)
    reliability_metrics = compute_reliability_metrics(log_report)
    evolution_metrics = compute_evolution_metrics(ranking_summary, str(memory_path))
    improvement_summary = _build_improvement_summary(failure_report, ranking_summary)
    patch_plan = _build_patch_plan(failure_report)
    feedback_fen_suite = build_feedback_fen_suite(log_report)
    historical_profile_pool = build_historical_profile_pool(
        memory_records,
        current_round_id=round_id,
    )
    stockfish_diagnostics = _stockfish_diagnostics(log_report)
    state_summary = _state_summary(
        log_report=log_report,
        ranking_summary=ranking_summary,
        memory_records=memory_records,
        fen_suite=feedback_fen_suite,
        historical_profile_pool=historical_profile_pool,
    )
    engine_runtime_config = black_numba_config_snapshot()

    normalized_backend = _normalize_backend(backend)
    execution_backend = "profile"
    generation_succeeded = True
    generation_error = ""
    tuning_report = AutonomousTuningReport()
    feedback_prescreen = PrescreenSummary()
    historical_regression = HistoricalRegressionReport()
    promotion_gate = PromotionGateReport(validator_passed=validator_report.passed)
    candidate_artifact = CandidateArtifact(backend=normalized_backend)
    candidate_profile: Optional[StrategyProfile] = None

    try:
        _progress(
            progress_callback,
            "generating",
            "Generating profile candidate from tuning policy",
        )
        tuning_report = run_autonomous_tuning_round(
            round_id=round_id,
            failure_type=failure_report.main_failure_type,
            memory_records=memory_records,
            match_timeout_slack_ms=optimizer_match_timeout_slack_ms,
            match_timeout_slack_ratio=optimizer_match_timeout_slack_ratio,
            selected_block=tuning_block,
            promote=False,
        )
        candidate_artifact, candidate_profile = _build_candidate_artifact(
            round_id=round_id,
            tuning_report=tuning_report,
            baseline_profile=active_profile,
        )
        if candidate_profile is not None:
            _progress(progress_callback, "prescreen", "Running feedback-driven FEN prescreen")
            feedback_prescreen = _run_feedback_prescreen(
                candidate_profile=candidate_profile,
                baseline_profile=active_profile,
                tuning_report=tuning_report,
                fen_suite=feedback_fen_suite,
            )
            _progress(progress_callback, "regression", "Running historical profile regression")
            historical_regression = run_historical_regression(
                candidate_profile,
                historical_profile_pool,
            )
        else:
            historical_regression = HistoricalRegressionReport(
                enabled=False,
                notes=["no candidate profile produced by tuning policy"],
            )
        promotion_gate = _evaluate_promotion_gate(
            tuning_report=tuning_report,
            feedback_prescreen=feedback_prescreen,
            historical_regression=historical_regression,
            validator_passed=validator_report.passed,
            candidate_changed=candidate_artifact.changed,
        )
    except Exception as exc:  # noqa: BLE001 - archive orchestration failures in report artifacts.
        generation_succeeded = False
        generation_error = _format_exception(exc)
        candidate_artifact = CandidateArtifact(
            summary="Profile candidate orchestration failed before candidate materialized.",
            changed=False,
            backend=execution_backend,
        )
        tuning_report = AutonomousTuningReport(
            action="skipped",
            reason_code="orchestration_failed",
            reason=generation_error,
        )
        feedback_prescreen = PrescreenSummary()
        historical_regression = HistoricalRegressionReport(
            enabled=False,
            passed=False,
            notes=[generation_error],
        )
        promotion_gate = PromotionGateReport(
            passed=False,
            reasons=[generation_error],
            validator_passed=validator_report.passed,
        )

    risks = _collect_risks(
        catarena_status_message=catarena_status.message,
        catarena_ready=catarena_status.has_chessgame,
        catarena_platform=catarena_platform,
        validator_passed=validator_report.passed,
        generation_succeeded=generation_succeeded,
        generation_error=generation_error,
        promote_agent=promote_agent,
        promotion_gate=promotion_gate,
        candidate_changed=candidate_artifact.changed,
    )

    if (
        promote_profile
        and candidate_profile is not None
        and candidate_artifact.changed
        and promotion_gate.passed
    ):
        _progress(progress_callback, "promoting", "Promoting validated strategy profile candidate")
        archived_path = _promote_strategy_profile(
            proposed_profile=candidate_profile.model_dump(),
            strategy_profile_path=DEFAULT_STRATEGY_PROFILE_PATH,
            round_id=round_id,
        )
        candidate_artifact.promoted = True
        candidate_artifact.archived_path = str(archived_path) if archived_path is not None else ""
        tuning_report.action = "promote"
        tuning_report.promoted_strategy_profile = True
        tuning_report.promoted_profile_path = str(DEFAULT_STRATEGY_PROFILE_PATH)
        tuning_report.archived_profile_path = candidate_artifact.archived_path

    strategy_profile_after = strategy_profile_snapshot(DEFAULT_STRATEGY_PROFILE_PATH)
    report = OptimizationReport(
        round_id=round_id,
        backend=normalized_backend,
        catarena_ready=catarena_status.has_chessgame,
        catarena_message=catarena_status.message,
        log_report=log_report,
        ranking_summary=ranking_summary,
        opponent_report=opponent_report,
        failure_report=failure_report,
        reliability_metrics=reliability_metrics,
        evolution_metrics=evolution_metrics,
        generated_agent=candidate_artifact,
        generation_succeeded=generation_succeeded,
        generation_error=generation_error,
        validator_passed=validator_report.passed,
        repair_attempts=max(0, int(max_repair_attempts)) * 0,
        improvement_summary=improvement_summary,
        patch_plan=patch_plan,
        memory_records_seen=len(memory_records),
        state_summary=state_summary,
        stockfish_diagnostics=stockfish_diagnostics,
        engine_runtime_config=engine_runtime_config,
        catarena_source_files_seen=(
            len(catarena_platform.source_files) if catarena_platform is not None else 0
        ),
        catarena_missing_required_files=(
            catarena_platform.missing_required_files if catarena_platform is not None else []
        ),
        risks=risks,
        tuning_report=tuning_report,
        feedback_fen_suite=feedback_fen_suite,
        feedback_prescreen=feedback_prescreen,
        historical_profile_pool=historical_profile_pool,
        historical_regression=historical_regression,
        promotion_gate=promotion_gate,
    )

    resolved_report_path = _resolve_report_path(report_path=report_path, logs=logs, ranking=ranking)
    if resolved_report_path is not None:
        report.artifact_paths = _persist_round_artifacts(
            report=report,
            artifact_dir=resolved_report_path.parent,
            report_path=resolved_report_path,
            agent_path=Path(agent_path),
            logs=logs,
            ranking=ranking,
            opponents=opponents,
            strategy_profile_before=strategy_profile_before,
            strategy_profile_after=strategy_profile_after,
            candidate_profile=candidate_profile,
            candidate_hint_path=next_agent_path,
        )

    append_memory(_memory_record(report), memory_path)
    if resolved_report_path is not None:
        _progress(progress_callback, "writing_report", "Writing optimization report")
        resolved_report_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_report_path.write_text(
            json.dumps(to_plain_data(report), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return report


def _normalize_backend(backend: str) -> str:
    return BACKEND_ALIASES.get(backend.lower().strip(), "profile")


def _build_candidate_artifact(
    *,
    round_id: str,
    tuning_report: AutonomousTuningReport,
    baseline_profile: StrategyProfile,
) -> tuple[CandidateArtifact, Optional[StrategyProfile]]:
    seed = _select_candidate_seed(tuning_report)
    if seed is None or not seed.proposed_profile:
        return (
            CandidateArtifact(
                summary="No profile candidate produced by the tuning policy.",
                changed=False,
                backend="profile",
                selected_block=tuning_report.selected_block,
            ),
            None,
        )

    candidate_profile = StrategyProfile.model_validate(seed.proposed_profile)
    baseline = _without_source(baseline_profile.model_dump())
    candidate = _without_source(candidate_profile.model_dump())
    effective_changes = _diff_dicts(baseline, candidate)
    changed_paths = [item["path"] for item in effective_changes]
    summary = (
        f"Profile candidate for {round_id} from block "
        f"{tuning_report.selected_block or 'unknown'} using seed {seed.seed}."
    )
    return (
        CandidateArtifact(
            summary=summary,
            changed=bool(changed_paths),
            backend="profile",
            selected_block=tuning_report.selected_block,
            effective_changed_paths=changed_paths,
        ),
        candidate_profile,
    )


def _select_candidate_seed(
    tuning_report: AutonomousTuningReport,
):
    if tuning_report.chosen_seed:
        for seed in tuning_report.seeds:
            if seed.seed == tuning_report.chosen_seed and seed.proposed_profile:
                return seed
    candidates = [seed for seed in tuning_report.seeds if seed.proposed_profile]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            item.score_difference,
            item.acceptance_prescreen_difference,
            item.acceptance_mean_score_a,
            item.applied_change_count,
        ),
    )


def _run_feedback_prescreen(
    *,
    candidate_profile: StrategyProfile,
    baseline_profile: StrategyProfile,
    tuning_report: AutonomousTuningReport,
    fen_suite: FenSuiteReport,
) -> PrescreenSummary:
    signal_mode = "line_quality"
    prescreen_set = ""
    prescreen_time_limit_ms = 40
    if tuning_report.selected_block:
        try:
            block = load_tuning_registry().block(tuning_report.selected_block)
        except KeyError:
            block = None
        if block is not None:
            signal_mode = block.signal_mode or signal_mode
            prescreen_set = block.prescreen_set
            prescreen_time_limit_ms = block.prescreen_time_limit_ms or prescreen_time_limit_ms
    return run_fen_prescreen(
        candidate_profile,
        baseline_profile,
        baseline_profile=baseline_profile,
        config=PrescreenConfig(
            candidate_time_limit_ms=prescreen_time_limit_ms,
            oracle_time_limit_ms=max(60, prescreen_time_limit_ms * 3),
            signal_mode=signal_mode,
            prescreen_set=prescreen_set,
            positions=fen_suite.as_prescreen_positions(),
        ),
    )


def _evaluate_promotion_gate(
    *,
    tuning_report: AutonomousTuningReport,
    feedback_prescreen: PrescreenSummary,
    historical_regression: HistoricalRegressionReport,
    validator_passed: bool,
    candidate_changed: bool,
) -> PromotionGateReport:
    tuning_ready = tuning_report.action in {"ready", "promote"}
    feedback_prescreen_passed = feedback_prescreen.score_difference >= 0.0
    historical_regression_passed = historical_regression.passed

    gate = PromotionGateReport(
        passed=False,
        tuning_ready=tuning_ready,
        feedback_prescreen_passed=feedback_prescreen_passed,
        historical_regression_passed=historical_regression_passed,
        validator_passed=validator_passed,
        candidate_changed=candidate_changed,
    )
    if not validator_passed:
        gate.reasons.append("active agent failed validation")
    if not candidate_changed:
        gate.reasons.append("candidate profile made no effective change")
    if not tuning_ready:
        gate.reasons.append(
            f"tuning policy did not mark candidate ready: {tuning_report.action or 'skipped'}"
        )
    if candidate_changed and not feedback_prescreen_passed:
        gate.reasons.append("feedback FEN prescreen did not beat or match baseline")
    if candidate_changed and not historical_regression_passed:
        gate.reasons.append("historical profile regression gate failed")
    gate.passed = not gate.reasons
    return gate


def _collect_risks(
    *,
    catarena_status_message: str,
    catarena_ready: bool,
    catarena_platform: Any,
    validator_passed: bool,
    generation_succeeded: bool,
    generation_error: str,
    promote_agent: bool,
    promotion_gate: PromotionGateReport,
    candidate_changed: bool,
) -> list[str]:
    risks: list[str] = []
    if not catarena_ready:
        risks.append(catarena_status_message)
    if catarena_platform is not None and catarena_platform.missing_required_files:
        risks.append("required CATArena files missing from checkout")
    if not validator_passed:
        risks.append("active agent failed validation")
    if not generation_succeeded:
        risks.append(f"profile candidate orchestration failed: {generation_error}")
    if promote_agent:
        risks.append("agent code promotion is disabled in the profile-only pipeline")
    if candidate_changed and not promotion_gate.passed:
        risks.extend(promotion_gate.reasons)
    return risks


def _state_summary(
    *,
    log_report: GameLogReport,
    ranking_summary: RankingSummary,
    memory_records: list[dict[str, Any]],
    fen_suite: FenSuiteReport,
    historical_profile_pool: OpponentPoolReport,
) -> Dict[str, Any]:
    return {
        "round_games": log_report.total_games,
        "round_actions": log_report.total_actions,
        "key_failure_fens": log_report.key_failure_fens[:10],
        "average_response_ms": log_report.average_response_ms,
        "average_depth": log_report.average_depth,
        "average_cp": log_report.average_cp,
        "current_rank": ranking_summary.rank,
        "current_win_rate": ranking_summary.win_rate,
        "memory_versions_seen": len(memory_records),
        "feedback_fen_positions": fen_suite.total_positions,
        "historical_profiles_selected": len(historical_profile_pool.selected_profiles),
    }


def _stockfish_diagnostics(log_report: GameLogReport) -> Dict[str, Any]:
    for fen in log_report.key_failure_fens:
        report = analyze_with_stockfish(fen, depth=10, multipv=1)
        report["fen"] = fen
        return report
    return {"available": False, "reason": "no failure FEN available"}


def _build_improvement_summary(
    failure_report: FailureReport,
    ranking_summary: RankingSummary,
) -> str:
    if failure_report.main_failure_type in STABILITY_FIRST_FAILURES:
        return (
            "Reliability issues dominate; restrict optimization to stability-first handling "
            "before any formal parameter search."
        )
    if failure_report.main_failure_type == "regression_after_patch":
        return "Use historical profile regression before any further profile promotion."
    if failure_report.main_failure_type == "tactical_blunder":
        return (
            "Focus on the formally validated TT move ordering parameter under feedback "
            "prescreen and regression gates."
        )
    if ranking_summary.rank_delta is not None and ranking_summary.rank_delta > 0:
        return (
            "Previous profile changes improved rank; continue with one gated formal "
            "parameter step."
        )
    return "No critical reliability failure detected; continue gated profile-only optimization."


def _build_patch_plan(failure_report: FailureReport) -> str:
    actions = "; ".join(failure_report.next_actions)
    if not actions:
        actions = "keep runtime code fixed and adjust one profile block under prescreen + SPRT"
    return (
        "Profile-only revision plan: %s. Runtime tools remain fixed; only strategy-profile "
        "parameters may change after passing feedback prescreen and historical regression gates."
    ) % actions


def _resolve_report_path(
    *,
    report_path: Optional[Path],
    logs: Optional[Path],
    ranking: Optional[Path],
) -> Optional[Path]:
    if report_path is not None:
        return Path(report_path)
    for source in (logs, ranking):
        if source is None:
            continue
        path = Path(source)
        base_dir = path if path.is_dir() else path.parent
        return base_dir / "optimization_report.json"
    return None


def _persist_round_artifacts(
    *,
    report: OptimizationReport,
    artifact_dir: Path,
    report_path: Path,
    agent_path: Path,
    logs: Optional[Path],
    ranking: Optional[Path],
    opponents: Optional[Path],
    strategy_profile_before: Dict[str, Any],
    strategy_profile_after: Dict[str, Any],
    candidate_profile: Optional[StrategyProfile],
    candidate_hint_path: Optional[Path],
) -> Dict[str, str]:
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    parameter_candidates_dir = artifact_dir / "parameter_candidates"
    before_path = artifact_dir / "strategy_profile_before.json"
    after_path = artifact_dir / "strategy_profile_after.json"
    parameter_record_path = artifact_dir / "parameter_record.json"
    evaluation_record_path = artifact_dir / "evaluation_record.json"
    round_record_path = artifact_dir / "round_record.json"
    fen_suite_path = artifact_dir / "feedback_fen_suite.json"
    candidate_profile_path = _candidate_profile_path(
        artifact_dir=artifact_dir,
        candidate_hint_path=candidate_hint_path,
    )

    before_path.write_text(
        json.dumps(strategy_profile_before, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    after_path.write_text(
        json.dumps(strategy_profile_after, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    fen_suite_path.write_text(
        json.dumps(
            to_plain_data(report.feedback_fen_suite),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    candidate_payload = (
        candidate_profile.model_dump()
        if candidate_profile is not None
        else _without_source(strategy_profile_before)
    )
    candidate_profile_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_profile_path.write_text(
        json.dumps(candidate_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report.generated_agent.path = str(candidate_profile_path)

    parameter_record = _build_parameter_record(
        report=report,
        before_path=before_path,
        after_path=after_path,
        parameter_candidates_dir=parameter_candidates_dir,
        strategy_profile_before=strategy_profile_before,
        strategy_profile_after=strategy_profile_after,
    )
    evaluation_record = _build_evaluation_record(
        report=report,
        agent_path=agent_path,
        logs=logs,
        ranking=ranking,
        opponents=opponents,
        candidate_profile_path=candidate_profile_path,
        fen_suite_path=fen_suite_path,
    )
    artifact_paths = {
        "optimization_report_path": str(report_path),
        "round_record_path": str(round_record_path),
        "evaluation_record_path": str(evaluation_record_path),
        "parameter_record_path": str(parameter_record_path),
        "strategy_profile_before_path": str(before_path),
        "strategy_profile_after_path": str(after_path),
        "candidate_profile_path": str(candidate_profile_path),
        "feedback_fen_suite_path": str(fen_suite_path),
    }
    if parameter_record.get("seed_records"):
        artifact_paths["parameter_candidates_dir"] = str(parameter_candidates_dir)

    round_record = _build_round_record(
        report=report,
        agent_path=agent_path,
        evaluation_record=evaluation_record,
        parameter_record=parameter_record,
        artifact_paths=artifact_paths,
    )
    parameter_record_path.write_text(
        json.dumps(parameter_record, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    evaluation_record_path.write_text(
        json.dumps(evaluation_record, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    round_record_path.write_text(
        json.dumps(round_record, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return artifact_paths


def _candidate_profile_path(
    *,
    artifact_dir: Path,
    candidate_hint_path: Optional[Path],
) -> Path:
    if candidate_hint_path is None:
        return artifact_dir / "candidate_profile.json"
    return Path(candidate_hint_path)


def _build_parameter_record(
    *,
    report: OptimizationReport,
    before_path: Path,
    after_path: Path,
    parameter_candidates_dir: Path,
    strategy_profile_before: Dict[str, Any],
    strategy_profile_after: Dict[str, Any],
) -> Dict[str, Any]:
    before_profile = _without_source(strategy_profile_before)
    after_profile = _without_source(strategy_profile_after)
    effective_changes = _diff_dicts(before_profile, after_profile)
    seed_records = []
    for seed in report.tuning_report.seeds:
        proposed_profile = to_plain_data(seed.proposed_profile)
        proposed_profile_path = ""
        proposed_changes = []
        if proposed_profile:
            parameter_candidates_dir.mkdir(parents=True, exist_ok=True)
            seed_path = parameter_candidates_dir / f"seed_{seed.seed}_proposed_profile.json"
            seed_path.write_text(
                json.dumps(proposed_profile, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            proposed_profile_path = str(seed_path)
            proposed_changes = _diff_dicts(before_profile, proposed_profile)
        seed_records.append(
            {
                "seed": seed.seed,
                "score_difference": seed.score_difference,
                "prescreen_score_difference": seed.prescreen_score_difference,
                "applied_change_count": seed.applied_change_count,
                "applied_change_paths": list(seed.applied_change_paths),
                "acceptance_prescreen_difference": seed.acceptance_prescreen_difference,
                "acceptance_mean_score_a": seed.acceptance_mean_score_a,
                "sprt_decision": seed.sprt_decision,
                "player_a_timeouts": seed.player_a_timeouts,
                "player_b_timeouts": seed.player_b_timeouts,
                "player_a_crashes": seed.player_a_crashes,
                "proposed_profile_path": proposed_profile_path,
                "proposed_changed_paths": [item["path"] for item in proposed_changes],
                "proposed_changes": proposed_changes,
            }
        )
    return {
        "optimization_mode": OPTIMIZATION_MODE,
        "pipeline_version": PIPELINE_VERSION,
        "runtime_policy": RUNTIME_POLICY,
        "formal_execution_backend": FORMAL_EXECUTION_BACKEND,
        "round_id": report.round_id,
        "strategy_profile_before_path": str(before_path),
        "strategy_profile_after_path": str(after_path),
        "strategy_profile_before_source": strategy_profile_before.get("source", ""),
        "strategy_profile_after_source": strategy_profile_after.get("source", ""),
        "strategy_profile_before_sha256": _json_sha256(before_profile),
        "strategy_profile_after_sha256": _json_sha256(after_profile),
        "effective_changed_paths": [item["path"] for item in effective_changes],
        "effective_changes": effective_changes,
        "candidate_artifact": to_plain_data(report.generated_agent),
        "feedback_prescreen": to_plain_data(report.feedback_prescreen),
        "historical_regression": to_plain_data(report.historical_regression),
        "promotion_gate": to_plain_data(report.promotion_gate),
        "tuning": {
            "enabled": report.tuning_report.enabled,
            "action": report.tuning_report.action,
            "reason_code": report.tuning_report.reason_code,
            "reason": report.tuning_report.reason,
            "selected_block": report.tuning_report.selected_block,
            "selected_block_mode": report.tuning_report.selected_block_mode,
            "selected_block_note": report.tuning_report.selected_block_note,
            "gate_cross_count": report.tuning_report.gate_cross_count,
            "positive_inner_count": report.tuning_report.positive_inner_count,
            "negative_inner_count": report.tuning_report.negative_inner_count,
            "positive_acceptance_prescreen_count": (
                report.tuning_report.positive_acceptance_prescreen_count
            ),
            "negative_acceptance_prescreen_count": (
                report.tuning_report.negative_acceptance_prescreen_count
            ),
            "safe_seed_count": report.tuning_report.safe_seed_count,
            "consecutive_similar_holds": report.tuning_report.consecutive_similar_holds,
            "chosen_seed": report.tuning_report.chosen_seed,
            "chosen_changed_paths": list(report.tuning_report.chosen_changed_paths),
            "promoted_strategy_profile": report.tuning_report.promoted_strategy_profile,
            "promoted_profile_path": report.tuning_report.promoted_profile_path,
            "archived_profile_path": report.tuning_report.archived_profile_path,
        },
        "seed_records": seed_records,
    }


def _build_evaluation_record(
    *,
    report: OptimizationReport,
    agent_path: Path,
    logs: Optional[Path],
    ranking: Optional[Path],
    opponents: Optional[Path],
    candidate_profile_path: Path,
    fen_suite_path: Path,
) -> Dict[str, Any]:
    candidate_hash = _file_sha256(candidate_profile_path)
    return {
        "optimization_mode": OPTIMIZATION_MODE,
        "pipeline_version": PIPELINE_VERSION,
        "runtime_policy": RUNTIME_POLICY,
        "formal_execution_backend": FORMAL_EXECUTION_BACKEND,
        "round_id": report.round_id,
        "backend": report.backend,
        "version": {
            "active_agent_path": str(agent_path),
            "active_agent_sha256": _file_sha256(agent_path),
            "candidate_profile_path": str(candidate_profile_path),
            "candidate_profile_sha256": candidate_hash,
            "candidate_profile_exists": candidate_profile_path.exists(),
            "candidate_agent_path": str(candidate_profile_path),
            "candidate_agent_sha256": candidate_hash,
            "candidate_agent_exists": candidate_profile_path.exists(),
            "candidate_backend": report.generated_agent.backend,
            "candidate_promoted": report.generated_agent.promoted,
            "candidate_archived_path": report.generated_agent.archived_path,
            "generation_succeeded": report.generation_succeeded,
            "generation_error": report.generation_error,
            "validator_passed": report.validator_passed,
            "repair_attempts": report.repair_attempts,
        },
        "feedback_sources": {
            "logs": str(logs) if logs is not None else "",
            "ranking": str(ranking) if ranking is not None else "",
            "opponents": str(opponents) if opponents is not None else "",
            "raw_log_files": list(report.log_report.raw_files),
            "ranking_source": report.ranking_summary.source or "",
            "feedback_fen_suite_path": str(fen_suite_path),
        },
        "platform": {
            "catarena_ready": report.catarena_ready,
            "catarena_message": report.catarena_message,
            "catarena_source_files_seen": report.catarena_source_files_seen,
            "catarena_missing_required_files": list(report.catarena_missing_required_files),
        },
        "game_result_statistics": to_plain_data(report.ranking_summary),
        "reliability_metrics": to_plain_data(report.reliability_metrics),
        "evolution_metrics": to_plain_data(report.evolution_metrics),
        "state_summary": report.state_summary,
        "failure_report": to_plain_data(report.failure_report),
        "abnormal_events": {
            "illegal_moves": report.log_report.illegal_moves,
            "timeouts": report.log_report.timeouts,
            "crashes": report.log_report.crashes,
            "runtime_errors": list(report.log_report.runtime_errors),
            "risks": list(report.risks),
        },
        "key_failure_positions": list(report.log_report.key_failure_fens),
        "opponent_features": to_plain_data(report.opponent_report),
        "historical_profile_pool": to_plain_data(report.historical_profile_pool),
        "historical_regression": to_plain_data(report.historical_regression),
        "feedback_prescreen": to_plain_data(report.feedback_prescreen),
        "promotion_gate": to_plain_data(report.promotion_gate),
        "stockfish_diagnostics": report.stockfish_diagnostics,
        "core_modification_summary": {
            "generated_agent_summary": report.generated_agent.summary,
            "candidate_profile_summary": report.generated_agent.summary,
            "improvement_summary": report.improvement_summary,
            "patch_plan": report.patch_plan,
            "changed": report.generated_agent.changed,
            "generation_succeeded": report.generation_succeeded,
            "generation_error": report.generation_error,
        },
        "next_round_revision_plan": {
            "next_focus": report.improvement_summary,
            "patch_plan": report.patch_plan,
            "tuning_action": report.tuning_report.action,
            "tuning_reason_code": report.tuning_report.reason_code,
        },
    }


def _build_round_record(
    *,
    report: OptimizationReport,
    agent_path: Path,
    evaluation_record: Dict[str, Any],
    parameter_record: Dict[str, Any],
    artifact_paths: Dict[str, str],
) -> Dict[str, Any]:
    candidate_hash = _file_sha256(Path(report.generated_agent.path))
    return {
        "optimization_mode": OPTIMIZATION_MODE,
        "pipeline_version": PIPELINE_VERSION,
        "runtime_policy": RUNTIME_POLICY,
        "formal_execution_backend": FORMAL_EXECUTION_BACKEND,
        "round_id": report.round_id,
        "version_identifier": {
            "round_version": report.round_id,
            "active_agent_path": str(agent_path),
            "candidate_profile_path": report.generated_agent.path,
            "candidate_agent_path": report.generated_agent.path,
            "candidate_profile_backend": report.generated_agent.backend,
            "candidate_agent_backend": report.generated_agent.backend,
            "candidate_profile_sha256": candidate_hash,
            "candidate_agent_sha256": candidate_hash,
            "candidate_profile_promoted": report.generated_agent.promoted,
            "candidate_agent_promoted": False,
            "candidate_profile_archived_path": report.generated_agent.archived_path,
            "candidate_agent_archived_path": report.generated_agent.archived_path,
            "strategy_profile_before_sha256": parameter_record["strategy_profile_before_sha256"],
            "strategy_profile_after_sha256": parameter_record["strategy_profile_after_sha256"],
        },
        "core_modification_summary": {
            "generated_agent_summary": report.generated_agent.summary,
            "candidate_profile_summary": report.generated_agent.summary,
            "improvement_summary": report.improvement_summary,
            "patch_plan": report.patch_plan,
            "repair_attempts": report.repair_attempts,
            "generation_succeeded": report.generation_succeeded,
            "generation_error": report.generation_error,
            "validator_passed": report.validator_passed,
            "tuning_selected_block": report.tuning_report.selected_block,
            "tuning_action": report.tuning_report.action,
        },
        "game_result_statistics": evaluation_record["game_result_statistics"],
        "key_failure_positions": evaluation_record["key_failure_positions"],
        "abnormal_events": evaluation_record["abnormal_events"],
        "opponent_features": evaluation_record["opponent_features"],
        "feedback_evidence": {
            "raw_log_files": evaluation_record["feedback_sources"]["raw_log_files"],
            "ranking_source": evaluation_record["feedback_sources"]["ranking_source"],
            "runtime_errors": evaluation_record["abnormal_events"]["runtime_errors"],
            "key_failure_positions": evaluation_record["key_failure_positions"],
        },
        "next_round_revision_plan": evaluation_record["next_round_revision_plan"],
        "parameter_adjustment_record": {
            "selected_block": parameter_record["tuning"]["selected_block"],
            "tuning_action": parameter_record["tuning"]["action"],
            "tuning_reason_code": parameter_record["tuning"]["reason_code"],
            "effective_changed_paths": parameter_record["effective_changed_paths"],
            "chosen_changed_paths": parameter_record["tuning"]["chosen_changed_paths"],
        },
        "artifact_paths": artifact_paths,
    }


def _memory_record(report: OptimizationReport) -> Dict[str, Any]:
    return {
        "optimization_mode": OPTIMIZATION_MODE,
        "pipeline_version": PIPELINE_VERSION,
        "runtime_policy": RUNTIME_POLICY,
        "formal_execution_backend": FORMAL_EXECUTION_BACKEND,
        "round_id": report.round_id,
        "agent_version": report.generated_agent.path,
        "rank": report.ranking_summary.rank,
        "win_rate": report.ranking_summary.win_rate,
        "failure_reason": report.failure_report.main_failure_type,
        "runtime_errors": report.log_report.runtime_errors,
        "illegal_moves": report.log_report.illegal_moves,
        "timeouts": report.log_report.timeouts,
        "crashes": report.log_report.crashes,
        "same_round_score": report.evolution_metrics.same_round_score,
        "sevo": report.evolution_metrics.sevo,
        "main_failure_type": report.failure_report.main_failure_type,
        "generation_succeeded": report.generation_succeeded,
        "generation_error": report.generation_error,
        "round_changes": report.patch_plan,
        "changed_modules": [report.generated_agent.path] if report.generated_agent.path else [],
        "effective_changes": list(report.generated_agent.effective_changed_paths),
        "ineffective_changes": [],
        "next_focus": report.improvement_summary,
        "tuning": to_plain_data(report.tuning_report),
        "artifact_paths": report.artifact_paths,
    }


def _without_source(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in snapshot.items() if key != "source"}


def _diff_dicts(
    before: Dict[str, Any],
    after: Dict[str, Any],
    prefix: str = "",
) -> list[Dict[str, Any]]:
    changes: list[Dict[str, Any]] = []
    keys = sorted(set(before) | set(after))
    for key in keys:
        path = f"{prefix}.{key}" if prefix else str(key)
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, dict) and isinstance(after_value, dict):
            changes.extend(_diff_dicts(before_value, after_value, path))
            continue
        if before_value != after_value:
            changes.append(
                {
                    "path": path,
                    "before": to_plain_data(before_value),
                    "after": to_plain_data(after_value),
                }
            )
    return changes


def _json_sha256(payload: Dict[str, Any]) -> str:
    text = json.dumps(to_plain_data(payload), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return ""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def _promote_strategy_profile(
    *,
    proposed_profile: Dict[str, Any],
    strategy_profile_path: Path,
    round_id: str,
) -> Optional[Path]:
    if not proposed_profile:
        return None
    strategy_profile_path = Path(strategy_profile_path)
    strategy_profile_path.parent.mkdir(parents=True, exist_ok=True)
    archive_dir = strategy_profile_path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / (
        f"{strategy_profile_path.stem}_{round_id}{strategy_profile_path.suffix}"
    )
    if strategy_profile_path.exists():
        shutil.copy2(strategy_profile_path, archive_path)
    strategy_profile_path.write_text(
        json.dumps(proposed_profile, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return archive_path


def _format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


def _progress(
    progress_callback: Optional[ProgressCallback],
    status: str,
    message: str,
) -> None:
    if progress_callback is not None:
        progress_callback(status, message)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one CATArena-backed profile-only optimization round."
    )
    parser.add_argument("--round-id", required=True)
    parser.add_argument("--logs", type=Path)
    parser.add_argument("--ranking", type=Path)
    parser.add_argument("--opponents", type=Path)
    parser.add_argument("--agent", type=Path, default=Path("agents/chess_agent.py"))
    parser.add_argument("--memory", type=Path, default=DEFAULT_MEMORY_PATH)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--next-agent", type=Path)
    parser.add_argument("--strict-catarena", action="store_true")
    parser.add_argument(
        "--backend",
        choices=["rule", "openai", "profile"],
        default="profile",
        help="Compatibility alias. All values execute the same profile-only optimizer.",
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
        help="Promote a validated strategy profile when the promotion gate passes.",
    )
    parser.add_argument(
        "--promote-agent",
        action="store_true",
        help="Deprecated compatibility flag. Runtime agent code is never promoted.",
    )
    parser.add_argument("--promote-profile", action="store_true")
    args = parser.parse_args()

    try:
        report = run_optimization_round(
            round_id=args.round_id,
            logs=args.logs,
            ranking=args.ranking,
            opponents=args.opponents,
            agent_path=args.agent,
            memory_path=args.memory,
            report_path=args.report,
            next_agent_path=args.next_agent,
            strict_catarena=args.strict_catarena,
            backend=args.backend,
            max_repair_attempts=args.max_repair_attempts,
            promote_agent=args.promote_agent,
            promote_profile=args.promote_profile,
            promote=args.promote,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(to_plain_data(report), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
