"""Small SPSA helper for normalized strategy-profile tuning."""

from __future__ import annotations

import random
from typing import List

from pydantic import BaseModel, Field


class SpsaConfig(BaseModel):
    alpha: float = 0.602
    gamma: float = 0.101
    learning_rate: float = 0.15
    perturbation: float = 0.10
    stability_constant: float = 5.0
    min_effective_score_difference: float = 0.0


class SpsaStep(BaseModel):
    iteration: int
    ak: float
    ck: float
    delta: List[int] = Field(default_factory=list)
    plus_vector: List[float] = Field(default_factory=list)
    minus_vector: List[float] = Field(default_factory=list)


class SpsaIteration(BaseModel):
    step: SpsaStep
    score_difference: float
    match_score_difference: float = 0.0
    prescreen_score_difference: float = 0.0
    updated_vector: List[float] = Field(default_factory=list)
    applied_change_count: int = 0
    applied_change_paths: List[str] = Field(default_factory=list)


def spsa_update_step(
    theta: List[float],
    iteration: int,
    config: SpsaConfig,
    rng: random.Random,
) -> SpsaStep:
    ak = config.learning_rate / ((iteration + config.stability_constant) ** config.alpha)
    ck = config.perturbation / (iteration**config.gamma)
    delta = [rng.choice((-1, 1)) for _ in theta]
    plus_vector = [_clip01(value + ck * direction) for value, direction in zip(theta, delta)]
    minus_vector = [_clip01(value - ck * direction) for value, direction in zip(theta, delta)]
    return SpsaStep(
        iteration=iteration,
        ak=ak,
        ck=ck,
        delta=delta,
        plus_vector=plus_vector,
        minus_vector=minus_vector,
    )


def apply_spsa_result(
    theta: List[float],
    step: SpsaStep,
    score_difference: float,
    min_effective_score_difference: float = 0.0,
) -> List[float]:
    if not theta:
        return []
    effective_difference = score_difference
    if (
        min_effective_score_difference > 0.0
        and 0.0 < abs(score_difference) < min_effective_score_difference
    ):
        effective_difference = min_effective_score_difference
        if score_difference < 0.0:
            effective_difference *= -1.0
    gradient_scale = effective_difference / max(1e-9, 2.0 * step.ck)
    updated: List[float] = []
    for value, direction in zip(theta, step.delta):
        gradient = gradient_scale * direction
        updated.append(_clip01(value + step.ak * gradient))
    return updated


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))
