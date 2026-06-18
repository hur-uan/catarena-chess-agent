"""Regression checks against historical promoted or archived profiles."""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

from tools.opponent_pool import HistoricalProfileEntry, OpponentPoolReport
from tools.strategy_profile import StrategyProfile, load_strategy_profile
from tuning.match_runner import MatchConfig, MatchSummary, run_paired_match


class HistoricalRegressionEntry(BaseModel):
    round_id: str
    profile_path: str
    mean_score_a: float = 0.5
    timeout_rate_a: float = 0.0
    timeout_rate_b: float = 0.0
    crashes_a: int = 0
    crashes_b: int = 0
    passed: bool = True


class HistoricalRegressionReport(BaseModel):
    enabled: bool = False
    total_profiles: int = 0
    passed_profiles: int = 0
    failed_profiles: int = 0
    passed: bool = True
    entries: List[HistoricalRegressionEntry] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


def run_historical_regression(
    candidate_profile: StrategyProfile,
    pool_report: OpponentPoolReport,
    *,
    pair_count: int = 2,
    time_limit_ms: int = 40,
    max_plies: int = 40,
) -> HistoricalRegressionReport:
    report = HistoricalRegressionReport(enabled=True)
    selected = list(pool_report.selected_profiles)
    report.total_profiles = len(selected)
    if not selected:
        report.notes.append("no historical profiles selected")
        return report

    for item in selected:
        summary = _match_against_profile(
            candidate_profile,
            item,
            pair_count=pair_count,
            time_limit_ms=time_limit_ms,
            max_plies=max_plies,
        )
        passed = _passes_regression_gate(summary)
        report.entries.append(
            HistoricalRegressionEntry(
                round_id=item.round_id,
                profile_path=item.profile_path,
                mean_score_a=summary.mean_score_a,
                timeout_rate_a=summary.timeout_rate_a(),
                timeout_rate_b=summary.timeout_rate_b(),
                crashes_a=summary.player_a_crashes,
                crashes_b=summary.player_b_crashes,
                passed=passed,
            )
        )
        if passed:
            report.passed_profiles += 1
        else:
            report.failed_profiles += 1
            report.passed = False

    return report


def _match_against_profile(
    candidate_profile: StrategyProfile,
    historical_entry: HistoricalProfileEntry,
    *,
    pair_count: int,
    time_limit_ms: int,
    max_plies: int,
) -> MatchSummary:
    profile_path = Path(historical_entry.profile_path)
    historical_profile = load_strategy_profile(profile_path)
    return run_paired_match(
        candidate_profile,
        historical_profile,
        MatchConfig(
            pair_count=pair_count,
            time_limit_ms=time_limit_ms,
            max_plies=max_plies,
        ),
    )


def _passes_regression_gate(summary: MatchSummary) -> bool:
    if summary.player_a_crashes > 0:
        return False
    if summary.timeout_rate_a() > summary.timeout_rate_b() + 0.05:
        return False
    return summary.mean_score_a >= 0.45
