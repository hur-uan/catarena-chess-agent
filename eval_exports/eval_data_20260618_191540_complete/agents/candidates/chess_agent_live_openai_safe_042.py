"""Safer CATArena chess agent with deterministic tactical guards.

The public entry point remains:
select_move(observation, output_format="uci", time_limit_ms=100) -> str
"""

from __future__ import annotations

from typing import Any

import chess

from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
from tools.board_parser import parse_observation
from tools.strategy_profile import resolve_strategy_profile

DEFAULT_ENGINE_CONFIG = EngineConfig()
MATE_SCORE = 100000
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3,
    chess.D3,
    chess.E3,
    chess.F3,
    chess.C4,
    chess.F4,
    chess.C5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
}


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
    """Return the selected move and lightweight search diagnostics."""
    board = parse_observation(observation)
    legal_moves = list(board.legal_moves)
    legal_uci = [move.uci() for move in legal_moves]
    if not legal_moves or board.is_game_over(claim_draw=False):
        return _make_record(board, "", 0, legal_uci, backend="terminal")

    mate_move = _find_immediate_mate(board, legal_moves)
    if mate_move is not None:
        return _make_record(
            board,
            _format_move(board, mate_move, output_format),
            MATE_SCORE,
            legal_uci,
            depth=1,
            backend="mate_guard",
        )

    strategy_profile, strategy_source = resolve_strategy_profile(observation=observation)
    config = EngineConfig(strategy_profile=strategy_profile)
    record = select_move_record(
        observation=observation,
        output_format=output_format,
        time_limit_ms=time_limit_ms,
        config=config,
    )
    record.engine_config = {
        "profile_name": strategy_profile.profile_name,
        "strategy_source": strategy_source,
        "external_engine": "disabled_for_match_safety",
    }

    selected_move = _parse_selected_move(board, record.selected_move)
    if selected_move is None:
        fallback = _best_fallback_move(board, legal_moves)
        return _make_record(
            board,
            _format_move(board, fallback, output_format),
            _static_board_score_after(board, fallback),
            legal_uci,
            depth=0,
            backend="legal_fallback",
            fallback_used=True,
        )

    if _allows_opponent_mate_in_one(board, selected_move):
        safer_move = _best_mate_safe_alternative(board, legal_moves)
        if safer_move is not None and safer_move != selected_move:
            return _make_record(
                board,
                _format_move(board, safer_move, output_format),
                _static_board_score_after(board, safer_move),
                legal_uci,
                depth=1,
                backend="mate_blunder_guard",
                fallback_used=True,
            )

    record.selected_move = _format_move(board, selected_move, output_format)
    record.legal_moves = legal_uci
    return record


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _format_move(board: chess.Board, move: chess.Move, output_format: str) -> str:
    normalized = output_format.lower().strip()
    if normalized == "san":
        return board.san(move)
    return move.uci()


def _parse_selected_move(board: chess.Board, selected: str) -> chess.Move | None:
    text = str(selected or "").strip()
    if not text:
        return None
    try:
        move = chess.Move.from_uci(text)
    except ValueError:
        try:
            move = board.parse_san(text)
        except ValueError:
            return None
    return move if move in board.legal_moves else None


def _find_immediate_mate(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move | None:
    mate_moves: list[chess.Move] = []
    for candidate in legal_moves:
        board.push(candidate)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            mate_moves.append(candidate)
    if not mate_moves:
        return None
    return max(mate_moves, key=lambda move: _move_order_score(board, move))


def _allows_opponent_mate_in_one(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    if board.is_checkmate() or board.is_game_over(claim_draw=False):
        board.pop()
        return False
    for reply in board.legal_moves:
        board.push(reply)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            board.pop()
            return True
    board.pop()
    return False


def _best_mate_safe_alternative(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move | None:
    safe_moves = [move for move in legal_moves if not _allows_opponent_mate_in_one(board, move)]
    if not safe_moves:
        return None
    return max(safe_moves, key=lambda move: _static_board_score_after(board, move))


def _best_fallback_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move:
    safe = _best_mate_safe_alternative(board, legal_moves)
    if safe is not None:
        return safe
    return max(legal_moves, key=lambda move: _move_order_score(board, move))


def _static_board_score_after(board: chess.Board, move: chess.Move) -> int:
    board.push(move)
    score = _material_score(board) + _king_safety_score(board) + _mobility_score(board)
    if board.is_checkmate():
        score += MATE_SCORE
    board.pop()
    return score


def _material_score(board: chess.Board) -> int:
    score = 0
    perspective = not board.turn
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES.get(piece.piece_type, 0)
        if piece.color == perspective:
            score += value
            if square in CENTER_SQUARES:
                score += 8
            elif square in EXTENDED_CENTER:
                score += 3
        else:
            score -= value
    return score


def _king_safety_score(board: chess.Board) -> int:
    perspective = not board.turn
    own_king = board.king(perspective)
    enemy_king = board.king(not perspective)
    score = 0
    if own_king is not None:
        score -= 18 * len(board.attackers(not perspective, own_king))
    if enemy_king is not None:
        score += 18 * len(board.attackers(perspective, enemy_king))
    return score


def _mobility_score(board: chess.Board) -> int:
    turn = board.turn
    own_count = board.legal_moves.count()
    board.turn = not turn
    try:
        enemy_count = board.legal_moves.count()
    finally:
        board.turn = turn
    return 2 * (enemy_count - own_count)


def _move_order_score(board: chess.Board, move: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_at(move.from_square)
    captured_piece = board.piece_at(move.to_square)
    if captured_piece is not None:
        attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0
        victim_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
        score += 1000 + 10 * victim_value - attacker_value
    if move.promotion:
        score += 800 + PIECE_VALUES.get(move.promotion, 0)
    if board.gives_check(move):
        score += 300
    if board.is_castling(move):
        score += 150
    if move.to_square in CENTER_SQUARES:
        score += 40
    elif move.to_square in EXTENDED_CENTER:
        score += 15
    if moving_piece is not None and moving_piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        home_rank = chess.square_rank(move.from_square)
        if home_rank in {0, 7}:
            score += 25
    return score


def _make_record(
    board: chess.Board,
    selected_move: str,
    cp: int,
    legal_moves: list[str],
    depth: int = 0,
    backend: str = "internal_guard",
    fallback_used: bool = False,
) -> SearchRecord:
    return SearchRecord(
        fen=board.fen(),
        selected_move=selected_move,
        cp=cp,
        mate_distance=1 if cp >= MATE_SCORE else None,
        wdl=cp_to_wdl(cp, 1 if cp >= MATE_SCORE else None),
        depth=depth,
        elapsed_ms=0.0,
        nodes=0,
        qnodes=0,
        legal_moves=legal_moves,
        fallback_used=fallback_used,
        backend=backend,
    )
