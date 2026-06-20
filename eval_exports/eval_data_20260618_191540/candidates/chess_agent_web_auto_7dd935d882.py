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

from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
from tools.black_numba_client import (
    BlackNumbaUnavailable,
    analyze_position,
    is_black_numba_available,
)
from tools.board_parser import extract_legal_moves, parse_observation

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
    external = _select_move_via_black_numba(observation, output_format, time_limit_ms)
    if external is not None:
        return external
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


def _select_move_via_black_numba(
    observation: Any,
    output_format: str,
    time_limit_ms: int,
) -> SearchRecord | None:
    if output_format.lower().strip() not in {"uci", "default", ""}:
        return None
    if not is_black_numba_available():
        return None

    board = parse_observation(observation)
    legal_moves = [move.uci() for move in board.legal_moves]
    if not legal_moves or board.is_game_over(claim_draw=False):
        return SearchRecord(
            fen=board.fen(),
            selected_move="",
            cp=0,
            mate_distance=None,
            wdl=cp_to_wdl(0, None),
            depth=0,
            elapsed_ms=0.0,
            nodes=0,
            qnodes=0,
            legal_moves=legal_moves,
        )

    try:
        response = analyze_position(
            fen=board.fen(),
            time_limit_ms=max(50, time_limit_ms),
            depth_limit=4,
        )
    except BlackNumbaUnavailable:
        return None

    hinted = {
        str(item).strip()
        for item in extract_legal_moves(observation)
        if str(item).strip()
    }
    move = str(response.get("move", "")).strip()
    if hinted and move not in hinted and hinted.intersection(legal_moves):
        move = next(iter(hinted.intersection(legal_moves)))
    if move not in legal_moves:
        return None

    score_cp = int(response.get("score_cp", 0))
    mate_distance = response.get("mate_distance")
    return SearchRecord(
        fen=board.fen(),
        selected_move=move,
        cp=score_cp,
        mate_distance=int(mate_distance) if mate_distance is not None else None,
        wdl=cp_to_wdl(score_cp, int(mate_distance) if mate_distance is not None else None),
        depth=int(response.get("depth", 0)),
        elapsed_ms=float(response.get("elapsed_ms", 0.0)),
        nodes=int(response.get("nodes", 0)),
        qnodes=0,
        legal_moves=legal_moves,
        principal_variation=list(response.get("principal_variation", [])),
        fallback_used=False,
    )
