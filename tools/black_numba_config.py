"""Shared configuration for black_numba-backed move selection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import chess
from pydantic import BaseModel

from tools.strategy_profile import (
    DEFAULT_STRATEGY_PROFILE_PATH,
    StrategyProfile,
    load_strategy_profile,
    resolve_strategy_profile,
    _deep_merge,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BLACK_NUMBA_CONFIG_PATH = ROOT / "config/black_numba.json"


class BlackNumbaConfig(BaseModel):
    enabled: bool = False
    minimum_external_budget_ms: int = 60
    time_buffer_ms: int = 8
    low_time_threshold_ms: int = 80
    opening_fullmove_limit: int = 10
    endgame_non_king_piece_threshold: int = 10
    opening_depth_limit: int = 4
    opening_node_limit: int = 2_000_000
    middlegame_depth_limit: int = 4
    middlegame_node_limit: int = 4_000_000
    endgame_depth_limit: int = 5
    endgame_node_limit: int = 8_000_000
    low_time_depth_limit: int = 2
    low_time_node_limit: int = 250_000


class ResolvedBlackNumbaConfig(BaseModel):
    enabled: bool = True
    phase: str = "middlegame"
    requested_time_limit_ms: int = 100
    search_time_limit_ms: int = 92
    depth_limit: int = 4
    node_limit: int = 4_000_000
    source: str = "defaults"
    used_low_time_profile: bool = False


def load_black_numba_config(path: Optional[Path] = None) -> BlackNumbaConfig:
    profile = _load_profile(path)
    return _from_strategy_profile(profile)


def resolve_black_numba_config(
    board: chess.Board,
    requested_time_limit_ms: int,
    observation: Any = None,
    path: Optional[Path] = None,
) -> ResolvedBlackNumbaConfig:
    profile, source = resolve_strategy_profile(observation=observation, path=path)
    legacy_override = _legacy_override_payload(observation)
    if legacy_override:
        profile = StrategyProfile.model_validate(
            _deep_merge(
                profile.model_dump(),
                {"external_engine": legacy_override},
            )
        )
        source = "legacy_observation_override"
    config = _from_strategy_profile(profile)

    requested = max(0, int(requested_time_limit_ms))
    if not config.enabled:
        return ResolvedBlackNumbaConfig(
            enabled=False,
            requested_time_limit_ms=requested,
            search_time_limit_ms=max(1, requested),
            source=source,
        )

    if requested < config.minimum_external_budget_ms:
        return ResolvedBlackNumbaConfig(
            enabled=False,
            requested_time_limit_ms=requested,
            search_time_limit_ms=max(1, requested),
            source=source,
        )

    phase = _phase(board, config)
    used_low_time_profile = requested <= config.low_time_threshold_ms
    if used_low_time_profile:
        depth_limit = config.low_time_depth_limit
        node_limit = config.low_time_node_limit
        phase = "low_time"
    elif phase == "opening":
        depth_limit = config.opening_depth_limit
        node_limit = config.opening_node_limit
    elif phase == "endgame":
        depth_limit = config.endgame_depth_limit
        node_limit = config.endgame_node_limit
    else:
        depth_limit = config.middlegame_depth_limit
        node_limit = config.middlegame_node_limit

    return ResolvedBlackNumbaConfig(
        enabled=True,
        phase=phase,
        requested_time_limit_ms=requested,
        search_time_limit_ms=max(1, requested - config.time_buffer_ms),
        depth_limit=depth_limit,
        node_limit=node_limit,
        source=source,
        used_low_time_profile=used_low_time_profile,
    )


def black_numba_config_snapshot(path: Optional[Path] = None) -> Dict[str, Any]:
    config_path = _config_path(path)
    config = load_black_numba_config(path)
    snapshot = config.model_dump()
    snapshot["source"] = str(config_path) if config_path.exists() else "defaults"
    return snapshot


def _config_path(path: Optional[Path]) -> Path:
    if path is not None:
        return Path(path)
    env_path = os.environ.get("STRATEGY_PROFILE_PATH")
    if env_path:
        return Path(env_path)
    legacy_env_path = os.environ.get("BLACK_NUMBA_CONFIG_PATH")
    if legacy_env_path:
        return Path(legacy_env_path)
    return DEFAULT_STRATEGY_PROFILE_PATH


def _phase(board: chess.Board, config: BlackNumbaConfig) -> str:
    if board.fullmove_number <= config.opening_fullmove_limit:
        return "opening"
    non_king_pieces = 0
    for piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        non_king_pieces += len(board.pieces(piece_type, chess.WHITE))
        non_king_pieces += len(board.pieces(piece_type, chess.BLACK))
    if non_king_pieces <= config.endgame_non_king_piece_threshold:
        return "endgame"
    return "middlegame"


def _load_profile(path: Optional[Path]) -> StrategyProfile:
    return load_strategy_profile(path or _config_path(path))


def _from_strategy_profile(profile: StrategyProfile) -> BlackNumbaConfig:
    external = profile.external_engine
    phase = profile.phase
    return BlackNumbaConfig(
        enabled=external.enabled,
        minimum_external_budget_ms=external.minimum_external_budget_ms,
        time_buffer_ms=external.time_buffer_ms,
        low_time_threshold_ms=external.low_time_threshold_ms,
        opening_fullmove_limit=phase.opening_fullmove_limit,
        endgame_non_king_piece_threshold=phase.endgame_non_king_piece_threshold,
        opening_depth_limit=external.opening_depth_limit,
        opening_node_limit=external.opening_node_limit,
        middlegame_depth_limit=external.middlegame_depth_limit,
        middlegame_node_limit=external.middlegame_node_limit,
        endgame_depth_limit=external.endgame_depth_limit,
        endgame_node_limit=external.endgame_node_limit,
        low_time_depth_limit=external.low_time_depth_limit,
        low_time_node_limit=external.low_time_node_limit,
    )


def _legacy_override_payload(observation: Any) -> Dict[str, Any]:
    if not isinstance(observation, dict):
        return {}
    override = observation.get("black_numba_config")
    return override if isinstance(override, dict) else {}
