"""Sequential testing utilities for local engine-vs-engine evaluation."""

from __future__ import annotations

import math
from enum import Enum
from statistics import mean
from typing import List

from pydantic import BaseModel


class SprtDecision(str, Enum):
    ACCEPT_H0 = "accept_h0"
    ACCEPT_H1 = "accept_h1"
    CONTINUE = "continue"


class SprtConfig(BaseModel):
    elo0: float = 0.0
    elo1: float = 5.0
    alpha: float = 0.05
    beta: float = 0.05


class SprtResult(BaseModel):
    games: int = 0
    mean_score: float = 0.5
    variance: float = 0.25
    llr: float = 0.0
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    decision: SprtDecision = SprtDecision.CONTINUE


def evaluate_sprt(scores: List[float], config: SprtConfig) -> SprtResult:
    if not scores:
        lower_bound, upper_bound = _bounds(config)
        return SprtResult(lower_bound=lower_bound, upper_bound=upper_bound)

    games = len(scores)
    average = mean(scores)
    variance = _variance(scores, average)
    variance = max(variance, 1e-6)
    mu0 = _score_expectation(config.elo0)
    mu1 = _score_expectation(config.elo1)
    llr = games * (((average - mu0) ** 2) - ((average - mu1) ** 2)) / (2.0 * variance)
    lower_bound, upper_bound = _bounds(config)
    if llr >= upper_bound:
        decision = SprtDecision.ACCEPT_H1
    elif llr <= lower_bound:
        decision = SprtDecision.ACCEPT_H0
    else:
        decision = SprtDecision.CONTINUE
    return SprtResult(
        games=games,
        mean_score=average,
        variance=variance,
        llr=llr,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        decision=decision,
    )


def _score_expectation(elo: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-elo / 400.0))


def _bounds(config: SprtConfig) -> tuple[float, float]:
    lower = math.log(config.beta / max(1e-9, 1.0 - config.alpha))
    upper = math.log((1.0 - config.beta) / max(1e-9, config.alpha))
    return lower, upper


def _variance(values: List[float], average: float) -> float:
    if len(values) <= 1:
        return 0.25
    numerator = sum((value - average) ** 2 for value in values)
    return numerator / (len(values) - 1)
