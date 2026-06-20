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

import time
from typing import Any, Iterable, Optional

import chess

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

CENTER = {
    chess.D4,
    chess.E4,
    chess.D5,
    chess.E5,
}

EXTENDED_CENTER = {
    chess.C3,
    chess.D3,
    chess.E3,
    chess.F3,
    chess.C4,
    chess.D4,
    chess.E4,
    chess.F4,
    chess.C5,
    chess.D5,
    chess.E5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
}

MATE_SCORE = 100_000
MIN_TIME_MARGIN_MS = 4


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
    started = time.monotonic()
    board = _parse_observation(observation)

    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    best_move: Optional[chess.Move] = None
    best_score = -10**9

    for candidate in _ordered_moves(board, legal_moves):
        if _time_exceeded(started, time_limit_ms):
            break
        if candidate not in board.legal_moves:
            continue

        score = _score_move(board, candidate, started, time_limit_ms)
        if best_move is None or score > best_score:
            best_move = candidate
            best_score = score
        elif score == best_score and candidate.uci() < best_move.uci():
            best_move = candidate

    if best_move not in board.legal_moves:
        best_move = _first_legal(board)
    if best_move is None:
        return ""
    return _format_move(board, best_move, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = _extract_fen(observation)
    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass

    if isinstance(observation, str):
        text = observation.strip()
        if text:
            try:
                return chess.Board(text)
            except ValueError:
                pass

    return chess.Board()


def _extract_fen(observation: Any) -> Optional[str]:
    if isinstance(observation, dict):
        for key in ("fen", "board", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        nested = observation.get("observation")
        if nested is not observation:
            return _extract_fen(nested)
        return None

    for attr in ("fen", "board", "position"):
        value = getattr(observation, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = getattr(observation, "observation", None)
    if nested is not None and nested is not observation:
        return _extract_fen(nested)
    return None


def _ordered_moves(
    board: chess.Board,
    legal_moves: Iterable[chess.Move],
) -> list[chess.Move]:
    moves = list(legal_moves)
    moves.sort(key=lambda item: (-_move_order_key(board, item), item.uci()))
    return moves


def _move_order_key(board: chess.Board, move_obj: chess.Move) -> int:
    score = 0
    victim = _captured_piece(board, move_obj)
    attacker = board.piece_at(move_obj.from_square)

    if victim is not None:
        victim_value = PIECE_VALUES.get(victim.piece_type, 0)
        attacker_value = 0
        if attacker is not None:
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 0)
        score += 1000 + 10 * victim_value - attacker_value
    if move_obj.promotion:
        score += PIECE_VALUES.get(move_obj.promotion, 0) + 800
    if board.gives_check(move_obj):
        score += 300
    if move_obj.to_square in CENTER:
        score += 40
    elif move_obj.to_square in EXTENDED_CENTER:
        score += 15
    return score


def _score_move(
    board: chess.Board,
    move_obj: chess.Move,
    started: float,
    time_limit_ms: int,
) -> int:
    side = board.turn
    moving_piece = board.piece_at(move_obj.from_square)
    score = _static_move_bonus(board, move_obj, moving_piece)
    before_eval = _evaluate(board, side)

    board.push(move_obj)
    try:
        if board.is_checkmate():
            return MATE_SCORE + score
        if board.is_stalemate() or board.is_insufficient_material():
            score -= 250

        score += _evaluate(board, side) - before_eval
        score -= _hanging_penalty(board, move_obj, moving_piece, side)

        if not _time_near_limit(started, time_limit_ms):
            score -= _reply_danger(board, side, started, time_limit_ms)
    finally:
        board.pop()

    return score


def _static_move_bonus(
    board: chess.Board,
    move_obj: chess.Move,
    moving_piece: Optional[chess.Piece],
) -> int:
    score = 0
    captured = _captured_piece(board, move_obj)

    if captured is not None:
        victim_value = PIECE_VALUES.get(captured.piece_type, 0)
        attacker_value = 0
        if moving_piece is not None:
            attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0)
        score += 9 * victim_value - attacker_value // 2

    if move_obj.promotion:
        score += PIECE_VALUES.get(move_obj.promotion, 0) + 150
    if move_obj.to_square in CENTER:
        score += 35
    elif move_obj.to_square in EXTENDED_CENTER:
        score += 12
    if board.gives_check(move_obj):
        score += 75
    if board.is_castling(move_obj):
        score += 100
    score += _development_bonus(board, move_obj, moving_piece)
    return score


def _captured_piece(
    board: chess.Board,
    move_obj: chess.Move,
) -> Optional[chess.Piece]:
    captured = board.piece_at(move_obj.to_square)
    if captured is None and board.is_en_passant(move_obj):
        return chess.Piece(chess.PAWN, not board.turn)
    return captured


def _development_bonus(
    board: chess.Board,
    move_obj: chess.Move,
    moving_piece: Optional[chess.Piece],
) -> int:
    if moving_piece is None:
        return 0

    bonus = 0
    piece_type = moving_piece.piece_type
    color = moving_piece.color
    from_rank = chess.square_rank(move_obj.from_square)
    home_rank = 0 if color == chess.WHITE else 7

    if piece_type in (chess.KNIGHT, chess.BISHOP) and from_rank == home_rank:
        bonus += 30
    if piece_type == chess.PAWN and move_obj.to_square in CENTER:
        bonus += 18
    if board.fullmove_number <= 10 and piece_type == chess.QUEEN:
        bonus -= 25
    if board.fullmove_number <= 10 and piece_type == chess.ROOK:
        if not board.is_castling(move_obj):
            bonus -= 10
    return bonus


def _hanging_penalty(
    board_after: chess.Board,
    move_obj: chess.Move,
    moving_piece: Optional[chess.Piece],
    side: bool,
) -> int:
    if moving_piece is None or moving_piece.piece_type == chess.KING:
        return 0
    square = move_obj.to_square
    if not board_after.is_attacked_by(not side, square):
        return 0

    value = PIECE_VALUES.get(moving_piece.piece_type, 0)
    defended = board_after.is_attacked_by(side, square)
    return value // 5 if defended else value // 2


def _reply_danger(
    board_after: chess.Board,
    side: bool,
    started: float,
    time_limit_ms: int,
) -> int:
    replies = _ordered_moves(board_after, list(board_after.legal_moves))
    worst = 0

    for index, reply in enumerate(replies):
        if index >= 80 or _time_near_limit(started, time_limit_ms):
            break

        danger = 0
        captured = _captured_piece(board_after, reply)
        attacker = board_after.piece_at(reply.from_square)

        if captured is not None:
            victim_value = PIECE_VALUES.get(captured.piece_type, 0)
            attacker_value = 0
            if attacker is not None:
                attacker_value = PIECE_VALUES.get(attacker.piece_type, 0)
            danger += 9 * victim_value - attacker_value // 2
        if reply.promotion:
            danger += PIECE_VALUES.get(reply.promotion, 0)
        if board_after.gives_check(reply):
            danger += 90

        board_after.push(reply)
        try:
            if board_after.is_checkmate():
                return MATE_SCORE
            danger += max(0, _evaluate(board_after, not side) // 20)
        finally:
            board_after.pop()

        if danger > worst:
            worst = danger
    return worst


def _evaluate(board: chess.Board, side: bool) -> int:
    score = _material(board, side)
    score += _piece_activity(board, side)
    score += _pawn_structure(board, side)
    score += _king_safety(board, side)
    return score


def _material(board: chess.Board, side: bool) -> int:
    score = 0
    for piece_type, value in PIECE_VALUES.items():
        score += len(board.pieces(piece_type, side)) * value
        score -= len(board.pieces(piece_type, not side)) * value
    return score


def _piece_activity(board: chess.Board, side: bool) -> int:
    score = 0
    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == side else -1
        if square in CENTER:
            score += sign * 16
        elif square in EXTENDED_CENTER:
            score += sign * 6
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            score += sign * _minor_piece_square_bonus(square, piece.color)
        elif piece.piece_type == chess.ROOK:
            score += sign * _rook_file_bonus(board, square, piece.color)
    return score


def _minor_piece_square_bonus(square: chess.Square, color: bool) -> int:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    if color == chess.BLACK:
        rank_index = 7 - rank_index
    file_distance = abs(file_index - 3.5)
    rank_bonus = min(rank_index, 5)
    return int(8 + rank_bonus * 2 - file_distance * 2)


def _rook_file_bonus(board: chess.Board, square: chess.Square, color: bool) -> int:
    file_index = chess.square_file(square)
    own_pawns = board.pieces(chess.PAWN, color)
    opp_pawns = board.pieces(chess.PAWN, not color)
    own_on_file = any(chess.square_file(pawn) == file_index for pawn in own_pawns)
    opp_on_file = any(chess.square_file(pawn) == file_index for pawn in opp_pawns)
    if not own_on_file and not opp_on_file:
        return 18
    if not own_on_file:
        return 9
    return 0


def _pawn_structure(board: chess.Board, side: bool) -> int:
    return _pawn_score_for(board, side) - _pawn_score_for(board, not side)


def _pawn_score_for(board: chess.Board, color: bool) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    score = 0
    file_counts = [0] * 8
    for square in pawns:
        file_counts[chess.square_file(square)] += 1

    for square in pawns:
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)
        advance = rank_index if color == chess.WHITE else 7 - rank_index
        score += advance * 3
        if file_counts[file_index] > 1:
            score -= 8
        left_empty = file_index == 0 or file_counts[file_index - 1] == 0
        right_empty = file_index == 7 or file_counts[file_index + 1] == 0
        if left_empty and right_empty:
            score -= 10
    return score


def _king_safety(board: chess.Board, side: bool) -> int:
    return _king_safety_for(board, side) - _king_safety_for(board, not side)


def _king_safety_for(board: chess.Board, color: bool) -> int:
    king_square = board.king(color)
    if king_square is None:
        return -500

    score = 0
    if board.is_attacked_by(not color, king_square):
        score -= 70
    for square in chess.SquareSet(chess.BB_KING_ATTACKS[king_square]):
        piece = board.piece_at(square)
        if piece is not None and piece.color == color:
            score += 7 if piece.piece_type == chess.PAWN else 3
        if board.is_attacked_by(not color, square):
            score -= 2
    return score


def _format_move(board: chess.Board, move_obj: chess.Move, output_format: str) -> str:
    if move_obj not in board.legal_moves:
        fallback = _first_legal(board)
        if fallback is None:
            return ""
        move_obj = fallback

    fmt = (output_format or "uci").lower()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(move_obj)
        except (AssertionError, ValueError):
            return move_obj.uci()
    return move_obj.uci()


def _first_legal(board: chess.Board) -> Optional[chess.Move]:
    for legal in board.legal_moves:
        return legal
    return None


def _time_near_limit(started: float, time_limit_ms: int) -> bool:
    if time_limit_ms <= 0:
        return False
    elapsed_ms = (time.monotonic() - started) * 1000.0
    return elapsed_ms >= max(1, time_limit_ms - MIN_TIME_MARGIN_MS)


def _time_exceeded(started: float, time_limit_ms: int) -> bool:
    if time_limit_ms <= 0:
        return False
    elapsed_ms = (time.monotonic() - started) * 1000.0
    return elapsed_ms >= time_limit_ms
