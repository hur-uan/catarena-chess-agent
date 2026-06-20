"""Self-contained safe CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent uses only python-chess, performs no network access, reads/writes no files,
and validates every returned move against python-chess legal_moves.
"""

from __future__ import annotations

import math
import time
from typing import Any

import chess


MATE_SCORE = 100000
INF = 10**9

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Piece-square tables from White's perspective. Black uses mirrored squares.
PST = {
    chess.PAWN: [
        0, 0, 0, 0, 0, 0, 0, 0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5, 5, 10, 25, 25, 10, 5, 5,
        0, 0, 0, 20, 20, 0, 0, 0,
        5, -5, -10, 0, 0, -10, -5, 5,
        5, 10, 10, -20, -20, 10, 10, 5,
        0, 0, 0, 0, 0, 0, 0, 0,
    ],
    chess.KNIGHT: [
        -50, -40, -30, -30, -30, -30, -40, -50,
        -40, -20, 0, 5, 5, 0, -20, -40,
        -30, 5, 10, 15, 15, 10, 5, -30,
        -30, 0, 15, 20, 20, 15, 0, -30,
        -30, 5, 15, 20, 20, 15, 5, -30,
        -30, 0, 10, 15, 15, 10, 0, -30,
        -40, -20, 0, 0, 0, 0, -20, -40,
        -50, -40, -30, -30, -30, -30, -40, -50,
    ],
    chess.BISHOP: [
        -20, -10, -10, -10, -10, -10, -10, -20,
        -10, 5, 0, 0, 0, 0, 5, -10,
        -10, 10, 10, 10, 10, 10, 10, -10,
        -10, 0, 10, 10, 10, 10, 0, -10,
        -10, 5, 5, 10, 10, 5, 5, -10,
        -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -20, -10, -10, -10, -10, -10, -10, -20,
    ],
    chess.ROOK: [
        0, 0, 0, 5, 5, 0, 0, 0,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        5, 10, 10, 10, 10, 10, 10, 5,
        0, 0, 0, 0, 0, 0, 0, 0,
    ],
    chess.QUEEN: [
        -20, -10, -10, -5, -5, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 5, 5, 5, 0, -10,
        -5, 0, 5, 5, 5, 5, 0, -5,
        0, 0, 5, 5, 5, 5, 0, -5,
        -10, 5, 5, 5, 5, 5, 0, -10,
        -10, 0, 5, 0, 0, 0, 0, -10,
        -20, -10, -10, -5, -5, -10, -10, -20,
    ],
    chess.KING: [
        20, 30, 10, 0, 0, 10, 30, 20,
        20, 20, 0, 0, 0, 0, 20, 20,
        -10, -20, -20, -20, -20, -20, -20, -10,
        -20, -30, -30, -40, -40, -30, -30, -20,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
    ],
}

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(observation: Any, output_format: str = "uci", time_limit_ms: int = 100) -> str:
    """Choose a legal chess move for the supplied observation."""
    try:
        board = _parse_observation(observation)
        if board.is_game_over(claim_draw=False):
            return ""
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return ""

        chosen = _choose_move(board, legal_moves, time_limit_ms)
        if chosen not in board.legal_moves:
            chosen = legal_moves[0]
        return _format_move(board, chosen, output_format)
    except Exception:
        # Last-resort legal fallback. This preserves the no-illegal-move contract
        # even if the input payload is malformed in an unexpected way.
        try:
            board = _parse_observation(observation)
            legal_moves = list(board.legal_moves)
            if not legal_moves:
                return ""
            return _format_move(board, legal_moves[0], output_format)
        except Exception:
            return ""


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    fen = None
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
    elif isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text
    else:
        value = getattr(observation, "fen", None)
        if isinstance(value, str) and value.strip():
            fen = value.strip()
        elif callable(value):
            maybe = value()
            if isinstance(maybe, str) and maybe.strip():
                fen = maybe.strip()

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _format_move(board: chess.Board, move_obj: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").strip().lower()
    if fmt in {"san", "algebraic"}:
        return board.san(move_obj)
    return move_obj.uci()


def _choose_move(board: chess.Board, legal_moves: list[chess.Move], time_limit_ms: int) -> chess.Move:
    # Deterministic opening preference for common starting positions. Each move is
    # still checked for legality before use.
    book_move = _book_move(board)
    if book_move is not None and book_move in legal_moves:
        return book_move

    # Immediate tactical win: if any legal move checkmates, play it.
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        mates = board.is_checkmate()
        board.pop()
        if mates:
            return mv

    seconds = max(0.008, min(0.22, float(time_limit_ms) / 1000.0 * 0.72))
    deadline = time.perf_counter() + seconds
    if time_limit_ms <= 35:
        max_depth = 2
    elif time_limit_ms <= 120:
        max_depth = 3
    else:
        max_depth = 4

    ordered = _ordered_moves(board, legal_moves)
    best_move = ordered[0]
    best_score = -INF

    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        completed = True
        for mv in ordered:
            if time.perf_counter() >= deadline:
                completed = False
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -INF, -alpha, deadline, 0)
            board.pop()
            if score > current_score:
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score
        if completed:
            best_move = current_best
            best_score = current_score
            ordered = [best_move] + [mv for mv in ordered if mv != best_move]
            if best_score >= MATE_SCORE - 1000:
                break

    return best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, deadline: float, ply: int) -> int:
    if time.perf_counter() >= deadline:
        return _evaluate_for_side_to_move(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    best = -INF
    moves = _ordered_moves(board, list(board.legal_moves))
    for mv in moves:
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
        if time.perf_counter() >= deadline:
            break
    return best


def _quiescence(board: chess.Board, alpha: int, beta: int, deadline: float, ply: int) -> int:
    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if ply > 10 or time.perf_counter() >= deadline:
        return alpha

    noisy = [mv for mv in board.legal_moves if board.is_capture(mv) or mv.promotion]
    for mv in _ordered_moves(board, noisy):
        board.push(mv)
        if board.is_checkmate():
            score = MATE_SCORE - ply
        else:
            score = -_quiescence(board, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
        if time.perf_counter() >= deadline:
            break
    return alpha


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_score(board, mv), reverse=True)


def _move_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_at(mv.from_square)
    captured_piece = board.piece_at(mv.to_square)
    if captured_piece is None and board.is_en_passant(mv):
        captured_piece = chess.Piece(chess.PAWN, not board.turn)
    if captured_piece is not None:
        attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0
        victim_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
        score += 10000 + 10 * victim_value - attacker_value
    if mv.promotion:
        score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.gives_check(mv):
        score += 900
    if mv.to_square in CENTER_SQUARES:
        score += 70
    elif mv.to_square in EXTENDED_CENTER:
        score += 30
    if moving_piece is not None and moving_piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        home_rank = 0 if moving_piece.color == chess.WHITE else 7
        if chess.square_rank(mv.from_square) == home_rank:
            score += 45
    if board.is_castling(mv):
        score += 120
    return score


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    score = _evaluate_white_minus_black(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_minus_black(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    white_bishops = 0
    black_bishops = 0

    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        value = PIECE_VALUES[piece.piece_type]
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        score += sign * (value + PST[piece.piece_type][pst_square])
        if piece.piece_type == chess.BISHOP:
            if piece.color == chess.WHITE:
                white_bishops += 1
            else:
                black_bishops += 1
        if piece.piece_type == chess.PAWN:
            score += sign * _pawn_bonus(board, square, piece.color)

    if white_bishops >= 2:
        score += 25
    if black_bishops >= 2:
        score -= 25

    score += _king_safety_bonus(board, chess.WHITE)
    score -= _king_safety_bonus(board, chess.BLACK)

    # Mobility is useful, but computing both sides exactly should remain cheap.
    turn = board.turn
    board.turn = chess.WHITE
    white_mobility = board.legal_moves.count() if board.king(chess.WHITE) is not None else 0
    board.turn = chess.BLACK
    black_mobility = board.legal_moves.count() if board.king(chess.BLACK) is not None else 0
    board.turn = turn
    score += 2 * (white_mobility - black_mobility)

    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 8
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 8
    return int(score)


def _pawn_bonus(board: chess.Board, square: chess.Square, color: chess.Color) -> int:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    direction = 1 if color == chess.WHITE else -1
    advancement = rank_index if color == chess.WHITE else 7 - rank_index
    bonus = advancement * 3

    # Passed pawn approximation.
    enemy = not color
    passed = True
    for file_delta in (-1, 0, 1):
        f = file_index + file_delta
        if f < 0 or f > 7:
            continue
        for r in range(rank_index + direction, 8 if color == chess.WHITE else -1, direction):
            p = board.piece_at(chess.square(f, r))
            if p is not None and p.color == enemy and p.piece_type == chess.PAWN:
                passed = False
                break
        if not passed:
            break
    if passed:
        bonus += 18 + advancement * 5
    return bonus


def _king_safety_bonus(board: chess.Board, color: chess.Color) -> int:
    king_sq = board.king(color)
    if king_sq is None:
        return 0
    bonus = 0
    rank = chess.square_rank(king_sq)
    file_index = chess.square_file(king_sq)
    home_rank = 0 if color == chess.WHITE else 7
    if rank == home_rank and file_index in {0, 1, 2, 5, 6, 7}:
        bonus += 25
    pawn_rank = rank + (1 if color == chess.WHITE else -1)
    if 0 <= pawn_rank <= 7:
        for df in (-1, 0, 1):
            f = file_index + df
            if 0 <= f <= 7:
                piece = board.piece_at(chess.square(f, pawn_rank))
                if piece is not None and piece.color == color and piece.piece_type == chess.PAWN:
                    bonus += 8
    return bonus


def _book_move(board: chess.Board) -> chess.Move | None:
    # Tiny deterministic book. It improves opening consistency without any file IO.
    fen_key = " ".join(board.fen().split()[:4])
    book = {
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -": "e2e4",
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -": "e7e5",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "g1f3",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -": "b8c6",
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": "f1b5",
        "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq -": "d7d5",
        "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq -": "c2c4",
    }
    uci = book.get(fen_key)
    if not uci:
        return None
    try:
        mv = chess.Move.from_uci(uci)
    except ValueError:
        return None
    return mv if mv in board.legal_moves else None
