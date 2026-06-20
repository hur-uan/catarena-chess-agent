"""Proposal-aligned CATArena chess agent.

The public entry point remains:
select_move(observation, output_format="uci", time_limit_ms=100) -> str
"""

from __future__ import annotations

from typing import Any

from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
from tools.black_numba_client import (
    BlackNumbaUnavailable,
    analyze_position,
    is_black_numba_available,
)
from tools.black_numba_config import ResolvedBlackNumbaConfig, resolve_black_numba_config
from tools.board_parser import extract_legal_moves, parse_observation
from tools.strategy_profile import resolve_strategy_profile

DEFAULT_ENGINE_CONFIG = EngineConfig()


def _is_uci_output(output_format: str) -> bool:
    """Return True when the caller expects the standard CATArena UCI move string."""
    return str(output_format or "").lower().strip() in {"uci", "default", ""}


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
    config = EngineConfig(strategy_profile=strategy_profile)

    # A mate in one is inexpensive to prove and should never be missed due to
    # external-engine availability, shallow depth limits, or move-order noise.
    immediate_mate = _select_mate_in_one(observation, output_format)
    if immediate_mate is not None:
        immediate_mate.engine_config = {
            "profile_name": strategy_profile.profile_name,
            "strategy_source": strategy_source,
            "tactical_override": "mate_in_one",
        }
        return immediate_mate

    external = _select_move_via_black_numba(observation, output_format, time_limit_ms)
    if external is not None:
        return external
    record = select_move_record(
        observation=observation,
        output_format=output_format,
        time_limit_ms=time_limit_ms,
        config=config,
    )
    record.engine_config = {
        "profile_name": strategy_profile.profile_name,
        "strategy_source": strategy_source,
    }
    return record


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _select_mate_in_one(observation: Any, output_format: str) -> SearchRecord | None:
    """Return a deterministic legal checkmating move if one exists.

    The helper is deliberately shallow and bounded: it only iterates over the
    current legal move list once and validates each candidate with python-chess
    push/pop semantics. If parsing or board access fails, callers fall back to
    the normal engine path.
    """
    if not _is_uci_output(output_format):
        return None
    try:
        board = parse_observation(observation)
        legal_moves = list(board.legal_moves)
    except Exception:
        return None

    legal_uci = [move.uci() for move in legal_moves]
    if not legal_moves or board.is_game_over(claim_draw=False):
        return None

    # Sort UCI strings for deterministic behavior while still validating with
    # the original Move object. Promotions naturally sort after their origin and
    # destination and remain legal only if python-chess generated them.
    by_uci = {move.uci(): move for move in legal_moves}
    for move_uci in sorted(by_uci):
        candidate = by_uci[move_uci]
        board.push(candidate)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return SearchRecord(
                fen=board.fen(),
                selected_move=move_uci,
                cp=99999,
                mate_distance=1,
                wdl=cp_to_wdl(99999, 1),
                depth=1,
                elapsed_ms=0.0,
                nodes=len(legal_moves),
                qnodes=0,
                legal_moves=legal_uci,
                principal_variation=[move_uci],
                fallback_used=False,
                backend="mate_in_one_precheck",
            )
    return None


def _select_move_via_black_numba(
    observation: Any,
    output_format: str,
    time_limit_ms: int,
) -> SearchRecord | None:
    if not _is_uci_output(output_format):
        return None
    if not is_black_numba_available():
        return None

    board = parse_observation(observation)
    resolved = resolve_black_numba_config(
        board=board,
        requested_time_limit_ms=time_limit_ms,
        observation=observation,
    )
    if not resolved.enabled:
        return None
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
            time_limit_ms=resolved.search_time_limit_ms,
            depth_limit=resolved.depth_limit,
            node_limit=resolved.node_limit,
        )
    except BlackNumbaUnavailable:
        return None
    except Exception:
        # Treat unexpected local external-engine errors as unavailability so the
        # trusted internal engine can still produce a legal move.
        return None

    hinted = {
        str(item).strip()
        for item in extract_legal_moves(observation)
        if str(item).strip()
    }
    move = str(response.get("move", "")).strip()
    hinted_legal = sorted(hinted.intersection(legal_moves))
    if hinted and move not in hinted and hinted_legal:
        move = hinted_legal[0]
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
        backend="black_numba",
        engine_config=_engine_config_payload(resolved),
    )


def _engine_config_payload(resolved: ResolvedBlackNumbaConfig) -> dict[str, object]:
    return {
        "phase": resolved.phase,
        "requested_time_limit_ms": resolved.requested_time_limit_ms,
        "search_time_limit_ms": resolved.search_time_limit_ms,
        "depth_limit": resolved.depth_limit,
        "node_limit": resolved.node_limit,
        "source": resolved.source,
        "used_low_time_profile": resolved.used_low_time_profile,
    }
