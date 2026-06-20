"""Safe standalone CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This file intentionally avoids network access, subprocesses, file I/O, eval/exec,
dynamic imports, and third-party dependencies beyond python-chess.
"""

from __future__ import annotations

from dataclasses import dataclass
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
PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    45, 50, 35, 15, 15, 35, 50, 45,
    14, 16, 20, 28, 28, 20, 16, 14,
    8, 10, 14, 24, 24, 14, 10, 8,
    3, 5, 8, 18, 18, 8, 5, 3,
    2, 2, 4, 8, 8, 4, 2, 2,
    0, 0, 0, -10, -10, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_PST = [
    -55, -35, -25, -18, -18, -25, -35, -55,
    -35, -18, 0, 8, 8, 0, -18, -35,
    -25, 4, 16, 22, 22, 16, 4, -25,
    -18, 8, 22, 30, 30, 22, 8, -18,
    -18, 8, 22, 30, 30, 22, 8, -18,
    -25, 4, 16, 22, 22, 16, 4, -25,
    -35, -18, 0, 8, 8, 0, -18, -35,
    -55, -35, -25, -18, -18, -25, -35, -55,
]
BISHOP_PST = [
    -22, -12, -10, -8, -8, -10, -12, -22,
    -12, 4, 2, 6, 6, 2, 4, -12,
    -10, 6, 10, 14, 14, 10, 6, -10,
    -8, 8, 14, 18, 18, 14, 8, -8,
    -8, 8, 14, 18, 18, 14, 8, -8,
    -10, 6, 10, 14, 14, 10, 6, -10,
    -12, 4, 2, 6, 6, 2, 4, -12,
    -22, -12, -10, -8, -8, -10, -12, -22,
]
ROOK_PST = [
    0, 0, 4, 8, 8, 4, 0, 0,
    -2, 0, 4, 8, 8, 4, 0, -2,
    -4, 0, 4, 8, 8, 4, 0, -4,
    -4, 0, 4, 8, 8, 4, 0, -4,
    -4, 0, 4, 8, 8, 4, 0, -4,
    -4, 0, 4, 8, 8, 4, 0, -4,
    8, 10, 12, 14, 14, 12, 10, 8,
    0, 0, 4, 8, 8, 4, 0, 0,
]
QUEEN_PST = [
    -20, -10, -8, -4, -4, -8, -10, -20,
    -10, 0, 4, 6, 6, 4, 0, -10,
    -8, 4, 8, 10, 10, 8, 4, -8,
    -4, 6, 10, 12, 12, 10, 6, -4,
    -4, 6, 10, 12, 12, 10, 6, -4,
    -8, 4, 8, 10, 10, 8, 4, -8,
    -10, 0, 4, 6, 6, 4, 0, -10,
    -20, -10, -8, -4, -4, -8, -10, -20,
]
KING_MID_PST = [
    24, 30, 10, 0, 0, 10, 30, 24,
    18, 18, 0, 0, 0, 0, 18, 18,
    -12, -18, -22, -28, -28, -22, -18, -12,
    -28, -35, -40, -48, -48, -40, -35, -28,
    -38, -45, -52, -60, -60, -52, -45, -38,
    -45, -55, -62, -70, -70, -62, -55, -45,
    -55, -65, -72, -80, -80, -72, -65, -55,
    -65, -75, -82, -90, -90, -82, -75, -65,
]
KING_END_PST = [
    -45, -30, -20, -12, -12, -20, -30, -45,
    -30, -10, 0, 8, 8, 0, -10, -30,
    -20, 0, 12, 20, 20, 12, 0, -20,
    -12, 8, 20, 30, 30, 20, 8, -12,
    -12, 8, 20, 30, 30, 20, 8, -12,
    -20, 0, 12, 20, 20, 12, 0, -20,
    -30, -10, 0, 8, 8, 0, -10, -30,
    -45, -30, -20, -12, -12, -20, -30, -45,
]
PSTS = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
}

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


@dataclass
class SearchLimits:
    deadline: float
    root_depth: int
    q_depth: int


class _Timeout(Exception):
    pass


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(observation: Any, output_format: str = "uci", time_limit_ms: int = 100) -> str:
    """Choose a legal chess move for the supplied observation."""
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    safe_ms = max(5, int(time_limit_ms or 100))
    # Leave a conservative buffer for arena overhead and Python variance.
    budget = max(0.004, (safe_ms - 8) / 1000.0)
    deadline = time.perf_counter() + budget
    root_depth = 2
    if safe_ms >= 70 and len(legal_moves) <= 48:
        root_depth = 3
    if safe_ms >= 140 and len(legal_moves) <= 32:
        root_depth = 4
    if board.fullmove_number <= 8 and safe_ms < 120:
        root_depth = min(root_depth, 3)
    limits = SearchLimits(deadline=deadline, root_depth=root_depth, q_depth=4)

    chosen = _book_move(board)
    if chosen is None:
        chosen = _search_best_move(board, legal_moves, limits)
    if chosen not in legal_moves:
        chosen = _fallback_move(board, legal_moves)
    return _format_move(board, chosen, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    fen = None
    if isinstance(observation, str):
        text = observation.strip()
        fen = text or None
    elif isinstance(observation, dict):
        for key in ("fen", "board", "state", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        if fen is None:
            nested = observation.get("observation")
            if isinstance(nested, dict):
                for key in ("fen", "board", "state", "position"):
                    value = nested.get(key)
                    if isinstance(value, str) and value.strip():
                        fen = value.strip()
                        break
    else:
        value = getattr(observation, "fen", None)
        if callable(value):
            try:
                fen = value()
            except (TypeError, ValueError, AttributeError):
                fen = None
        elif isinstance(value, str):
            fen = value

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _format_move(board: chess.Board, selected: chess.Move, output_format: str) -> str:
    if selected not in board.legal_moves:
        legal = list(board.legal_moves)
        if not legal:
            return ""
        selected = legal[0]
    fmt = (output_format or "uci").lower().strip()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(selected)
        except (ValueError, AssertionError):
            return selected.uci()
    return selected.uci()


def _book_move(board: chess.Board) -> chess.Move | None:
    """Tiny deterministic opening guardrail; every candidate is legality checked."""
    if board.fullmove_number > 6:
        return None
    fen_key = " ".join(board.fen().split()[:4])
    book = {
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -": ["e2e4", "d2d4", "g1f3"],
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -": ["c7c5", "e7e5", "e7e6"],
        "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq -": ["g8f6", "d7d5", "e7e6"],
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": ["g1f3", "b1c3", "f1c4"],
        "rnbqkbnr/pppppppp/8/8/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -": ["b8c6", "g8f6", "d7d6"],
    }
    legal = set(board.legal_moves)
    for uci in book.get(fen_key, []):
        move = chess.Move.from_uci(uci)
        if move in legal:
            return move
    return None


def _search_best_move(board: chess.Board, legal_moves: list[chess.Move], limits: SearchLimits) -> chess.Move:
    best = _fallback_move(board, legal_moves)
    ordered = _ordered_moves(board, legal_moves)
    best_score = -INF

    try:
        # Iterative deepening gives a legal, tactically checked answer even if time expires.
        for depth in range(1, limits.root_depth + 1):
            if time.perf_counter() >= limits.deadline:
                break
            current_best = best
            current_score = -INF
            alpha = -INF
            beta = INF
            for mv in ordered:
                _check_time(limits)
                board.push(mv)
                score = -_negamax(board, depth - 1, -beta, -alpha, limits, ply=1)
                board.pop()
                if score > current_score or (score == current_score and _move_tiebreak(board, mv) > _move_tiebreak(board, current_best)):
                    current_score = score
                    current_best = mv
                alpha = max(alpha, current_score)
            best = current_best
            best_score = current_score
            ordered = [best] + [mv for mv in ordered if mv != best]
            if best_score >= MATE_SCORE - 32:
                break
    except _Timeout:
        pass
    return best if best in legal_moves else _fallback_move(board, legal_moves)


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, limits: SearchLimits, ply: int) -> int:
    _check_time(limits)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, limits, limits.q_depth, ply)

    best = -INF
    moves = _ordered_moves(board, list(board.legal_moves))
    if not moves:
        return _static_score_for_side_to_move(board)
    for mv in moves:
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, limits, ply + 1)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(board: chess.Board, alpha: int, beta: int, limits: SearchLimits, depth: int, ply: int) -> int:
    _check_time(limits)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    stand_pat = _static_score_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if depth <= 0:
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion is not None:
            tactical.append(mv)
        elif board.is_check() and len(tactical) < 12:
            tactical.append(mv)
    for mv in _ordered_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, limits, depth - 1, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if mv.promotion is not None:
        score += 9000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.is_capture(mv):
        victim_type = board.piece_type_at(mv.to_square)
        if victim_type is None and board.is_en_passant(mv):
            victim_type = chess.PAWN
        attacker_type = board.piece_type_at(mv.from_square)
        score += 6000 + 10 * PIECE_VALUES.get(victim_type, 0) - PIECE_VALUES.get(attacker_type, 0)
    try:
        if board.gives_check(mv):
            score += 2500
    except AssertionError:
        pass
    if board.is_castling(mv):
        score += 700
    piece = board.piece_at(mv.from_square)
    if piece is not None:
        if mv.to_square in CENTER:
            score += 180
        elif mv.to_square in EXTENDED_CENTER:
            score += 70
        if board.fullmove_number <= 10:
            if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                home = {chess.B1, chess.G1, chess.C1, chess.F1} if piece.color == chess.WHITE else {chess.B8, chess.G8, chess.C8, chess.F8}
                if mv.from_square in home:
                    score += 260
            if piece.piece_type == chess.QUEEN:
                score -= 180
            if piece.piece_type == chess.ROOK:
                score -= 100
    return score


def _move_tiebreak(board: chess.Board, mv: chess.Move) -> int:
    return _move_order_score(board, mv) + (63 - mv.from_square) + mv.to_square


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    # Deterministic legal fallback with basic tactical preference.
    return max(legal_moves, key=lambda mv: _move_order_score(board, mv))


def _check_time(limits: SearchLimits) -> None:
    if time.perf_counter() >= limits.deadline:
        raise _Timeout


def _static_score_for_side_to_move(board: chess.Board) -> int:
    score_white = _evaluate_white_minus_black(board)
    return score_white if board.turn == chess.WHITE else -score_white


def _evaluate_white_minus_black(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    non_king_material = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        if piece.piece_type != chess.KING:
            non_king_material += value
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        if piece.piece_type == chess.KING:
            table = KING_END_PST if non_king_material <= 2600 else KING_MID_PST
            positional = table[pst_square]
        else:
            positional = PSTS[piece.piece_type][pst_square]
        term = value + positional
        score += term if piece.color == chess.WHITE else -term

    score += _bishop_pair_bonus(board, chess.WHITE) - _bishop_pair_bonus(board, chess.BLACK)
    score += _pawn_structure_score(board, chess.WHITE) - _pawn_structure_score(board, chess.BLACK)
    score += _king_safety_score(board, chess.WHITE) - _king_safety_score(board, chess.BLACK)
    score += _development_score(board, chess.WHITE) - _development_score(board, chess.BLACK)

    # Mobility is mildly weighted and computed by temporarily toggling turn on copies.
    score += 2 * (_mobility(board, chess.WHITE) - _mobility(board, chess.BLACK))
    if board.turn == chess.WHITE and board.is_check():
        score -= 25
    elif board.turn == chess.BLACK and board.is_check():
        score += 25
    return int(max(-MATE_SCORE + 1000, min(MATE_SCORE - 1000, score)))


def _bishop_pair_bonus(board: chess.Board, color: chess.Color) -> int:
    return 35 if len(board.pieces(chess.BISHOP, color)) >= 2 else 0


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    if not pawns:
        return 0
    files = [chess.square_file(sq) for sq in pawns]
    score = 0
    for file_idx in range(8):
        count = files.count(file_idx)
        if count > 1:
            score -= 14 * (count - 1)
    occupied_files = set(files)
    for sq in pawns:
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        if file_idx - 1 not in occupied_files and file_idx + 1 not in occupied_files:
            score -= 10
        score += 3 * (rank_idx if color == chess.WHITE else 7 - rank_idx)
    return score


def _king_safety_score(board: chess.Board, color: chess.Color) -> int:
    king = board.king(color)
    if king is None:
        return -500
    score = 0
    enemy = not color
    ring = chess.SquareSet(chess.BB_KING_ATTACKS[king])
    attacked = 0
    for sq in ring:
        if board.is_attacked_by(enemy, sq):
            attacked += 1
    score -= 9 * attacked

    rank_dir = 1 if color == chess.WHITE else -1
    king_file = chess.square_file(king)
    king_rank = chess.square_rank(king)
    for df in (-1, 0, 1):
        file_idx = king_file + df
        rank_idx = king_rank + rank_dir
        if 0 <= file_idx <= 7 and 0 <= rank_idx <= 7:
            piece = board.piece_at(chess.square(file_idx, rank_idx))
            if piece is not None and piece.color == color and piece.piece_type == chess.PAWN:
                score += 12
    if board.has_kingside_castling_rights(color) or board.has_queenside_castling_rights(color):
        score += 8
    return score


def _development_score(board: chess.Board, color: chess.Color) -> int:
    if board.fullmove_number > 16:
        return 0
    score = 0
    home_minor = [chess.B1, chess.G1, chess.C1, chess.F1] if color == chess.WHITE else [chess.B8, chess.G8, chess.C8, chess.F8]
    for sq in home_minor:
        piece = board.piece_at(sq)
        if piece is not None and piece.color == color and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            score -= 18
    queen_home = chess.D1 if color == chess.WHITE else chess.D8
    queen = board.piece_at(queen_home)
    if queen is None or queen.color != color or queen.piece_type != chess.QUEEN:
        score -= 6
    return score


def _mobility(board: chess.Board, color: chess.Color) -> int:
    temp = board.copy(stack=False)
    temp.turn = color
    if temp.king(color) is None:
        return 0
    try:
        return min(60, temp.legal_moves.count())
    except (ValueError, AssertionError):
        return 0
