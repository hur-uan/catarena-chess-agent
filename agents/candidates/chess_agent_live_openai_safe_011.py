"""Self-contained CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent uses python-chess only, performs no network or file I/O, and always
validates the returned move against legal_moves before returning it.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import chess

INF = 10_000_000
MATE = 9_000_000
DEFAULT_TIME_LIMIT_MS = 100

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Piece-square tables are from White's perspective and mirrored for Black.
PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 27, 27, 10, 5, 5,
    0, 0, 0, 25, 25, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -25, -25, 10, 10, 5,
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
    -30, -10, 0, 0, 0, 0, -10, -30,
    -30, 0, 20, 30, 30, 20, 0, -30,
    -30, 0, 30, 40, 40, 30, 0, -30,
    -30, 0, 30, 40, 40, 30, 0, -30,
    -30, 0, 20, 30, 30, 20, 0, -30,
    -30, -10, 0, 0, 0, 0, -10, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]
PSTS = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
}

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


@dataclass
class SearchState:
    deadline: float
    nodes: int = 0
    stopped: bool = False


class ChessAgent:
    """Small wrapper compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = DEFAULT_TIME_LIMIT_MS) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(observation: Any, output_format: str = "uci", time_limit_ms: int = DEFAULT_TIME_LIMIT_MS) -> str:
    """Choose a legal chess move for the supplied observation."""
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    legal_set = {move.uci() for move in legal_moves}

    # Fast tactical win: if any move mates immediately, play it.
    for move in _ordered_moves(board, legal_moves):
        board.push(move)
        gives_mate = board.is_checkmate()
        board.pop()
        if gives_mate and move.uci() in legal_set:
            return _format_move(board, move, output_format)

    budget_ms = _safe_budget_ms(time_limit_ms)
    state = SearchState(deadline=time.monotonic() + budget_ms / 1000.0)
    best_move = _fallback_move(board, legal_moves)
    best_score = -INF

    # Depth is deliberately conservative; quiescence supplies tactical extension.
    max_depth = _choose_depth(board, budget_ms)
    ordered_root = _ordered_moves(board, legal_moves)

    for depth in range(1, max_depth + 1):
        if _time_up(state):
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        beta = INF
        for move in ordered_root:
            if _time_up(state):
                break
            board.push(move)
            score = -_negamax(board, depth - 1, -beta, -alpha, state, ply=1)
            board.pop()
            if state.stopped:
                break
            if score > current_score or (score == current_score and _move_tiebreak(board, move) > _move_tiebreak(board, current_best)):
                current_score = score
                current_best = move
            if score > alpha:
                alpha = score
        if not state.stopped and current_best in legal_moves:
            best_move = current_best
            best_score = current_score
            # Do not waste time if a forced mate is already found.
            if best_score > MATE - 1000:
                break

    if best_move.uci() not in legal_set:
        best_move = _fallback_move(board, legal_moves)
    return _format_move(board, best_move, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    """Parse common CATArena payloads without file/network access."""
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
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

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _safe_budget_ms(time_limit_ms: int) -> int:
    try:
        requested = int(time_limit_ms)
    except (TypeError, ValueError):
        requested = DEFAULT_TIME_LIMIT_MS
    requested = max(10, requested)
    # Leave overhead for the arena and Python runtime.
    if requested <= 30:
        return max(5, requested - 5)
    if requested <= 100:
        return max(15, requested - 15)
    return max(30, min(requested - 25, 450))


def _choose_depth(board: chess.Board, budget_ms: int) -> int:
    legal_count = board.legal_moves.count()
    phase = _phase_material(board)
    if budget_ms < 35:
        return 2
    if budget_ms < 85:
        return 3 if legal_count <= 28 else 2
    if budget_ms < 180:
        return 4 if legal_count <= 18 or phase < 2600 else 3
    return 4


def _time_up(state: SearchState) -> bool:
    if state.nodes & 63 == 0 and time.monotonic() >= state.deadline:
        state.stopped = True
    return state.stopped


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, state: SearchState, ply: int) -> int:
    state.nodes += 1
    if _time_up(state):
        return 0

    if board.is_checkmate():
        return -MATE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, state, ply)

    best = -INF
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return -MATE + ply if board.is_check() else 0

    for move in _ordered_moves(board, legal_moves):
        board.push(move)
        score = -_negamax(board, depth - 1, -beta, -alpha, state, ply + 1)
        board.pop()
        if state.stopped:
            return 0
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(board: chess.Board, alpha: int, beta: int, state: SearchState, ply: int) -> int:
    state.nodes += 1
    if _time_up(state):
        return 0

    if board.is_checkmate():
        return -MATE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    tactical_moves = []
    for move in board.legal_moves:
        if board.is_capture(move) or move.promotion or board.gives_check(move):
            tactical_moves.append(move)

    for move in _ordered_moves(board, tactical_moves):
        # Delta pruning for quiet checks is intentionally avoided; correctness is safer.
        board.push(move)
        score = -_quiescence(board, -beta, -alpha, state, ply + 1)
        board.pop()
        if state.stopped:
            return 0
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, move: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_type_at(move.from_square) or chess.PAWN
    captured_piece = board.piece_type_at(move.to_square)
    if captured_piece is None and board.is_en_passant(move):
        captured_piece = chess.PAWN
    if captured_piece is not None:
        score += 10_000 + 10 * PIECE_VALUES[captured_piece] - PIECE_VALUES[moving_piece]
    if move.promotion:
        score += 8_000 + PIECE_VALUES.get(move.promotion, 0)
    if board.gives_check(move):
        score += 1_200
    if move.to_square in CENTER_SQUARES:
        score += 90
    elif move.to_square in EXTENDED_CENTER:
        score += 35
    if board.is_castling(move):
        score += 250
    if moving_piece in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 12:
        score += 30
    return score


def _move_tiebreak(board: chess.Board, move: chess.Move) -> int:
    return _move_order_score(board, move) + (63 - move.from_square) + move.to_square


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    # Deterministic fallback: prefer safe tactical/forcing moves using the same ordering.
    ordered = _ordered_moves(board, legal_moves)
    for move in ordered:
        board.push(move)
        own_king_ok = not board.is_checkmate()
        board.pop()
        if own_king_ok:
            return move
    return ordered[0]


def _format_move(board: chess.Board, move: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").lower().strip()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(move)
        except (ValueError, AssertionError):
            return move.uci()
    return move.uci()


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    score = _evaluate_white_minus_black(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_minus_black(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE if board.turn == chess.WHITE else MATE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    phase = _phase_material(board)
    endgame = phase < 1800

    for color in (chess.WHITE, chess.BLACK):
        sign = 1 if color == chess.WHITE else -1
        bishops = 0
        for piece_type in chess.PIECE_TYPES:
            pieces = board.pieces(piece_type, color)
            if piece_type == chess.BISHOP:
                bishops = len(pieces)
            for square in pieces:
                score += sign * PIECE_VALUES[piece_type]
                pst_square = square if color == chess.WHITE else chess.square_mirror(square)
                if piece_type == chess.KING:
                    score += sign * (KING_END_PST[pst_square] if endgame else KING_MID_PST[pst_square])
                else:
                    score += sign * PSTS[piece_type][pst_square]
                if square in CENTER_SQUARES and piece_type != chess.KING:
                    score += sign * 12
        if bishops >= 2:
            score += sign * 35

    score += _pawn_structure_score(board, chess.WHITE)
    score -= _pawn_structure_score(board, chess.BLACK)
    score += _king_safety_score(board, chess.WHITE, endgame)
    score -= _king_safety_score(board, chess.BLACK, endgame)
    score += _mobility_score(board)

    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 12
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 12

    if board.is_check():
        score += -25 if board.turn == chess.WHITE else 25
    return score


def _phase_material(board: chess.Board) -> int:
    total = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += len(board.pieces(piece_type, chess.WHITE)) * PIECE_VALUES[piece_type]
        total += len(board.pieces(piece_type, chess.BLACK)) * PIECE_VALUES[piece_type]
    return total


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    if not pawns:
        return 0
    files: dict[int, int] = {}
    for square in pawns:
        files[chess.square_file(square)] = files.get(chess.square_file(square), 0) + 1

    score = 0
    enemy = not color
    enemy_pawns = board.pieces(chess.PAWN, enemy)
    direction = 1 if color == chess.WHITE else -1

    for square in pawns:
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)
        if files[file_index] > 1:
            score -= 12
        if files.get(file_index - 1, 0) == 0 and files.get(file_index + 1, 0) == 0:
            score -= 10

        passed = True
        for adjacent_file in (file_index - 1, file_index, file_index + 1):
            if adjacent_file < 0 or adjacent_file > 7:
                continue
            for enemy_square in enemy_pawns:
                if chess.square_file(enemy_square) != adjacent_file:
                    continue
                enemy_rank = chess.square_rank(enemy_square)
                if (color == chess.WHITE and enemy_rank > rank_index) or (color == chess.BLACK and enemy_rank < rank_index):
                    passed = False
                    break
            if not passed:
                break
        if passed:
            advance = rank_index if color == chess.WHITE else 7 - rank_index
            score += 18 + 8 * advance

        next_rank = rank_index + direction
        if 0 <= next_rank <= 7:
            front_square = chess.square(file_index, next_rank)
            if board.piece_at(front_square) is not None:
                score -= 8
    return score


def _king_safety_score(board: chess.Board, color: chess.Color, endgame: bool) -> int:
    if endgame:
        return 0
    king_square = board.king(color)
    if king_square is None:
        return -500
    score = 0
    enemy = not color
    if board.is_attacked_by(enemy, king_square):
        score -= 40
    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    shield_rank = king_rank + (1 if color == chess.WHITE else -1)
    if 0 <= shield_rank <= 7:
        for file_index in (king_file - 1, king_file, king_file + 1):
            if 0 <= file_index <= 7:
                piece = board.piece_at(chess.square(file_index, shield_rank))
                if piece and piece.color == color and piece.piece_type == chess.PAWN:
                    score += 12
                else:
                    score -= 8
    attackers = 0
    for square in chess.SquareSet(chess.BB_KING_ATTACKS[king_square]):
        if board.is_attacked_by(enemy, square):
            attackers += 1
    score -= 5 * attackers
    return score


def _mobility_score(board: chess.Board) -> int:
    # Lightweight pseudo-legal mobility estimate to avoid expensive legal generation for both sides.
    turn = board.turn
    score = 0
    try:
        board.turn = chess.WHITE
        score += min(60, board.legal_moves.count())
        board.turn = chess.BLACK
        score -= min(60, board.legal_moves.count())
    finally:
        board.turn = turn
    return 2 * score
