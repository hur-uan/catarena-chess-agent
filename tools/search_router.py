"""Deterministic runtime routing for the chess agent search tools."""

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
from tools.strategy_profile import StrategyProfile


def route_search(
    observation: Any,
    *,
    output_format: str = "uci",
    time_limit_ms: int = 100,
    strategy_profile: StrategyProfile,
    strategy_source: str,
) -> SearchRecord:
    external = _try_external_route(
        observation=observation,
        output_format=output_format,
        time_limit_ms=time_limit_ms,
        strategy_profile=strategy_profile,
    )
    if external is not None:
        external.engine_config.setdefault("profile_name", strategy_profile.profile_name)
        external.engine_config.setdefault("strategy_source", strategy_source)
        return external

    record = select_move_record(
        observation=observation,
        output_format=output_format,
        time_limit_ms=time_limit_ms,
        config=EngineConfig(strategy_profile=strategy_profile),
    )
    record.engine_config = {
        "router_backend": "internal",
        "profile_name": strategy_profile.profile_name,
        "strategy_source": strategy_source,
        "external_engine_available": is_black_numba_available(),
    }
    return record


def router_snapshot(
    observation: Any,
    *,
    requested_time_limit_ms: int,
) -> dict[str, object]:
    board = parse_observation(observation)
    resolved = resolve_black_numba_config(
        board=board,
        requested_time_limit_ms=requested_time_limit_ms,
        observation=observation,
    )
    return {
        "external_engine_available": is_black_numba_available(),
        "requested_time_limit_ms": requested_time_limit_ms,
        "external_route_enabled": resolved.enabled,
        "external_route_phase": resolved.phase,
        "external_route_depth_limit": resolved.depth_limit,
        "external_route_node_limit": resolved.node_limit,
        "external_route_source": resolved.source,
        "used_low_time_profile": resolved.used_low_time_profile,
    }


def _try_external_route(
    *,
    observation: Any,
    output_format: str,
    time_limit_ms: int,
    strategy_profile: StrategyProfile,
) -> SearchRecord | None:
    if output_format.lower().strip() not in {"uci", "default", ""}:
        return None
    if not strategy_profile.external_engine.enabled:
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
            backend="black_numba",
            engine_config=_resolved_payload(resolved),
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

    hinted = {
        str(item).strip()
        for item in extract_legal_moves(observation)
        if str(item).strip()
    }
    move = str(response.get("move", "")).strip()
    hinted_legal = hinted.intersection(legal_moves)
    if hinted_legal and move not in hinted_legal:
        move = next(iter(hinted_legal))
    if move not in legal_moves:
        return None

    score_cp = int(response.get("score_cp", 0))
    mate_distance = response.get("mate_distance")
    parsed_mate = int(mate_distance) if mate_distance is not None else None
    return SearchRecord(
        fen=board.fen(),
        selected_move=move,
        cp=score_cp,
        mate_distance=parsed_mate,
        wdl=cp_to_wdl(score_cp, parsed_mate),
        depth=int(response.get("depth", 0)),
        elapsed_ms=float(response.get("elapsed_ms", 0.0)),
        nodes=int(response.get("nodes", 0)),
        qnodes=0,
        legal_moves=legal_moves,
        principal_variation=list(response.get("principal_variation", [])),
        fallback_used=False,
        backend="black_numba",
        engine_config=_resolved_payload(resolved),
    )


def _resolved_payload(resolved: ResolvedBlackNumbaConfig) -> dict[str, object]:
    return {
        "router_backend": "black_numba",
        "phase": resolved.phase,
        "requested_time_limit_ms": resolved.requested_time_limit_ms,
        "search_time_limit_ms": resolved.search_time_limit_ms,
        "depth_limit": resolved.depth_limit,
        "node_limit": resolved.node_limit,
        "source": resolved.source,
        "used_low_time_profile": resolved.used_low_time_profile,
    }
