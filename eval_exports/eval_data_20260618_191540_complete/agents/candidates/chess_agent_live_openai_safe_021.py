"""Safe self-contained CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

Design goals:
- no network, subprocess, file IO, eval/exec, or dynamic imports during play
- always validate selected moves against python-chess legal_moves
- deterministic bounded search suitable for short arena time limits
"""

from __future__ import annotations

import json
import math
import time
from typing import Any

import chess


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Small piece-square tables from White's perspective. Values are intentionally
# modest so material and tactics dominate.
PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    8, 8, 8, -8, -8, 8, 8, 8,
    4, 4, 8, 12, 12, 8, 4, 4,
    2, 2, 6, 16, 16, 6, 2, 2,
    0, 0, 4, 14, 14, 4, 0, 0,
    2, -2, -4, 6, 6, -4, -2, 2,
    2, 4, 4, -12, -12, 4, 4, 2,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_PST = [
    -30, -20, -15, -12, -12, -15, -20, -30,
    -20, -8, 0, 4, 4, 0, -8, -20,
    -15, 4, 10, 14, 14, 10, 4, -15,
    -12, 6, 14, 18, 18, 14, 6, -12,
    -12, 4, 14, 18, 18, 14, 4, -12,
    -15, 2, 8, 14, 14, 8, 2, -15,
    -20, -8, 0, 2, 2, 0, -8, -20,
    -30, -20, -15, -12, -12, -15, -20, -30,
]
BISHOP_PST = [
    -16, -8, -8, -8, -8, -8, -8, -16,
    -8, 4, 2, 2, 2, 2, 4, -8,
    -8, 6, 8, 8, 8, 8, 6, -8,
    -8, 2, 8, 10, 10, 8, 2, -8,
    -8, 4, 8, 10, 10, 8, 4, -8,
    -8, 2, 8, 8, 8, 8, 2, -8,
    -8, 6, 2, 2, 2, 2, 6, -8,
    -16, -8, -8, -8, -8, -8, -8, -16,
]
ROOK_PST = [
    0, 0, 2, 6, 6, 2, 0, 0,
    -2, 0, 0, 0, 0, 0, 0, -2,
    -2, 0, 0, 0, 0, 0, 0, -2,
    -2, 0, 0, 0, 0, 0, 0, -2,
    -2, 0, 0, 0, 0, 0, 0, -2,
    -2, 0, 0, 0, 0, 0, 0, -2,
    4, 6, 6, 6, 6, 6, 6, 4,
    0, 0, 2, 6, 6, 2, 0, 0,
]
QUEEN_PST = [
    -10, -6, -4, -2, -2, -4, -6, -10,
    -6, 0, 2, 0, 0, 0, 0, -6,
    -4, 2, 4, 4, 4, 4, 0, -4,
    -2, 0, 4, 4, 4, 4, 0, -2,
    0, 0, 4, 4, 4, 4, 0, -2,
    -4, 4, 4, 4, 4, 4, 0, -4,
    -6, 2, 4, 0, 0, 0, 0, -6,
    -10, -6, -4, -2, -2, -4, -6, -10,
]
KING_MID_PST = [
    20, 30, 10, 0, 0, 10, 30, 20,
    20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
]
PSTS = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
    chess.KING: KING_MID_PST,
}

MATE_SCORE = 100000
INF = 10**9


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
    """Choose a legal move for the supplied observation."""
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    selected = _choose_move(board, max(1, int(time_limit_ms or 100)))
    if selected not in legal_moves:
        selected = _fallback_move(board, legal_moves)
    if selected not in legal_moves:
        selected = legal_moves[0]
    return _format_move(board, selected, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    fen = _extract_fen(observation)
    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _extract_fen(observation: Any) -> str:
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and _looks_like_fen(value):
                return value.strip()
        nested = observation.get("observation")
        if nested is not observation:
            return _extract_fen(nested)
    if isinstance(observation, str):
        text = observation.strip()
        if _looks_like_fen(text):
            return text
        try:
            loaded = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return ""
        return _extract_fen(loaded)
    for attr in ("fen", "board"):
        value = getattr(observation, attr, None)
        if callable(value):
            try:
                value = value()
            except (TypeError, ValueError, AttributeError):
                value = None
        if isinstance(value, str) and _looks_like_fen(value):
            return value.strip()
    return ""


def _looks_like_fen(text: str) -> bool:
    parts = text.strip().split()
    return len(parts) >= 4 and "/" in parts[0] and parts[1] in {"w", "b"}


def _format_move(board: chess.Board, selected: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").strip().lower()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(selected)
        except (ValueError, AssertionError):
            return selected.uci()
    return selected.uci()


def _choose_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    immediate = _mate_in_one(board)
    if immediate is not None:
        return immediate

    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    deadline = time.perf_counter() + max(0.005, min(time_limit_ms, 250) / 1000.0 * 0.72)
    depth = _depth_for_position(board, time_limit_ms)

    best_move = _fallback_move(board, legal_moves)
    best_score = -INF
    alpha = -INF
    beta = INF

    ordered = _ordered_moves(board, legal_moves)
    try:
        for current_depth in range(1, depth + 1):
            if time.perf_counter() >= deadline:
                break
            iteration_best = best_move
            iteration_score = -INF
            local_alpha = alpha
            for mv in ordered:
                if time.perf_counter() >= deadline:
                    raise TimeoutError
                board.push(mv)
                score = -_negamax(board, current_depth - 1, -beta, -local_alpha, deadline, 0)
                board.pop()
                score += _root_tiebreak(board, mv)
                if score > iteration_score:
                    iteration_score = score
                    iteration_best = mv
                if score > local_alpha:
                    local_alpha = score
            best_move = iteration_best
            best_score = iteration_score
            alpha = max(-INF, best_score - 35)
            beta = min(INF, best_score + 35)
            ordered = [best_move] + [mv for mv in ordered if mv != best_move]
    except TimeoutError:
        pass

    return best_move


def _depth_for_position(board: chess.Board, time_limit_ms: int) -> int:
    legal_count = board.legal_moves.count()
    non_king_material = _non_king_material(board)
    if time_limit_ms < 35:
        return 2
    if time_limit_ms < 80:
        return 3
    if legal_count <= 12 or non_king_material <= 2600:
        return 4
    return 3


def _non_king_material(board: chess.Board) -> int:
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        if piece_type != chess.KING:
            total += value * len(board.pieces(piece_type, chess.WHITE))
            total += value * len(board.pieces(piece_type, chess.BLACK))
    return total


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError
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
    return best


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError
    if board.is_checkmate():
        return -MATE_SCORE + ply
    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            tactical.append(mv)
    for mv in _ordered_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        pst = PSTS.get(piece.piece_type)
        if pst is not None:
            idx = square if piece.color == chess.WHITE else chess.square_mirror(square)
            value += pst[idx]
        score += value if piece.color == chess.WHITE else -value

    # Mobility and king-pressure terms are deliberately light and cheap.
    turn = board.turn
    white_mobility = board.legal_moves.count() if turn == chess.WHITE else 0
    board.turn = not turn
    try:
        black_mobility = board.legal_moves.count() if board.turn == chess.BLACK else 0
    finally:
        board.turn = turn
    score += 2 * (white_mobility - black_mobility)

    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 10
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 10
    if board.is_check():
        score -= 25

    return score if board.turn == chess.WHITE else -score


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(mv.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 10000 + 10 * victim_value - attacker_value
    if mv.promotion:
        score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.gives_check(mv):
        score += 2500
    if board.is_castling(mv):
        score += 700
    to_file = chess.square_file(mv.to_square)
    to_rank = chess.square_rank(mv.to_square)
    if 2 <= to_file <= 5 and 2 <= to_rank <= 5:
        score += 90
    piece = board.piece_at(mv.from_square)
    if piece and piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        home_rank = 0 if piece.color == chess.WHITE else 7
        if chess.square_rank(mv.from_square) == home_rank:
            score += 120
    if piece and piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
        score -= 80
    return score


def _root_tiebreak(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    mover = board.piece_at(mv.from_square)
    if mover is None:
        return score
    # Penalize moves to squares immediately capturable by low-value enemy pieces.
    board.push(mv)
    try:
        attackers = board.attackers(not mover.color, mv.to_square)
        if attackers:
            lowest_attacker = min(
                PIECE_VALUES.get(board.piece_at(sq).piece_type, 0)
                for sq in attackers
                if board.piece_at(sq) is not None
            )
            moved_value = PIECE_VALUES.get(mover.piece_type, 0)
            if moved_value > lowest_attacker:
                score -= min(120, (moved_value - lowest_attacker) // 4)
    finally:
        board.pop()
    return score


def _mate_in_one(board: chess.Board) -> chess.Move | None:
    for mv in _ordered_moves(board, list(board.legal_moves)):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    # Deterministic tactical fallback. This is also used as the initial move for
    # iterative deepening, so prefer forcing and development moves.
    mate = _mate_in_one(board)
    if mate is not None:
        return mate
    best = legal_moves[0]
    best_score = -INF
    for mv in legal_moves:
        score = _move_order_score(board, mv)
        board.push(mv)
        if board.is_checkmate():
            score += MATE_SCORE
        elif board.is_stalemate():
            score -= 50
        else:
            score += _evaluate_for_side_to_move(board) // -20
        board.pop()
        if score > best_score:
            best_score = score
            best = mv
    return best
