"""Rule-based failure classification for round-to-round optimization."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from tools.log_parser import GameLogReport
from tools.ranking_analyzer import RankingSummary

TIMEOUT_RATE_FAILURE_THRESHOLD = 0.005
TIMEOUT_COUNT_FAILURE_THRESHOLD = 3


class FailureReport(BaseModel):
    main_failure_type: str = "unknown"
    priority: str = "medium"
    evidence: List[str] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)


def classify_failure(
    log_report: GameLogReport,
    ranking_summary: RankingSummary,
    validator_ok: bool = True,
) -> FailureReport:
    report = FailureReport()

    if not validator_ok:
        report.main_failure_type = "interface_error"
        report.priority = "critical"
        report.evidence.append("code validator failed")
        report.next_actions.append(
            "fix import/interface/validator failures before strategy changes"
        )
        return report

    if log_report.crashes > 0 or log_report.runtime_errors:
        report.main_failure_type = "interface_error"
        report.priority = "critical"
        report.evidence.append("crashes/runtime errors observed: %d" % log_report.crashes)
        report.next_actions.append("harden observation parsing and exception handling")
        return report

    if log_report.illegal_moves > 0:
        report.main_failure_type = "illegal_move"
        report.priority = "high"
        report.evidence.append("illegal moves observed: %d" % log_report.illegal_moves)
        report.next_actions.append("route every strategy output through validate_move and fallback")
        return report

    timeout_rate = (
        log_report.timeouts / log_report.total_actions
        if log_report.total_actions > 0
        else 0.0
    )
    if (
        log_report.timeouts >= TIMEOUT_COUNT_FAILURE_THRESHOLD
        or timeout_rate >= TIMEOUT_RATE_FAILURE_THRESHOLD
    ):
        report.main_failure_type = "timeout"
        report.priority = "high"
        report.evidence.append(
            "timeouts observed: %d (rate %.3f)" % (log_report.timeouts, timeout_rate)
        )
        report.next_actions.append("lower search depth and enforce stricter per-move budget")
        return report

    if ranking_summary.rank_delta is not None and ranking_summary.rank_delta < 0:
        report.main_failure_type = "regression_after_patch"
        report.priority = "high"
        report.evidence.append("rank worsened by %d places" % abs(ranking_summary.rank_delta))
        report.next_actions.append("compare latest patch against previous memory entry")
        return report

    if ranking_summary.win_rate is not None and ranking_summary.win_rate < 0.4:
        report.main_failure_type = "tactical_blunder"
        report.priority = "medium"
        report.evidence.append("low win rate: %.3f" % ranking_summary.win_rate)
        report.next_actions.append("improve capture ordering, checks, and shallow tactical search")
        return report

    report.main_failure_type = "no_clear_failure"
    report.priority = "low"
    if log_report.timeouts > 0:
        report.evidence.append(
            "low-rate timeouts observed but below failure threshold: %d (rate %.3f)"
            % (log_report.timeouts, timeout_rate)
        )
    else:
        report.evidence.append("no crashes, illegal moves, or timeout signals found")
    report.next_actions.append(
        "make one small strategy improvement and validate against fixed FEN set"
    )
    return report
