"""FEN-based pre-screening to extract stronger local tuning signals."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import chess
from pydantic import BaseModel, Field

from agents.engine import EngineConfig, evaluate_board, search_best_move
from tools.black_numba_client import (
    BlackNumbaUnavailable,
    analyze_position,
    is_black_numba_available,
)
from tools.strategy_profile import StrategyProfile


class PrescreenPosition(BaseModel):
    name: str
    fen: str


class PrescreenConfig(BaseModel):
    candidate_time_limit_ms: int = 40
    oracle_time_limit_ms: int = 120
    force_internal_engine: bool = True
    signal_mode: str = "line_quality"
    prescreen_set: str = ""
    use_external_oracle: bool = True
    external_oracle_depth_limit: int = 5
    external_oracle_node_limit: int = 2_000_000
    external_oracle_response_timeout_seconds: float = 1.0
    positions: List[PrescreenPosition] = Field(default_factory=list)


class PrescreenCaseResult(BaseModel):
    name: str
    fen: str
    oracle_move: str = ""
    move_a: str = ""
    move_b: str = ""
    score_a: float = 0.5
    score_b: float = 0.5
    oracle_line_cp: int = 0
    root_score_a_cp: int = 0
    root_score_b_cp: int = 0
    line_score_a_cp: int = 0
    line_score_b_cp: int = 0
    cp_loss_a: int = 0
    cp_loss_b: int = 0
    calibration_gap_a: int = 0
    calibration_gap_b: int = 0
    depth_a: int = 0
    depth_b: int = 0
    nodes_a: int = 0
    nodes_b: int = 0
    tt_hits_a: int = 0
    tt_hits_b: int = 0
    cutoffs_a: int = 0
    cutoffs_b: int = 0


class PrescreenSummary(BaseModel):
    positions: int = 0
    mean_score_a: float = 0.5
    mean_score_b: float = 0.5
    score_difference: float = 0.0
    results: List[PrescreenCaseResult] = Field(default_factory=list)


def run_fen_prescreen(
    profile_a: StrategyProfile,
    profile_b: StrategyProfile,
    baseline_profile: Optional[StrategyProfile] = None,
    config: Optional[PrescreenConfig] = None,
) -> PrescreenSummary:
    prescreen_config = config or PrescreenConfig()
    positions = prescreen_config.positions or resolve_prescreen_positions(
        prescreen_config.signal_mode,
        prescreen_config.prescreen_set,
    )
    oracle_profile = _oracle_profile(baseline_profile or profile_a, prescreen_config)
    candidate_a = _prepared_profile(profile_a, prescreen_config)
    candidate_b = _prepared_profile(profile_b, prescreen_config)
    root_reference_cache: Dict[str, Tuple[str, int]] = {}
    oracle_score_cache: Dict[str, int] = {}

    results: List[PrescreenCaseResult] = []
    score_total_a = 0.0
    score_total_b = 0.0
    for position in positions:
        board = chess.Board(position.fen)
        oracle_move, oracle_cp = _oracle_root_reference(
            board,
            oracle_profile,
            prescreen_config,
            root_reference_cache,
        )
        if prescreen_config.signal_mode == "static_eval":
            case_a = _static_eval_case(board, candidate_a, oracle_move, oracle_cp)
            case_b = _static_eval_case(board, candidate_b, oracle_move, oracle_cp)
        elif prescreen_config.signal_mode == "search_behavior":
            case_a = _search_behavior_case(
                board,
                candidate_a,
                oracle_profile,
                oracle_move,
                oracle_cp,
                prescreen_config,
                oracle_score_cache,
            )
            case_b = _search_behavior_case(
                board,
                candidate_b,
                oracle_profile,
                oracle_move,
                oracle_cp,
                prescreen_config,
                oracle_score_cache,
            )
        else:
            case_a = _line_quality_case(
                board,
                candidate_a,
                oracle_profile,
                oracle_move,
                oracle_cp,
                prescreen_config,
                oracle_score_cache,
            )
            case_b = _line_quality_case(
                board,
                candidate_b,
                oracle_profile,
                oracle_move,
                oracle_cp,
                prescreen_config,
                oracle_score_cache,
            )
        score_total_a += float(case_a["score"])
        score_total_b += float(case_b["score"])
        results.append(
            PrescreenCaseResult(
                name=position.name,
                fen=position.fen,
                oracle_move=oracle_move,
                move_a=str(case_a["move"]),
                move_b=str(case_b["move"]),
                score_a=float(case_a["score"]),
                score_b=float(case_b["score"]),
                oracle_line_cp=oracle_cp,
                root_score_a_cp=int(case_a["root_score_cp"]),
                root_score_b_cp=int(case_b["root_score_cp"]),
                line_score_a_cp=int(case_a["line_score_cp"]),
                line_score_b_cp=int(case_b["line_score_cp"]),
                cp_loss_a=int(case_a["cp_loss"]),
                cp_loss_b=int(case_b["cp_loss"]),
                calibration_gap_a=int(case_a["calibration_gap"]),
                calibration_gap_b=int(case_b["calibration_gap"]),
                depth_a=int(case_a.get("depth", 0)),
                depth_b=int(case_b.get("depth", 0)),
                nodes_a=int(case_a.get("nodes", 0)),
                nodes_b=int(case_b.get("nodes", 0)),
                tt_hits_a=int(case_a.get("tt_hits", 0)),
                tt_hits_b=int(case_b.get("tt_hits", 0)),
                cutoffs_a=int(case_a.get("cutoffs", 0)),
                cutoffs_b=int(case_b.get("cutoffs", 0)),
            )
        )
    count = len(results)
    if count == 0:
        return PrescreenSummary()
    mean_a = score_total_a / count
    mean_b = score_total_b / count
    return PrescreenSummary(
        positions=count,
        mean_score_a=mean_a,
        mean_score_b=mean_b,
        score_difference=mean_a - mean_b,
        results=results,
    )


def default_prescreen_positions() -> List[PrescreenPosition]:
    return [
        PrescreenPosition(
            name="mate_in_one_white",
            fen="6k1/5Q2/6K1/8/8/8/8/8 w - - 0 1",
        ),
        PrescreenPosition(
            name="mate_in_one_black",
            fen="8/8/8/8/8/6k1/5q2/6K1 b - - 0 1",
        ),
        PrescreenPosition(
            name="sharp_midgame_1",
            fen="r2q1k1r/2pnppb1/pp4pn/3N2Np/3P2bP/4B1P1/PPP1PPB1/R2Q1RK1 w - - 0 11",
        ),
        PrescreenPosition(
            name="sharp_midgame_2",
            fen="r1bq1rk1/pp1n1pbp/2pp1np1/4p3/2PPP3/2N1BN1P/PPQ2PP1/R3KB1R w KQ - 2 9",
        ),
        PrescreenPosition(
            name="isolated_pawn_tension",
            fen="2r2rk1/pp1q1ppp/2n1pn2/2bp4/3P4/2NBPN2/PPQ2PPP/2RR2K1 w - - 0 12",
        ),
        PrescreenPosition(
            name="rook_endgame",
            fen="8/5pk1/3p2p1/2pP4/2P1r3/4R1P1/5PK1/8 w - - 0 35",
        ),
    ]


def default_static_prescreen_positions() -> List[PrescreenPosition]:
    return [
        position
        for position in default_prescreen_positions()
        if not position.name.startswith("mate_")
    ]


def _default_positions_for_mode(signal_mode: str) -> List[PrescreenPosition]:
    if signal_mode == "static_eval":
        return default_static_prescreen_positions()
    return default_prescreen_positions()


def resolve_prescreen_positions(
    signal_mode: str,
    prescreen_set: str = "",
) -> List[PrescreenPosition]:
    key = prescreen_set.strip().lower()
    if not key:
        return _default_positions_for_mode(signal_mode)
    presets = {
        "search.depth_time": search_depth_time_positions(),
        "search.history_order": search_history_order_positions(),
        "move_ordering.tactical": move_ordering_tactical_positions(),
        "move_ordering.development": move_ordering_development_positions(),
        "piece_values": piece_value_positions(),
        "phase": phase_transition_positions(),
    }
    return list(presets.get(key, _default_positions_for_mode(signal_mode)))


def search_depth_time_positions() -> List[PrescreenPosition]:
    return [
        PrescreenPosition(
            name="forcing_check_chain",
            fen="6k1/5ppp/5n2/8/3Q4/5P2/5KPP/8 w - - 0 1",
        ),
        PrescreenPosition(
            name="mate_net_defense",
            fen="r5k1/5ppp/3Q4/8/8/6P1/5P1P/6K1 w - - 0 1",
        ),
        PrescreenPosition(
            name="low_budget_opening_black_1",
            fen="rn1qkb1r/ppp1pppp/7n/3p4/3P4/1P5P/P1PKPP1P/RNBQ1BNR b kq - 0 4",
        ),
        PrescreenPosition(
            name="low_budget_opening_white_1",
            fen="rnbqkbnr/pp1ppp1p/6p1/2p5/6P1/7B/PPPPPP1P/RNBQK1NR w KQkq - 0 3",
        ),
        PrescreenPosition(
            name="low_budget_opening_black_2",
            fen="r1bqkbnr/pppnp1pp/3p1p2/8/PP3P2/3P4/2P1P1PP/RNBQKBNR b KQkq - 0 4",
        ),
        PrescreenPosition(
            name="endgame_precision",
            fen="8/5pk1/3p2p1/2pP4/2P1r3/4R1P1/5PK1/8 w - - 0 35",
        ),
    ]


def search_history_order_positions() -> List[PrescreenPosition]:
    return [
        PrescreenPosition(
            name="ordering_branch_white_1",
            fen="rnbqkbn1/pp1ppp1r/6p1/2p4p/P4P2/4P3/1PPPK1PP/RNBQ1BNR w q - 1 5",
        ),
        PrescreenPosition(
            name="ordering_branch_white_2",
            fen="rnbqkbnr/3ppp2/p7/1Pp3pp/P7/7P/RP1PPPP1/1NBQKBNR w Kkq - 0 6",
        ),
        PrescreenPosition(
            name="ordering_branch_white_3",
            fen="rn1qkb1r/p1pppp1p/b5pn/1P6/8/6PN/PP1PPP1P/RNBQKB1R w KQkq - 2 5",
        ),
        PrescreenPosition(
            name="ordering_branch_white_4",
            fen="r1b1kb1r/pp1ppppp/7n/n7/2P5/6P1/P2NPP1P/R1BQKBNR w KQkq - 1 9",
        ),
        PrescreenPosition(
            name="ordering_branch_white_5",
            fen="r1bqkbnr/ppppp2p/5pp1/8/1P2P3/N7/1P1PNPPP/1RBQKB1R w Kkq - 0 7",
        ),
    ]


def move_ordering_tactical_positions() -> List[PrescreenPosition]:
    return [
        PrescreenPosition(
            name="promotion_race",
            fen="6k1/5P2/6K1/8/8/8/8/8 w - - 0 1",
        ),
        PrescreenPosition(
            name="capture_or_check",
            fen="r3k2r/pp3ppp/2n5/3q4/3P4/2N5/PP3PPP/R2Q1RK1 w kq - 0 1",
        ),
        PrescreenPosition(
            name="castle_or_tactic",
            fen="r1bqk2r/pppp1ppp/2n2n2/4p3/3PP1b1/2N2N2/PPP2PPP/R1BQKB1R w KQkq - 4 5",
        ),
        PrescreenPosition(
            name="forcing_capture",
            fen="4r1k1/pp3ppp/2n5/3q4/3P4/2NQ4/PP3PPP/4R1K1 w - - 0 1",
        ),
    ]


def move_ordering_development_positions() -> List[PrescreenPosition]:
    return [
        PrescreenPosition(
            name="minor_development",
            fen="rnbqkb1r/pppp1ppp/5n2/4p3/3P4/2N5/PPP1PPPP/R1BQKBNR w KQkq - 2 3",
        ),
        PrescreenPosition(
            name="early_queen_temptation",
            fen="rnb1kbnr/pppp1ppp/8/4p3/3q4/2N5/PPP1PPPP/R1BQKBNR w KQkq - 0 3",
        ),
        PrescreenPosition(
            name="center_pawn_push",
            fen="rnbqkb1r/pppp1ppp/5n2/8/3p4/2N5/PPP1PPPP/R1BQKBNR w KQkq - 0 3",
        ),
        PrescreenPosition(
            name="castle_develop_balance",
            fen="r1bqk1nr/pppp1ppp/2n5/2b1p3/3PP3/2N2N2/PPP2PPP/R1BQKB1R w KQkq - 4 5",
        ),
    ]


def piece_value_positions() -> List[PrescreenPosition]:
    return [
        PrescreenPosition(
            name="bishop_vs_knight_tension",
            fen="4k3/8/3n4/8/3B4/8/8/4K3 w - - 0 1",
        ),
        PrescreenPosition(
            name="exchange_sac_balance",
            fen="4k3/8/8/3r4/8/3R4/4P3/4K3 w - - 0 1",
        ),
        PrescreenPosition(
            name="queen_trade_bias",
            fen="4k3/8/8/3q4/8/3Q4/4P3/4K3 w - - 0 1",
        ),
        PrescreenPosition(
            name="rook_endgame_material",
            fen="8/5pk1/3p2p1/2pP4/2P1r3/4R1P1/5PK1/8 w - - 0 35",
        ),
    ]


def phase_transition_positions() -> List[PrescreenPosition]:
    return [
        PrescreenPosition(
            name="opening_boundary",
            fen="r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/2N2N2/PPP2PPP/R1BQKB1R b KQkq - 3 4",
        ),
        PrescreenPosition(
            name="middlegame_boundary",
            fen="r2q1rk1/pp2bppp/2np1n2/2p1p3/2P1P3/2NP1N2/PPQ1BPPP/R1B2RK1 w - - 0 9",
        ),
        PrescreenPosition(
            name="endgame_boundary",
            fen="8/5pk1/3p2p1/2pP4/2P1r3/4R1P1/5PK1/8 w - - 0 35",
        ),
        PrescreenPosition(
            name="reduced_material_transition",
            fen="8/2k5/3p4/2pP4/2P5/4K3/8/8 w - - 0 1",
        ),
    ]


def _line_quality_case(
    board: chess.Board,
    candidate_profile: StrategyProfile,
    oracle_profile: StrategyProfile,
    oracle_move: str,
    oracle_cp: int,
    config: PrescreenConfig,
    oracle_score_cache: Dict[str, int],
) -> dict[str, object]:
    candidate_result = search_best_move(
        board,
        time_limit_ms=config.candidate_time_limit_ms,
        config=EngineConfig(strategy_profile=candidate_profile),
    )
    if candidate_result.move is None:
        return {
            "move": "",
            "score": 0.0,
            "root_score_cp": 0,
            "line_score_cp": -100000,
            "cp_loss": 100000,
            "calibration_gap": 100000,
        }
    candidate_move = candidate_result.move.uci()
    line_score_cp = _line_score_after_move(
        board,
        candidate_result.move,
        oracle_profile,
        config,
        oracle_score_cache,
    )
    cp_loss = oracle_cp - line_score_cp
    calibration_gap = abs(candidate_result.score_cp - line_score_cp)
    move_match_bonus = 0.05 if candidate_move == oracle_move else 0.0
    quality_score = _score_from_positive_gap(cp_loss, scale=160.0)
    calibration_score = _score_from_abs_gap(calibration_gap, scale=220.0)
    total_score = min(1.0, quality_score * 0.75 + calibration_score * 0.20 + move_match_bonus)
    return {
        "move": candidate_move,
        "score": total_score,
        "root_score_cp": candidate_result.score_cp,
        "line_score_cp": line_score_cp,
        "cp_loss": cp_loss,
        "calibration_gap": calibration_gap,
        "depth": candidate_result.depth,
        "nodes": candidate_result.stats.nodes,
        "tt_hits": candidate_result.stats.tt_hits,
        "cutoffs": candidate_result.stats.cutoffs,
    }


def _search_behavior_case(
    board: chess.Board,
    candidate_profile: StrategyProfile,
    oracle_profile: StrategyProfile,
    oracle_move: str,
    oracle_cp: int,
    config: PrescreenConfig,
    oracle_score_cache: Dict[str, int],
) -> dict[str, object]:
    candidate_result = search_best_move(
        board,
        time_limit_ms=config.candidate_time_limit_ms,
        config=EngineConfig(strategy_profile=candidate_profile),
    )
    if candidate_result.move is None:
        return {
            "move": "",
            "score": 0.0,
            "root_score_cp": 0,
            "line_score_cp": -100000,
            "cp_loss": 100000,
            "calibration_gap": 100000,
            "depth": 0,
            "nodes": 0,
            "tt_hits": 0,
            "cutoffs": 0,
        }
    candidate_move = candidate_result.move.uci()
    line_score_cp = _line_score_after_move(
        board,
        candidate_result.move,
        oracle_profile,
        config,
        oracle_score_cache,
    )
    cp_loss = oracle_cp - line_score_cp
    calibration_gap = abs(candidate_result.score_cp - line_score_cp)
    move_match_bonus = 0.03 if candidate_move == oracle_move else 0.0
    quality_score = _score_from_positive_gap(cp_loss, scale=200.0)
    calibration_score = _score_from_abs_gap(calibration_gap, scale=280.0)
    depth_target = max(1, candidate_profile.search.default_depth)
    depth_score = min(1.0, candidate_result.depth / depth_target)
    node_count = max(1, candidate_result.stats.nodes)
    cutoff_score = min(1.0, (candidate_result.stats.cutoffs / node_count) * 18.0)
    tt_score = min(1.0, (candidate_result.stats.tt_hits / node_count) * 24.0)
    total_score = min(
        1.0,
        quality_score * 0.30
        + calibration_score * 0.20
        + depth_score * 0.30
        + cutoff_score * 0.12
        + tt_score * 0.08
        + move_match_bonus,
    )
    return {
        "move": candidate_move,
        "score": total_score,
        "root_score_cp": candidate_result.score_cp,
        "line_score_cp": line_score_cp,
        "cp_loss": cp_loss,
        "calibration_gap": calibration_gap,
        "depth": candidate_result.depth,
        "nodes": candidate_result.stats.nodes,
        "tt_hits": candidate_result.stats.tt_hits,
        "cutoffs": candidate_result.stats.cutoffs,
    }


def _static_eval_case(
    board: chess.Board,
    candidate_profile: StrategyProfile,
    oracle_move: str,
    oracle_cp: int,
) -> dict[str, object]:
    static_score_cp = evaluate_board(board, board.turn, candidate_profile)
    calibration_gap = abs(static_score_cp - oracle_cp)
    sign_bonus = _sign_agreement_bonus(static_score_cp, oracle_cp)
    total_score = min(1.0, _score_from_abs_gap(calibration_gap, scale=200.0) * 0.9 + sign_bonus)
    return {
        "move": "",
        "score": total_score,
        "root_score_cp": static_score_cp,
        "line_score_cp": static_score_cp,
        "cp_loss": calibration_gap,
        "calibration_gap": calibration_gap,
        "oracle_move": oracle_move,
    }


def _oracle_profile(profile: StrategyProfile, config: PrescreenConfig) -> StrategyProfile:
    payload = profile.model_dump()
    if config.force_internal_engine:
        payload["external_engine"]["enabled"] = False
    payload["search"]["default_depth"] = min(payload["search"]["default_depth"] + 1, 6)
    payload["search"]["max_depth"] = min(payload["search"]["max_depth"] + 2, 8)
    payload["search"]["quiescence_depth"] = min(payload["search"]["quiescence_depth"] + 2, 12)
    payload["search"]["min_time_margin_ms"] = max(
        1,
        min(payload["search"]["min_time_margin_ms"], 2),
    )
    return StrategyProfile.model_validate(payload)


def _prepared_profile(profile: StrategyProfile, config: PrescreenConfig) -> StrategyProfile:
    if not config.force_internal_engine:
        return profile
    payload = profile.model_dump()
    payload["external_engine"]["enabled"] = False
    return StrategyProfile.model_validate(payload)


def _oracle_root_reference(
    board: chess.Board,
    oracle_profile: StrategyProfile,
    config: PrescreenConfig,
    root_reference_cache: Dict[str, Tuple[str, int]],
) -> tuple[str, int]:
    fen = board.fen()
    cached = root_reference_cache.get(fen)
    if cached is not None:
        return cached
    if config.use_external_oracle and is_black_numba_available():
        try:
            response = analyze_position(
                fen,
                time_limit_ms=config.oracle_time_limit_ms,
                depth_limit=config.external_oracle_depth_limit,
                node_limit=config.external_oracle_node_limit,
                response_timeout_seconds=config.external_oracle_response_timeout_seconds,
            )
            result = str(response.get("move", "")), int(response.get("score_cp", 0))
            root_reference_cache[fen] = result
            return result
        except BlackNumbaUnavailable:
            config.use_external_oracle = False
    result = search_best_move(
        board,
        time_limit_ms=config.oracle_time_limit_ms,
        config=EngineConfig(strategy_profile=oracle_profile),
    )
    move_text = result.move.uci() if result.move is not None else ""
    reference = move_text, int(result.score_cp)
    root_reference_cache[fen] = reference
    return reference


def _line_score_after_move(
    board: chess.Board,
    move: chess.Move,
    oracle_profile: StrategyProfile,
    config: PrescreenConfig,
    oracle_score_cache: Dict[str, int],
) -> int:
    board_after = board.copy(stack=False)
    board_after.push(move)
    if board_after.is_game_over(claim_draw=True):
        if board_after.is_checkmate():
            return oracle_profile.eval.mate_score
        return oracle_profile.eval.draw_score
    return -_oracle_score_for_board(board_after, oracle_profile, config, oracle_score_cache)


def _oracle_score_for_board(
    board: chess.Board,
    oracle_profile: StrategyProfile,
    config: PrescreenConfig,
    oracle_score_cache: Dict[str, int],
) -> int:
    fen = board.fen()
    cached = oracle_score_cache.get(fen)
    if cached is not None:
        return cached
    if config.use_external_oracle and is_black_numba_available():
        try:
            response = analyze_position(
                fen,
                time_limit_ms=config.oracle_time_limit_ms,
                depth_limit=config.external_oracle_depth_limit,
                node_limit=config.external_oracle_node_limit,
                response_timeout_seconds=config.external_oracle_response_timeout_seconds,
            )
            score = int(response.get("score_cp", 0))
            oracle_score_cache[fen] = score
            return score
        except BlackNumbaUnavailable:
            config.use_external_oracle = False
    result = search_best_move(
        board,
        time_limit_ms=config.oracle_time_limit_ms,
        config=EngineConfig(strategy_profile=oracle_profile),
    )
    score = int(result.score_cp)
    oracle_score_cache[fen] = score
    return score


def _score_from_positive_gap(gap: int, scale: float) -> float:
    if gap <= 0:
        return 1.0
    return 1.0 / (1.0 + (gap / scale))


def _score_from_abs_gap(gap: int, scale: float) -> float:
    return 1.0 / (1.0 + (abs(gap) / scale))


def _sign_agreement_bonus(candidate_cp: int, oracle_cp: int) -> float:
    if abs(candidate_cp) <= 25 and abs(oracle_cp) <= 25:
        return 0.10
    if candidate_cp == 0 or oracle_cp == 0:
        return 0.0
    return 0.10 if (candidate_cp > 0) == (oracle_cp > 0) else 0.0
