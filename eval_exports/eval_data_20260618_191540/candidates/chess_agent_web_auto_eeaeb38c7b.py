"""Generated next-round CATArena chess agent.

This file is produced by the rule-template Optimization Agent. The first
stage generator keeps behavior identical unless a human applies the patch
plan below, which prevents unvalidated automatic strategy rewrites.

Failure type: no_clear_failure
Patch plan: Rule-template patch plan: make one small strategy improvement and validate against fixed
FEN set. Do not apply automatically; implement only after validating against the fixed
FEN and interface tests.
"""

from __future__ import annotations

from typing import Any

from agents.engine import EngineConfig, SearchRecord, select_move_record

DEFAULT_ENGINE_CONFIG = EngineConfig()


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> str:
    """Choose a legal chess move for the supplied observation."""
    return select_move_details(
        observation=observation,
        output_format=output_format,
        time_limit_ms=time_limit_ms,
    ).selected_move


def select_move_details(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> SearchRecord:
    """Return the selected move and the underlying search diagnostics."""
    return select_move_record(
        observation=observation,
        output_format=output_format,
        time_limit_ms=time_limit_ms,
        config=DEFAULT_ENGINE_CONFIG,
    )


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)
