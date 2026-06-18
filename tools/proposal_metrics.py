"""Metrics aligned with the project proposal."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from tools.log_parser import GameLogReport
from tools.memory_store import read_memory
from tools.ranking_analyzer import RankingSummary


class ReliabilityMetrics(BaseModel):
    legal_rate: Optional[float] = None
    interface_success_rate: Optional[float] = None
    error_rate: Optional[float] = None
    timeout_rate: Optional[float] = None
    average_response_ms: Optional[float] = None


class EvolutionMetrics(BaseModel):
    sbase: Optional[float] = None
    same_round_score: Optional[float] = None
    global_scores: List[float] = Field(default_factory=list)
    sevo: Optional[float] = None
    rounds_considered: int = 0


def compute_reliability_metrics(log_report: GameLogReport) -> ReliabilityMetrics:
    actions = log_report.total_actions
    if actions <= 0:
        return ReliabilityMetrics()
    legal_ok = max(0, actions - log_report.illegal_moves)
    interface_ok = max(0, log_report.interface_successes)
    return ReliabilityMetrics(
        legal_rate=legal_ok / actions,
        interface_success_rate=interface_ok / actions,
        error_rate=log_report.crashes / actions,
        timeout_rate=log_report.timeouts / actions,
        average_response_ms=log_report.average_response_ms,
    )


def compute_evolution_metrics(
    ranking_summary: RankingSummary,
    memory_path: Optional[str] = None,
) -> EvolutionMetrics:
    same_round_score = _score_from_ranking(ranking_summary)
    if memory_path is None:
        return EvolutionMetrics(sbase=same_round_score, same_round_score=same_round_score)

    records = read_memory(memory_path)
    scores = []
    for record in records:
        value = record.get("same_round_score")
        if isinstance(value, (int, float)):
            scores.append(float(value))
        elif isinstance(record.get("win_rate"), (int, float)):
            scores.append(float(record["win_rate"]))
    if same_round_score is not None:
        scores.append(same_round_score)
    sevo = _ols_slope(scores)
    sbase = scores[0] if scores else same_round_score
    return EvolutionMetrics(
        sbase=sbase,
        same_round_score=same_round_score,
        global_scores=scores,
        sevo=sevo,
        rounds_considered=len(scores),
    )


def _score_from_ranking(ranking_summary: RankingSummary) -> Optional[float]:
    if ranking_summary.win_rate is not None:
        return float(ranking_summary.win_rate)
    if ranking_summary.games > 0:
        score = ranking_summary.wins + 0.5 * ranking_summary.draws
        return score / ranking_summary.games
    return None


def _ols_slope(values: List[float]) -> Optional[float]:
    count = len(values)
    if count < 2:
        return None
    x_mean = (count + 1) / 2
    y_mean = sum(values) / count
    numerator = 0.0
    denominator = 0.0
    for index, value in enumerate(values, start=1):
        dx = index - x_mean
        numerator += dx * (value - y_mean)
        denominator += dx * dx
    if denominator == 0:
        return None
    return numerator / denominator
