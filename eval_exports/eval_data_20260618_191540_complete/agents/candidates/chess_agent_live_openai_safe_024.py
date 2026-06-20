"""Safe standalone CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation is intentionally self-contained, uses only python-chess,
performs no network or file access, and validates every returned move against
board.legal_moves.
"""

from __future__ import annotations

import time
from typing import Any

import chess


MATE_SCORE = 100000
INF = 10**9

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

PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, -20, -20, 10, 10, 5,
    5, -5, -10, 0, 0, -10, -5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, 5, 10, 25, 25, 10, 5, 5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_PST = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_PST = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_PST = [
    0, 0, 0, 5, 5, 0, 0, 0,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
QUEEN_PST = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -10, 5, 5, 5, 5, 5, 0, -10,
    0, 0, 5, 5, 5, 5, 0, -5,
    -5, 0, 5, 5, 5, 5, 0, -5,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_PST = [
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
    chess.KING: KING_PST,
}


class SearchTimeout(Exception):
    """Raised internally when the soft search deadline is reached."""


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
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    selected = _choose_move(board, time_limit_ms)
    if selected not in legal_moves:
        selected = _safe_fallback_move(board, legal_moves)

    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(selected)
        except Exception:
            return selected.uci()
    return selected.uci()


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    fen = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        if fen is None:
            nested = observation.get("observation")
            if isinstance(nested, dict):
                value = nested.get("fen")
                if isinstance(value, str) and value.strip():
                    fen = value.strip()
    elif isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text

    if fen:
        try:
            return chess.Board(fen)
        except Exception:
            pass
    return chess.Board()


def _choose_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    legal_moves = list(board.legal_moves)

    mate_move = _find_immediate_mate(board, legal_moves)
    if mate_move is not None:
        return mate_move

    safe_ms = max(1, int(time_limit_ms))
    budget_ms = max(3, min(safe_ms - 2, int(safe_ms * 0.82))) if safe_ms > 5 else 1
    deadline = time.perf_counter() + budget_ms / 1000.0

    if safe_ms < 25:
        return _safe_fallback_move(board, legal_moves)

    if len(legal_moves) <= 8 and safe_ms >= 120:
        max_depth = 4
    elif safe_ms >= 70:
        max_depth = 3
    else:
        max_depth = 2

    best_move = _safe_fallback_move(board, legal_moves)
    ordered_root = _ordered_moves(board, legal_moves)
    nodes = [0]

    try:
        for depth in range(1, max_depth + 1):
            current_best = best_move
            current_score = -INF
            alpha = -INF
            beta = INF
            for mv in ordered_root:
                _check_time(deadline, nodes)
                board.push(mv)
                score = -_negamax(board, depth - 1, -beta, -alpha, deadline, nodes, 1)
                board.pop()
                if score > current_score:
                    current_score = score
                    current_best = mv
                if score > alpha:
                    alpha = score
            best_move = current_best
            if current_score >= MATE_SCORE - 50:
                break
    except SearchTimeout:
        pass
    except Exception:
        return _safe_fallback_move(board, legal_moves)

    return best_move if best_move in legal_moves else _safe_fallback_move(board, legal_moves)


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    nodes: list[int],
    ply: int,
) -> int:
    _check_time(deadline, nodes)
    nodes[0] += 1

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, nodes, ply, 2)

    best = -INF
    legal = list(board.legal_moves)
    for mv in _ordered_moves(board, legal):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, nodes, ply + 1)
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
    nodes: list[int],
    ply: int,
    qdepth: int,
) -> int:
    _check_time(deadline, nodes)
    nodes[0] += 1

    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if qdepth <= 0:
        return alpha

    tactical = [mv for mv in board.legal_moves if board.is_capture(mv) or mv.promotion]
    for mv in _ordered_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, nodes, ply + 1, qdepth - 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _find_immediate_mate(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move | None:
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_at(mv.from_square)
    target_piece = board.piece_at(mv.to_square)

    if mv.promotion:
        score += 9000 + PIECE_VALUES.get(mv.promotion, 0)
    if target_piece is not None:
        attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0
        victim_value = PIECE_VALUES.get(target_piece.piece_type, 0)
        score += 10000 + 10 * victim_value - attacker_value
    elif board.is_en_passant(mv):
        score += 10000 + 1000

    try:
        if board.gives_check(mv):
            score += 700
    except Exception:
        pass

    if board.is_castling(mv):
        score += 350
    if mv.to_square in CENTER_SQUARES:
        score += 90
    elif mv.to_square in EXTENDED_CENTER:
        score += 35

    if moving_piece is not None:
        if moving_piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            home_rank = 0 if moving_piece.color == chess.WHITE else 7
            if chess.square_rank(mv.from_square) == home_rank:
                score += 120
        if moving_piece.piece_type == chess.PAWN and mv.to_square in CENTER_SQUARES:
            score += 60
    return score


def _evaluate_side_to_move(board: chess.Board) -> int:
    score = _evaluate_white_perspective(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_perspective(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        pst = PSTS[piece.piece_type]
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        piece_score = value + pst[pst_square]
        score += piece_score if piece.color == chess.WHITE else -piece_score

    score += _bishop_pair_bonus(board, chess.WHITE)
    score -= _bishop_pair_bonus(board, chess.BLACK)
    score += _king_safety(board, chess.WHITE)
    score -= _king_safety(board, chess.BLACK)
    score += _pawn_structure(board, chess.WHITE)
    score -= _pawn_structure(board, chess.BLACK)

    turn = board.turn
    board.turn = chess.WHITE
    try:
        white_mobility = board.legal_moves.count()
    except Exception:
        white_mobility = 0
    board.turn = chess.BLACK
    try:
        black_mobility = board.legal_moves.count()
    except Exception:
        black_mobility = 0
    board.turn = turn
    score += 2 * (white_mobility - black_mobility)

    return score


def _bishop_pair_bonus(board: chess.Board, color: chess.Color) -> int:
    return 35 if len(board.pieces(chess.BISHOP, color)) >= 2 else 0


def _king_safety(board: chess.Board, color: chess.Color) -> int:
    king_sq = board.king(color)
    if king_sq is None:
        return -500
    enemy = not color
    penalty = 0
    for sq in chess.SquareSet(chess.BB_KING_ATTACKS[king_sq]):
        if board.is_attacked_by(enemy, sq):
            penalty += 8
    if board.is_attacked_by(enemy, king_sq):
        penalty += 50

    bonus = 0
    rank_dir = 1 if color == chess.WHITE else -1
    k_file = chess.square_file(king_sq)
    k_rank = chess.square_rank(king_sq)
    shield_rank = k_rank + rank_dir
    if 0 <= shield_rank <= 7:
        for file_delta in (-1, 0, 1):
            file_idx = k_file + file_delta
            if 0 <= file_idx <= 7:
                sq = chess.square(file_idx, shield_rank)
                piece = board.piece_at(sq)
                if piece is not None and piece.color == color and piece.piece_type == chess.PAWN:
                    bonus += 10
    return bonus - penalty


def _pawn_structure(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    if not pawns:
        return 0
    files = [chess.square_file(sq) for sq in pawns]
    score = 0
    for file_idx in range(8):
        count = files.count(file_idx)
        if count > 1:
            score -= 12 * (count - 1)
    occupied_files = set(files)
    for sq in pawns:
        file_idx = chess.square_file(sq)
        if file_idx - 1 not in occupied_files and file_idx + 1 not in occupied_files:
            score -= 10
        rank = chess.square_rank(sq)
        score += 3 * (rank if color == chess.WHITE else 7 - rank)
    return score


def _safe_fallback_move(board: chess.Board, legal_moves: list[chess.Move] | None = None) -> chess.Move:
    moves = legal_moves if legal_moves is not None else list(board.legal_moves)
    if not moves:
        return chess.Move.null()
    return max(moves, key=lambda mv: _move_order_score(board, mv))


def _check_time(deadline: float, nodes: list[int]) -> None:
    if (nodes[0] & 0x3F) == 0 and time.perf_counter() >= deadline:
        raise SearchTimeout
