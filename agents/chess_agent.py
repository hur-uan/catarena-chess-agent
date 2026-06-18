"""Proposal-aligned CATArena chess agent.

The public entry point remains:
select_move(observation, output_format="uci", time_limit_ms=100) -> str
"""

from __future__ import annotations

from typing import Any

from agents.engine import SearchRecord
from tools.search_router import route_search
from tools.strategy_profile import resolve_strategy_profile


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
    strategy_profile, strategy_source = resolve_strategy_profile(observation=observation)
    return route_search(
        observation=observation,
        output_format=output_format,
        time_limit_ms=time_limit_ms,
        strategy_profile=strategy_profile,
        strategy_source=strategy_source,
    )


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)
