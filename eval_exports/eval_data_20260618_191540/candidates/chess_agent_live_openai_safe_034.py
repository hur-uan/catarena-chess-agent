"""Safe self-contained CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This version intentionally avoids network calls, subprocesses, file access, eval/exec,
and dynamic imports.  It relies only on python-chess, validates every selected move
against board.legal_moves, and falls back to a legal move if anything unexpected
occurs.
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

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}

# Piece-square tables from White's perspective.  Values are intentionally modest;
# material and tactics should dominate.
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
    0, 0, 5, 10, 10, 5, 0, 0,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5,
    0, 0, 0, 5, 5, 0, 0, 0,
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
PSTS = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
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
        legal_moves = list(board.legal_moves)
        if not legal_moves or board.is_game_over(claim_draw=False):
            return ""

        legal_hints = _extract_legal_move_hints(observation)
        hinted_moves = [mv for mv in legal_moves if mv.uci() in legal_hints]
        search_moves = hinted_moves if hinted_moves else legal_moves

        chosen = _choose_move(board, search_moves, time_limit_ms)
        if chosen not in legal_moves:
            chosen = _fallback_move(board, legal_moves)
        return _format_move(board, chosen, output_format)
    except Exception:
        try:
            board = _parse_observation(observation)
            legal_moves = list(board.legal_moves)
            if not legal_moves:
                return ""
            return _format_move(board, _fallback_move(board, legal_moves), output_format)
        except Exception:
            return ""


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                return chess.Board(value.strip())
        nested = observation.get("observation")
        if nested is not None and nested is not observation:
            return _parse_observation(nested)
    if isinstance(observation, str):
        text = observation.strip()
        if text:
            return chess.Board(text)
    return chess.Board()


def _extract_legal_move_hints(observation: Any) -> set[str]:
    hints: set[str] = set()
    if not isinstance(observation, dict):
        return hints
    for key in ("legal_moves", "legalMoves", "moves"):
        value = observation.get(key)
        if isinstance(value, (list, tuple, set)):
            for item in value:
                text = str(item).strip()
                if text:
                    hints.add(text)
    return hints


def _format_move(board: chess.Board, move_obj: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def _choose_move(board: chess.Board, root_moves: list[chess.Move], time_limit_ms: int) -> chess.Move:
    # Immediate winning tactic: if a legal move checkmates, play it without search.
    for mv in _ordered_moves(board, root_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv

    start = time.perf_counter()
    budget_ms = max(8, min(int(time_limit_ms) if isinstance(time_limit_ms, int) else 100, 250))
    # Keep a conservative margin to avoid platform timeouts.
    deadline = start + max(0.004, (budget_ms - 5) / 1000.0)

    piece_count = len(board.piece_map())
    if budget_ms < 35:
        max_depth = 2
    elif budget_ms < 80:
        max_depth = 3
    elif piece_count <= 12:
        max_depth = 5
    else:
        max_depth = 4

    best_move = _fallback_move(board, root_moves)
    best_score = -INF
    ordered_root = _ordered_moves(board, root_moves)

    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        completed = True
        for mv in ordered_root:
            if time.perf_counter() >= deadline:
                completed = False
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -INF, -alpha, deadline, 1)
            board.pop()
            if score > current_score:
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score
        if completed:
            best_move = current_best
            best_score = current_score
            ordered_root = [best_move] + [mv for mv in ordered_root if mv != best_move]
            if best_score >= MATE_SCORE - 1000:
                break
        else:
            break
    return best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, deadline: float, ply: int) -> int:
    if time.perf_counter() >= deadline:
        return _evaluate_for_side_to_move(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    best = -INF
    moves = _ordered_moves(board, list(board.legal_moves))
    for mv in moves:
        if time.perf_counter() >= deadline:
            break
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best if best != -INF else _evaluate_for_side_to_move(board)


def _quiescence(board: chess.Board, alpha: int, beta: int, deadline: float, ply: int) -> int:
    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat
    if time.perf_counter() >= deadline:
        return alpha

    noisy = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            noisy.append(mv)
    for mv in _ordered_moves(board, noisy):
        if time.perf_counter() >= deadline:
            break
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
    return alpha


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_score(board, mv), reverse=True)


def _move_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if board.gives_check(mv):
        score += 900
    if mv.promotion:
        score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(mv.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 5000 + 10 * victim_value - attacker_value
    if board.is_castling(mv):
        score += 250
    piece = board.piece_at(mv.from_square)
    if piece:
        if mv.to_square in CENTER:
            score += 90
        elif mv.to_square in EXTENDED_CENTER:
            score += 35
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 10:
            home_rank = chess.square_rank(mv.from_square)
            if (piece.color == chess.WHITE and home_rank == 0) or (piece.color == chess.BLACK and home_rank == 7):
                score += 70
        if piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 45
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
    non_king_material = 0
    piece_map = board.piece_map()
    for square, piece in piece_map.items():
        value = PIECE_VALUES[piece.piece_type]
        if piece.piece_type != chess.KING:
            non_king_material += value
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        if piece.piece_type == chess.KING:
            table = KING_END_PST if non_king_material <= 2200 else KING_MID_PST
            positional = table[pst_square]
        else:
            positional = PSTS.get(piece.piece_type, [0] * 64)[pst_square]
        delta = value + positional
        score += delta if piece.color == chess.WHITE else -delta

    # Mobility: small enough not to prefer activity over material, but helpful in quiet positions.
    turn = board.turn
    board.turn = chess.WHITE
    white_mobility = board.legal_moves.count() if board.king(chess.WHITE) is not None else 0
    board.turn = chess.BLACK
    black_mobility = board.legal_moves.count() if board.king(chess.BLACK) is not None else 0
    board.turn = turn
    score += 2 * (white_mobility - black_mobility)

    # Bishop pair bonus.
    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        score += 25
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        score -= 25

    # Simple king danger: penalize being in check and attacked king ring squares.
    score += _king_safety(board, chess.WHITE)
    score -= _king_safety(board, chess.BLACK)
    return score


def _king_safety(board: chess.Board, color: chess.Color) -> int:
    king_sq = board.king(color)
    if king_sq is None:
        return -5000
    penalty = 0
    if board.is_attacked_by(not color, king_sq):
        penalty += 60
    for sq in chess.SquareSet(chess.BB_KING_ATTACKS[king_sq]):
        if board.is_attacked_by(not color, sq):
            penalty += 3
    return -penalty


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    if not legal_moves:
        return chess.Move.null()
    ordered = _ordered_moves(board, legal_moves)
    # Avoid moves that immediately allow capture of an undefended queen if another
    # reasonable move exists; this is a cheap safety filter for shallow searches.
    for mv in ordered:
        if _move_is_legal_and_reasonable(board, mv):
            return mv
    return ordered[0]


def _move_is_legal_and_reasonable(board: chess.Board, mv: chess.Move) -> bool:
    if mv not in board.legal_moves:
        return False
    moving_piece = board.piece_at(mv.from_square)
    if moving_piece is None:
        return True
    board.push(mv)
    safe = True
    if moving_piece.piece_type == chess.QUEEN:
        if board.is_attacked_by(board.turn, mv.to_square) and not board.is_attacked_by(not board.turn, mv.to_square):
            safe = False
    board.pop()
    return safe
