"""Structured strategy profile for the chess playing agent."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STRATEGY_PROFILE_PATH = ROOT / "config/strategy_profile.json"


class SearchProfile(BaseModel):
    default_depth: int = 3
    max_depth: int = 4
    min_time_margin_ms: int = 4
    quiescence_depth: int = 8
    tt_move_bonus: int = 50_000
    history_bonus_scale: int = 1
    history_bonus_power: int = 2
    root_mate_stop_distance: int = 1
    mate_detection_margin: int = 1_000


class PieceValuesProfile(BaseModel):
    pawn: int = 100
    knight: int = 320
    bishop: int = 330
    rook: int = 500
    queen: int = 900


class EvalProfile(BaseModel):
    material_weight: float = 1.0
    mobility_weight: float = 1.0
    piece_activity_weight: float = 1.0
    pawn_structure_weight: float = 1.0
    king_safety_weight: float = 1.0
    draw_score: int = 0
    mate_score: int = 100_000
    missing_king_penalty: int = 500


class PieceActivityProfile(BaseModel):
    center_bonus: int = 15
    extended_center_bonus: int = 6
    minor_base_bonus: int = 8
    minor_rank_bonus_weight: int = 2
    minor_center_distance_penalty: int = 2
    rook_open_file_bonus: int = 18
    rook_half_open_file_bonus: int = 9


class PawnStructureProfile(BaseModel):
    advance_bonus_per_rank: int = 3
    doubled_penalty: int = 8
    isolated_penalty: int = 10


class KingSafetyProfile(BaseModel):
    attacked_king_penalty: int = 70
    pawn_shield_bonus: int = 7
    piece_shield_bonus: int = 3
    attacked_ring_penalty: int = 2


class MoveOrderingProfile(BaseModel):
    capture_base_bonus: int = 1_000
    capture_victim_multiplier: int = 10
    capture_attacker_penalty: int = 1
    promotion_bonus: int = 800
    check_bonus: int = 300
    castling_bonus: int = 150
    center_bonus: int = 40
    extended_center_bonus: int = 15
    minor_development_bonus: int = 30
    center_pawn_development_bonus: int = 18
    early_queen_penalty: int = 25
    early_rook_penalty: int = 10


class PhaseProfile(BaseModel):
    opening_fullmove_limit: int = 10
    endgame_non_king_piece_threshold: int = 10


class ExternalEngineProfile(BaseModel):
    enabled: bool = False
    minimum_external_budget_ms: int = 60
    time_buffer_ms: int = 8
    low_time_threshold_ms: int = 80
    opening_depth_limit: int = 4
    opening_node_limit: int = 2_000_000
    middlegame_depth_limit: int = 4
    middlegame_node_limit: int = 4_000_000
    endgame_depth_limit: int = 5
    endgame_node_limit: int = 8_000_000
    low_time_depth_limit: int = 2
    low_time_node_limit: int = 250_000


class StrategyProfile(BaseModel):
    profile_name: str = "default"
    search: SearchProfile = Field(default_factory=SearchProfile)
    piece_values: PieceValuesProfile = Field(default_factory=PieceValuesProfile)
    eval: EvalProfile = Field(default_factory=EvalProfile)
    piece_activity: PieceActivityProfile = Field(default_factory=PieceActivityProfile)
    pawn_structure: PawnStructureProfile = Field(default_factory=PawnStructureProfile)
    king_safety: KingSafetyProfile = Field(default_factory=KingSafetyProfile)
    move_ordering: MoveOrderingProfile = Field(default_factory=MoveOrderingProfile)
    phase: PhaseProfile = Field(default_factory=PhaseProfile)
    external_engine: ExternalEngineProfile = Field(default_factory=ExternalEngineProfile)


def load_strategy_profile(path: Optional[Path] = None) -> StrategyProfile:
    config_path = _config_path(path)
    if not config_path.exists():
        return StrategyProfile()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if _looks_like_legacy_black_numba_config(payload):
        return _legacy_black_numba_to_strategy_profile(payload)
    return StrategyProfile.model_validate(payload)


def resolve_strategy_profile(
    observation: Any = None,
    path: Optional[Path] = None,
) -> Tuple[StrategyProfile, str]:
    config_path = _config_path(path)
    profile = load_strategy_profile(path)
    source = str(config_path) if config_path.exists() else "defaults"

    override = _override_payload(observation)
    if override:
        merged = _deep_merge(profile.model_dump(), override)
        profile = StrategyProfile.model_validate(merged)
        source = "observation_override"
    return profile, source


def strategy_profile_snapshot(path: Optional[Path] = None) -> Dict[str, Any]:
    config_path = _config_path(path)
    profile = load_strategy_profile(path)
    snapshot = profile.model_dump()
    snapshot["source"] = str(config_path) if config_path.exists() else "defaults"
    return snapshot


def _config_path(path: Optional[Path]) -> Path:
    if path is not None:
        return Path(path)
    env_path = os.environ.get("STRATEGY_PROFILE_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_STRATEGY_PROFILE_PATH


def _override_payload(observation: Any) -> Dict[str, Any]:
    if not isinstance(observation, dict):
        return {}
    override = observation.get("strategy_profile")
    if isinstance(override, dict):
        return override
    engine_override = observation.get("engine_config")
    if isinstance(engine_override, dict):
        candidate = engine_override.get("strategy_profile")
        if isinstance(candidate, dict):
            return candidate
    return {}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _looks_like_legacy_black_numba_config(payload: Dict[str, Any]) -> bool:
    return "opening_depth_limit" in payload and "search" not in payload


def _legacy_black_numba_to_strategy_profile(payload: Dict[str, Any]) -> StrategyProfile:
    merged = _deep_merge(
        StrategyProfile().model_dump(),
        {
            "external_engine": payload,
            "phase": {
                "opening_fullmove_limit": payload.get("opening_fullmove_limit", 10),
                "endgame_non_king_piece_threshold": payload.get(
                    "endgame_non_king_piece_threshold",
                    10,
                ),
            },
        },
    )
    return StrategyProfile.model_validate(merged)
