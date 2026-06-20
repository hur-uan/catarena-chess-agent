"""CATArena-facing chess playing agent.

The public functions intentionally include several common names (`agent`, `act`,
`move`, `select_move`) so the module can be adapted to the official demo entry
point with minimal changes once the CATArena checkout is available locally.
"""

from __future__ import annotations

import time
from typing import Any, List, Optional

import chess

from tools.board_parser import extract_legal_moves, parse_observation
from tools.move_formatter import format_move
from tools.move_validator import coerce_move, first_legal_move, validate_move

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5, chess.C4, chess.F4, chess.C5, chess.F5}


class ChessAgent:
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
    started = time.monotonic()
    board = parse_observation(observation)
    if board.is_game_over():
        return ""

    candidates = _candidate_moves(board, observation)
    best_move: Optional[chess.Move] = None
    best_score = -10**9

    for move in candidates:
        if _time_exceeded(started, time_limit_ms):
            break
        result = validate_move(board, move)
        if not result.is_legal or not result.normalized_move:
            continue
        legal_move = chess.Move.from_uci(result.normalized_move)
        score = _score_move(board, legal_move)
        if score > best_score:
            best_move = legal_move
            best_score = score

    if best_move is None:
        best_move = first_legal_move(board)
    if best_move is None:
        return ""
    return format_move(board, best_move, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _candidate_moves(board: chess.Board, observation: Any) -> List[chess.Move]:
    hinted = []
    for raw_move in extract_legal_moves(observation):
        move_obj = coerce_move(board, raw_move)
        if move_obj is not None and move_obj in board.legal_moves:
            hinted.append(move_obj)
    if hinted:
        return hinted
    return list(board.legal_moves)


def _score_move(board: chess.Board, move: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_at(move.from_square)
    captured_piece = board.piece_at(move.to_square)

    if board.is_en_passant(move):
        captured_piece = chess.Piece(chess.PAWN, not board.turn)

    if captured_piece is not None:
        victim = PIECE_VALUES.get(captured_piece.piece_type, 0)
        attacker = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0
        score += 10 * victim - attacker

    if move.promotion:
        score += PIECE_VALUES.get(move.promotion, 0)

    if move.to_square in CENTER_SQUARES:
        score += 35

    if board.gives_check(move):
        score += 60

    if board.is_castling(move):
        score += 40

    score += _material_delta_after(board, move)

    board.push(move)
    try:
        if board.is_checkmate():
            score += 100000
        elif board.is_stalemate():
            score -= 200
    finally:
        board.pop()

    return score


def _material_delta_after(board: chess.Board, move: chess.Move) -> int:
    color = board.turn
    before = _material_balance(board, color)
    board.push(move)
    try:
        after = _material_balance(board, color)
    finally:
        board.pop()
    return after - before


def _material_balance(board: chess.Board, color: bool) -> int:
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        total += len(board.pieces(piece_type, color)) * value
        total -= len(board.pieces(piece_type, not color)) * value
    return total


def _time_exceeded(started: float, time_limit_ms: int) -> bool:
    if time_limit_ms <= 0:
        return False
    elapsed_ms = (time.monotonic() - started) * 1000
    return elapsed_ms >= time_limit_ms

