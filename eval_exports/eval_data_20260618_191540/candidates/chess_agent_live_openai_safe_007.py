"""Standalone safe CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This implementation is intentionally self-contained apart from python-chess.  It
never calls network APIs, never reads/writes files, never launches subprocesses,
and validates every returned move against python-chess legal moves.
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
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Piece-square tables from White's perspective.  Black uses mirrored squares.
PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
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
    0, 0, 5, 10, 10, 5, 0, 0,
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
KING_END_PST = [
    -50, -30, -30, -30, -30, -30, -30, -50,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -20, -10, 0, 0, -10, -20, -30,
    -50, -40, -30, -20, -20, -30, -40, -50,
]
PST = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
}

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
NEAR_CENTER = {chess.C3, chess.D3, chess.E3, chess.F3, chess.C4, chess.F4, chess.C5, chess.F5, chess.C6, chess.D6, chess.E6, chess.F6}


class _SearchTimeout(Exception):
    """Raised internally when the fixed search budget is exhausted."""


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


class _Searcher:
    def __init__(self, board: chess.Board, time_limit_ms: int) -> None:
        self.board = board
        safe_ms = max(10, min(int(time_limit_ms), 250))
        self.deadline = time.perf_counter() + safe_ms * 0.00082
        self.nodes = 0
        self.node_limit = 4500 if safe_ms <= 50 else 9500 if safe_ms <= 120 else 16000
        self.root_turn = board.turn

    def check_time(self) -> None:
        self.nodes += 1
        if self.nodes >= self.node_limit or time.perf_counter() >= self.deadline:
            raise _SearchTimeout

    def choose(self) -> chess.Move:
        legal = list(self.board.legal_moves)
        if not legal:
            return chess.Move.null()
        if len(legal) == 1:
            return legal[0]

        mate = _find_mate_in_one(self.board, legal)
        if mate is not None:
            return mate

        book = _book_move(self.board, legal)
        if book is not None:
            return book

        best_move = self._safe_fallback(legal)
        best_score = -INF
        max_depth = self._max_depth(len(legal))

        for depth in range(1, max_depth + 1):
            try:
                current_best = best_move
                current_score = -INF
                alpha = -INF
                beta = INF
                for move in self._ordered_moves(legal):
                    self.board.push(move)
                    score = -self._negamax(depth - 1, -beta, -alpha, 1)
                    self.board.pop()
                    if score > current_score:
                        current_score = score
                        current_best = move
                    if score > alpha:
                        alpha = score
                best_move = current_best
                best_score = current_score
                if best_score > MATE_SCORE - 1000:
                    break
            except _SearchTimeout:
                break

        if best_move in legal:
            return best_move
        return self._safe_fallback(legal)

    def _max_depth(self, legal_count: int) -> int:
        remaining_ms = max(1.0, (self.deadline - time.perf_counter()) * 1000.0)
        pieces = len(self.board.piece_map())
        if remaining_ms < 35:
            depth = 2
        elif remaining_ms < 90:
            depth = 3
        else:
            depth = 4
        if legal_count <= 12 or pieces <= 12:
            depth += 1
        if legal_count >= 36 and pieces > 18:
            depth -= 1
        return max(1, min(depth, 5))

    def _negamax(self, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.check_time()
        if self.board.is_checkmate():
            return -MATE_SCORE + ply
        if self.board.is_stalemate() or self.board.is_insufficient_material():
            return 0
        if self.board.can_claim_fifty_moves() or self.board.can_claim_threefold_repetition():
            return 0
        if depth <= 0:
            return self._quiescence(alpha, beta, ply)

        best = -INF
        legal = list(self.board.legal_moves)
        for move in self._ordered_moves(legal):
            self.board.push(move)
            score = -self._negamax(depth - 1, -beta, -alpha, ply + 1)
            self.board.pop()
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        return best

    def _quiescence(self, alpha: int, beta: int, ply: int) -> int:
        self.check_time()
        stand_pat = _evaluate_for_side_to_move(self.board)
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        noisy = []
        for move in self.board.legal_moves:
            if self.board.is_capture(move) or move.promotion or self.board.gives_check(move):
                noisy.append(move)
        for move in self._ordered_moves(noisy):
            if not self.board.gives_check(move) and not self.board.is_capture(move) and not move.promotion:
                continue
            self.board.push(move)
            score = -self._quiescence(-beta, -alpha, ply + 1)
            self.board.pop()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    def _ordered_moves(self, moves: list[chess.Move]) -> list[chess.Move]:
        return sorted(moves, key=lambda m: self._move_score(m), reverse=True)

    def _move_score(self, move: chess.Move) -> int:
        score = 0
        if self.board.is_capture(move):
            victim = self.board.piece_at(move.to_square)
            if victim is None and self.board.is_en_passant(move):
                victim_value = PIECE_VALUES[chess.PAWN]
            else:
                victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
            attacker = self.board.piece_at(move.from_square)
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 1) if attacker else 1
            score += 10000 + 10 * victim_value - attacker_value
        if move.promotion:
            score += 8000 + PIECE_VALUES.get(move.promotion, 0)
        if self.board.gives_check(move):
            score += 1200
        piece = self.board.piece_at(move.from_square)
        if piece is not None:
            if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and move.to_square in NEAR_CENTER:
                score += 60
            if move.to_square in CENTER_SQUARES:
                score += 45
            if piece.piece_type == chess.KING and self.board.is_castling(move):
                score += 250
        return score

    def _safe_fallback(self, legal: list[chess.Move]) -> chess.Move:
        ordered = self._ordered_moves(legal)
        return ordered[0] if ordered else legal[0]


def select_move(observation: Any, output_format: str = "uci", time_limit_ms: int = 100) -> str:
    """Choose a legal chess move for the supplied observation."""
    board = _parse_observation(observation)
    legal = list(board.legal_moves)
    if not legal or board.is_game_over(claim_draw=False):
        return ""

    try:
        chosen = _Searcher(board.copy(stack=False), time_limit_ms).choose()
    except Exception:
        chosen = _fallback_move(board)

    if chosen not in legal:
        chosen = _fallback_move(board)
    if chosen not in legal:
        chosen = legal[0]
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
    if isinstance(observation, dict):
        for key in ("fen", "board", "state", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
    elif isinstance(observation, str):
        fen = observation.strip()

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _format_move(board: chess.Board, chosen: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").strip().lower()
    if fmt == "san":
        try:
            return board.san(chosen)
        except Exception:
            return chosen.uci()
    return chosen.uci()


def _fallback_move(board: chess.Board) -> chess.Move:
    legal = list(board.legal_moves)
    if not legal:
        return chess.Move.null()
    mate = _find_mate_in_one(board, legal)
    if mate is not None:
        return mate
    captures = [m for m in legal if board.is_capture(m)]
    if captures:
        return max(captures, key=lambda m: _capture_value(board, m))
    return sorted(legal, key=lambda m: (m.uci()))[0]


def _find_mate_in_one(board: chess.Board, legal: list[chess.Move]) -> chess.Move | None:
    for move in legal:
        board.push(move)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return move
    return None


def _book_move(board: chess.Board, legal: list[chess.Move]) -> chess.Move | None:
    # Tiny deterministic opening hints.  Only used when legal, and only for the
    # initial common positions; search handles everything else.
    candidates_by_ply = {
        0: ("e2e4", "d2d4", "g1f3", "c2c4"),
        1: ("e7e5", "c7c5", "e7e6", "d7d5"),
        2: ("g1f3", "b1c3", "d2d4", "f1c4"),
        3: ("b8c6", "g8f6", "d7d6", "e7e6"),
    }
    if board.fullmove_number > 2:
        return None
    ply = 2 * (board.fullmove_number - 1) + (0 if board.turn == chess.WHITE else 1)
    legal_set = set(legal)
    for uci in candidates_by_ply.get(ply, ()):
        move = chess.Move.from_uci(uci)
        if move in legal_set:
            return move
    return None


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    score = _evaluate_absolute(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_absolute(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    white_bishops = 0
    black_bishops = 0
    non_pawn_material = 0

    piece_map = board.piece_map()
    for square, piece in piece_map.items():
        sign = 1 if piece.color == chess.WHITE else -1
        value = PIECE_VALUES[piece.piece_type]
        if piece.piece_type != chess.PAWN:
            non_pawn_material += value
        pst_score = _pst_value(piece, square, non_pawn_material)
        score += sign * (value + pst_score)
        if piece.piece_type == chess.BISHOP:
            if piece.color == chess.WHITE:
                white_bishops += 1
            else:
                black_bishops += 1

    if white_bishops >= 2:
        score += 35
    if black_bishops >= 2:
        score -= 35

    score += _pawn_structure_score(board, chess.WHITE)
    score -= _pawn_structure_score(board, chess.BLACK)
    score += _king_safety_score(board, chess.WHITE)
    score -= _king_safety_score(board, chess.BLACK)

    # Mobility is intentionally light to keep evaluation fast.
    turn = board.turn
    try:
        board.turn = chess.WHITE
        white_mobility = board.legal_moves.count()
        board.turn = chess.BLACK
        black_mobility = board.legal_moves.count()
    finally:
        board.turn = turn
    score += 2 * (white_mobility - black_mobility)

    if board.is_check():
        score += -35 if board.turn == chess.WHITE else 35
    return int(score)


def _pst_value(piece: chess.Piece, square: chess.Square, non_pawn_material: int) -> int:
    lookup_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
    if piece.piece_type == chess.KING:
        table = KING_END_PST if non_pawn_material <= 2400 else KING_MID_PST
        return table[lookup_square]
    table = PST.get(piece.piece_type)
    if table is None:
        return 0
    return table[lookup_square]


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = board.pieces(chess.PAWN, color)
    if not pawns:
        return 0
    score = 0
    files: dict[int, int] = {}
    enemy_pawns = board.pieces(chess.PAWN, not color)
    for sq in pawns:
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        files[file_idx] = files.get(file_idx, 0) + 1
        advance = rank_idx if color == chess.WHITE else 7 - rank_idx
        score += max(0, advance - 1) * 4
        if _is_passed_pawn(sq, color, enemy_pawns):
            score += 18 + advance * advance * 3
    for count in files.values():
        if count > 1:
            score -= 12 * (count - 1)
    for sq in pawns:
        f = chess.square_file(sq)
        if files.get(f - 1, 0) == 0 and files.get(f + 1, 0) == 0:
            score -= 10
    return score


def _is_passed_pawn(square: chess.Square, color: chess.Color, enemy_pawns: chess.SquareSet) -> bool:
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    for enemy in enemy_pawns:
        ef = chess.square_file(enemy)
        er = chess.square_rank(enemy)
        if abs(ef - file_idx) > 1:
            continue
        if color == chess.WHITE and er > rank_idx:
            return False
        if color == chess.BLACK and er < rank_idx:
            return False
    return True


def _king_safety_score(board: chess.Board, color: chess.Color) -> int:
    king = board.king(color)
    if king is None:
        return -500
    score = 0
    rank = chess.square_rank(king)
    file_idx = chess.square_file(king)
    home_rank = 0 if color == chess.WHITE else 7
    if rank == home_rank and file_idx in (0, 1, 2, 6, 7):
        score += 25
    own_pawns = board.pieces(chess.PAWN, color)
    shield_rank = rank + (1 if color == chess.WHITE else -1)
    if 0 <= shield_rank <= 7:
        for df in (-1, 0, 1):
            f = file_idx + df
            if 0 <= f <= 7 and chess.square(f, shield_rank) in own_pawns:
                score += 8
    attackers = board.attackers(not color, king)
    score -= 12 * len(attackers)
    return score


def _capture_value(board: chess.Board, move: chess.Move) -> int:
    victim = board.piece_at(move.to_square)
    if victim is None and board.is_en_passant(move):
        victim_value = PIECE_VALUES[chess.PAWN]
    else:
        victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
    attacker = board.piece_at(move.from_square)
    attacker_value = PIECE_VALUES.get(attacker.piece_type, 1) if attacker else 1
    promo = PIECE_VALUES.get(move.promotion, 0) if move.promotion else 0
    return 10 * victim_value - attacker_value + promo
