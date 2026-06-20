"""Self-contained safe CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str
"""

from __future__ import annotations

import math
import time
from typing import Any

import chess

MATE_SCORE = 100000
INF = 100000000

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]

KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]

BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

ROOK_TABLE = [
    0, 0, 5, 10, 10, 5, 0, 0,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5,
    0, 0, 0, 5, 5, 0, 0, 0,
]

QUEEN_TABLE = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]

KING_TABLE = [
    20, 30, 10, 0, 0, 10, 30, 20,
    20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
]

KING_ENDGAME_TABLE = [
    -50, -30, -30, -30, -30, -30, -30, -50,
    -30, -20, -10, -10, -10, -10, -20, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]

PIECE_TABLES = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE,
}

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


def _mirror_index(square: chess.Square, color: chess.Color) -> int:
    return square if color == chess.WHITE else chess.square_mirror(square)


class _Searcher:
    def __init__(self, deadline: float, max_nodes: int) -> None:
        self.deadline = deadline
        self.max_nodes = max_nodes
        self.nodes = 0
        self.stop = False
        self.tt: dict[tuple[str, int, int], int] = {}

    def out_of_time(self) -> bool:
        if self.stop:
            return True
        self.nodes += 1
        if self.nodes >= self.max_nodes or time.perf_counter() >= self.deadline:
            self.stop = True
        return self.stop

    def search_root(self, board: chess.Board, depth: int) -> chess.Move | None:
        best_move = None
        best_score = -INF
        alpha = -INF
        beta = INF
        for move in _ordered_moves(board):
            if self.out_of_time():
                break
            board.push(move)
            score = -self.negamax(board, depth - 1, -beta, -alpha, 1)
            board.pop()
            if self.stop:
                break
            if score > best_score or best_move is None:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
        return best_move

    def negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
        if self.out_of_time():
            return _evaluate(board)
        if board.is_checkmate():
            return -MATE_SCORE + ply
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
            return 0
        if depth <= 0:
            return self.quiescence(board, alpha, beta, ply)

        key = (board.transposition_key().hex() if hasattr(board.transposition_key(), "hex") else str(board.transposition_key()), depth, int(board.turn)) if hasattr(board, "transposition_key") else (board.board_fen(), depth, int(board.turn))
        cached = self.tt.get(key)
        if cached is not None:
            return cached

        best = -INF
        for move in _ordered_moves(board):
            board.push(move)
            score = -self.negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if self.stop:
                return _evaluate(board)
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        self.tt[key] = best
        return best

    def quiescence(self, board: chess.Board, alpha: int, beta: int, ply: int) -> int:
        if self.out_of_time():
            return _evaluate(board)
        if board.is_checkmate():
            return -MATE_SCORE + ply
        stand_pat = _evaluate(board)
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        noisy_moves = []
        for move in board.legal_moves:
            if board.is_capture(move) or move.promotion or board.gives_check(move):
                noisy_moves.append(move)
        noisy_moves.sort(key=lambda move: _move_score(board, move), reverse=True)

        for move in noisy_moves[:18]:
            board.push(move)
            score = -self.quiescence(board, -beta, -alpha, ply + 1)
            board.pop()
            if self.stop:
                return alpha
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha


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

    try:
        chosen = _choose_move(board, max(1, int(time_limit_ms)))
    except Exception:
        chosen = None

    if chosen not in legal_moves:
        chosen = _safe_fallback(board)
    if chosen not in legal_moves:
        chosen = legal_moves[0]
    return _format_move(board, chosen, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _choose_move(board: chess.Board, time_limit_ms: int) -> chess.Move | None:
    mate = _find_immediate_mate(board)
    if mate is not None:
        return mate

    legal_count = board.legal_moves.count()
    if legal_count == 1:
        return next(iter(board.legal_moves))

    start = time.perf_counter()
    budget = min(max(time_limit_ms, 1), 250) / 1000.0
    deadline = start + max(0.003, budget * 0.72)
    non_king_material = _non_king_material(board)

    if time_limit_ms < 25:
        max_depth = 1
        max_nodes = 800
    elif time_limit_ms < 80:
        max_depth = 2
        max_nodes = 3000
    elif non_king_material <= 2600 and time_limit_ms >= 120:
        max_depth = 4
        max_nodes = 18000
    else:
        max_depth = 3
        max_nodes = 9000

    searcher = _Searcher(deadline, max_nodes)
    best = _safe_fallback(board)
    for depth in range(1, max_depth + 1):
        candidate = searcher.search_root(board, depth)
        if searcher.stop:
            break
        if candidate is not None:
            best = candidate
    return best


def _find_immediate_mate(board: chess.Board) -> chess.Move | None:
    for move in _ordered_moves(board):
        board.push(move)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return move
    return None


def _ordered_moves(board: chess.Board) -> list[chess.Move]:
    moves = list(board.legal_moves)
    moves.sort(key=lambda move: _move_score(board, move), reverse=True)
    return moves


def _move_score(board: chess.Board, move: chess.Move) -> int:
    score = 0
    moved_piece = board.piece_at(move.from_square)
    if move.promotion:
        score += 8000 + PIECE_VALUES.get(move.promotion, 0)
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        if victim is None and board.is_en_passant(move):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker_value = PIECE_VALUES.get(moved_piece.piece_type, 0) if moved_piece else 0
        score += 5000 + 10 * victim_value - attacker_value
    if board.gives_check(move):
        score += 900
    if board.is_castling(move):
        score += 300
    if move.to_square in CENTER_SQUARES:
        score += 120
    elif move.to_square in EXTENDED_CENTER:
        score += 45
    if moved_piece and moved_piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        rank = chess.square_rank(move.to_square)
        if moved_piece.color == chess.BLACK:
            rank = 7 - rank
        if rank >= 2:
            score += 80
    return score


def _evaluate(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    endgame = _non_king_material(board) <= 2400
    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        value = PIECE_VALUES[piece.piece_type]
        table = KING_ENDGAME_TABLE if piece.piece_type == chess.KING and endgame else PIECE_TABLES[piece.piece_type]
        score += sign * (value + table[_mirror_index(square, piece.color)])

    score += _bishop_pair_bonus(board)
    score += _pawn_structure_score(board)
    score += _king_safety_score(board)

    turn = board.turn
    try:
        mobility = board.legal_moves.count()
        board.turn = not turn
        opponent_mobility = board.legal_moves.count() if board.status() == chess.STATUS_VALID else mobility
    finally:
        board.turn = turn
    score += 2 * (mobility - opponent_mobility) * (1 if turn == chess.WHITE else -1)

    if board.is_check():
        score -= 35
    return score if board.turn == chess.WHITE else -score


def _bishop_pair_bonus(board: chess.Board) -> int:
    score = 0
    for color in (chess.WHITE, chess.BLACK):
        if len(board.pieces(chess.BISHOP, color)) >= 2:
            score += 35 if color == chess.WHITE else -35
    return score


def _pawn_structure_score(board: chess.Board) -> int:
    score = 0
    for color in (chess.WHITE, chess.BLACK):
        sign = 1 if color == chess.WHITE else -1
        pawns = list(board.pieces(chess.PAWN, color))
        files: dict[int, int] = {}
        for square in pawns:
            file_index = chess.square_file(square)
            files[file_index] = files.get(file_index, 0) + 1
        for square in pawns:
            file_index = chess.square_file(square)
            rank = chess.square_rank(square) if color == chess.WHITE else 7 - chess.square_rank(square)
            score += sign * rank * 4
            if files[file_index] > 1:
                score -= sign * 10
            if files.get(file_index - 1, 0) == 0 and files.get(file_index + 1, 0) == 0:
                score -= sign * 12
    return score


def _king_safety_score(board: chess.Board) -> int:
    score = 0
    for color in (chess.WHITE, chess.BLACK):
        king_square = board.king(color)
        if king_square is None:
            continue
        sign = 1 if color == chess.WHITE else -1
        shield = 0
        direction = 1 if color == chess.WHITE else -1
        king_file = chess.square_file(king_square)
        king_rank = chess.square_rank(king_square)
        for file_index in (king_file - 1, king_file, king_file + 1):
            rank = king_rank + direction
            if 0 <= file_index <= 7 and 0 <= rank <= 7:
                piece = board.piece_at(chess.square(file_index, rank))
                if piece and piece.color == color and piece.piece_type == chess.PAWN:
                    shield += 1
        score += sign * shield * 12
        attackers = board.attackers(not color, king_square)
        score -= sign * len(attackers) * 18
    return score


def _non_king_material(board: chess.Board) -> int:
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        if piece_type != chess.KING:
            total += value * (len(board.pieces(piece_type, chess.WHITE)) + len(board.pieces(piece_type, chess.BLACK)))
    return total


def _safe_fallback(board: chess.Board) -> chess.Move | None:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None
    legal_moves.sort(key=lambda move: (_move_score(board, move), move.uci()), reverse=True)
    for move in legal_moves:
        board.push(move)
        safe = not board.is_checkmate()
        board.pop()
        if safe:
            return move
    return legal_moves[0]


def _format_move(board: chess.Board, selected: chess.Move, output_format: str) -> str:
    fmt = str(output_format or "uci").strip().lower()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(selected)
        except Exception:
            return selected.uci()
    return selected.uci()


def _parse_observation(observation: Any) -> chess.Board:
    fen = _extract_fen(observation)
    if fen:
        try:
            return chess.Board(fen)
        except Exception:
            pass
    return chess.Board()


def _extract_fen(observation: Any) -> str:
    if isinstance(observation, chess.Board):
        return observation.fen()
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and _looks_like_fen(value):
                return value.strip()
        nested = observation.get("observation")
        if isinstance(nested, dict):
            return _extract_fen(nested)
    if isinstance(observation, str):
        text = observation.strip()
        if _looks_like_fen(text):
            return text
    return ""


def _looks_like_fen(text: str) -> bool:
    parts = text.strip().split()
    return len(parts) >= 4 and "/" in parts[0] and parts[1] in {"w", "b"}
