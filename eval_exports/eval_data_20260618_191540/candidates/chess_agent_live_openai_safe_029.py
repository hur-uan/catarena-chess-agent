"""Safe self-contained CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation intentionally avoids network calls, subprocesses, file I/O,
dynamic imports, eval/exec, and external engine services.  Every returned move is
validated against python-chess legal_moves, with a deterministic legal fallback.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
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

# Piece-square tables from White's point of view.  Black uses mirrored squares.
PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 28, 28, 10, 5, 5,
    0, 0, 0, 24, 24, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -24, -24, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 12, 15, 15, 12, 5, -30,
    -30, 0, 15, 22, 22, 15, 0, -30,
    -30, 5, 15, 22, 22, 15, 5, -30,
    -30, 0, 12, 15, 15, 12, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 15, 15, 10, 0, -10,
    -10, 5, 5, 15, 15, 5, 5, -10,
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
    -10, 0, 5, 0, 0, 0, 0, -10,
    -10, 5, 5, 5, 5, 5, 0, -10,
    0, 0, 5, 5, 5, 5, 0, -5,
    -5, 0, 5, 5, 5, 5, 0, -5,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_MID_TABLE = [
    20, 30, 10, 0, 0, 10, 30, 20,
    20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
]
KING_END_TABLE = [
    -50, -30, -30, -30, -30, -30, -30, -50,
    -30, -10, 0, 0, 0, 0, -10, -30,
    -30, 0, 20, 30, 30, 20, 0, -30,
    -30, 0, 30, 40, 40, 30, 0, -30,
    -30, 0, 30, 40, 40, 30, 0, -30,
    -30, 0, 20, 30, 30, 20, 0, -30,
    -30, -10, 0, 0, 0, 0, -10, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]
PST = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_MID_TABLE,
}
CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


@dataclass
class SearchLimits:
    deadline: float
    node_limit: int
    nodes: int = 0
    stopped: bool = False


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

    chosen = _choose_move(board, legal_moves, time_limit_ms)
    if chosen not in legal_moves:
        chosen = _fallback_move(board, legal_moves)

    fmt = str(output_format or "uci").strip().lower()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(chosen)
        except Exception:
            return chosen.uci()
    return chosen.uci()


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
    moves: list[str] = []

    if isinstance(observation, dict):
        for key in ("fen", "board", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        raw_moves = observation.get("moves") or observation.get("move_history") or observation.get("history")
        if isinstance(raw_moves, str):
            moves = [part.strip() for part in raw_moves.replace(",", " ").split() if part.strip()]
        elif isinstance(raw_moves, (list, tuple)):
            moves = [str(part).strip() for part in raw_moves if str(part).strip()]
    elif isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text
    else:
        maybe_fen = getattr(observation, "fen", None)
        if isinstance(maybe_fen, str) and maybe_fen.strip():
            fen = maybe_fen.strip()

    try:
        board = chess.Board(fen) if fen else chess.Board()
    except Exception:
        board = chess.Board()

    for mv in moves:
        try:
            parsed = chess.Move.from_uci(mv)
        except Exception:
            continue
        if parsed in board.legal_moves:
            board.push(parsed)
    return board


def _choose_move(board: chess.Board, legal_moves: list[chess.Move], time_limit_ms: int) -> chess.Move:
    # Immediate tactical checks are cheap and reduce horizon mistakes.
    mate_move = _find_immediate_mate(board, legal_moves)
    if mate_move is not None:
        return mate_move

    safe_ms = max(8, min(int(time_limit_ms or 100), 250))
    margin = 0.006 if safe_ms >= 40 else 0.003
    deadline = time.perf_counter() + max(0.004, safe_ms / 1000.0 - margin)
    node_limit = 1800 if safe_ms < 60 else 5000 if safe_ms < 120 else 9000
    limits = SearchLimits(deadline=deadline, node_limit=node_limit)

    # A deterministic one-ply tactical fallback is always available if search is cut.
    best_move = _best_static_move(board, legal_moves)
    best_score = -INF

    max_depth = _depth_for(board, safe_ms)
    ordered = _order_moves(board, legal_moves)

    for depth in range(1, max_depth + 1):
        if _time_up(limits):
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        beta = INF
        for mv in ordered:
            if _time_up(limits):
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -beta, -alpha, limits, 0)
            board.pop()
            if limits.stopped:
                break
            if score > current_score:
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score
        if not limits.stopped and current_best in legal_moves:
            best_move = current_best
            best_score = current_score
            ordered = [best_move] + [mv for mv in ordered if mv != best_move]
        if best_score > MATE_SCORE - 1000:
            break

    return best_move if best_move in legal_moves else _fallback_move(board, legal_moves)


def _depth_for(board: chess.Board, safe_ms: int) -> int:
    pieces = len(board.piece_map())
    if safe_ms < 35:
        return 1
    if safe_ms < 80:
        return 2
    if pieces <= 12 and safe_ms >= 90:
        return 4
    return 3


def _time_up(limits: SearchLimits) -> bool:
    if limits.stopped:
        return True
    if limits.nodes >= limits.node_limit:
        limits.stopped = True
        return True
    if limits.nodes % 128 == 0 and time.perf_counter() >= limits.deadline:
        limits.stopped = True
        return True
    return False


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, limits: SearchLimits, ply: int) -> int:
    limits.nodes += 1
    if _time_up(limits):
        return _evaluate_for_turn(board)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, limits, ply, 0)

    best = -INF
    legal = list(board.legal_moves)
    if not legal:
        return _evaluate_for_turn(board)

    for mv in _order_moves(board, legal):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, limits, ply + 1)
        board.pop()
        if limits.stopped:
            return score
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(board: chess.Board, alpha: int, beta: int, limits: SearchLimits, ply: int, qdepth: int) -> int:
    limits.nodes += 1
    stand_pat = _evaluate_for_turn(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if qdepth >= 4 or _time_up(limits):
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion is not None:
            tactical.append(mv)
        elif board.is_check() and qdepth < 2:
            tactical.append(mv)
    for mv in _order_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, limits, ply + 1, qdepth + 1)
        board.pop()
        if limits.stopped:
            return alpha
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _find_immediate_mate(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move | None:
    ordered = _order_moves(board, legal_moves)
    for mv in ordered:
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _best_static_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    best = legal_moves[0]
    best_score = -INF
    for mv in _order_moves(board, legal_moves):
        board.push(mv)
        if board.is_checkmate():
            score = MATE_SCORE
        elif board.is_stalemate():
            score = 0
        else:
            score = -_evaluate_for_turn(board)
        board.pop()
        if score > best_score:
            best_score = score
            best = mv
    return best


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    # Deterministic and legal: prefer checks/captures/promotions, then stable UCI order.
    return sorted(legal_moves, key=lambda mv: (-_move_order_score(board, mv), mv.uci()))[0]


def _order_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: (-_move_order_score(board, mv), mv.uci()))


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    moving = board.piece_at(mv.from_square)
    victim = board.piece_at(mv.to_square)

    if board.is_capture(mv):
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker_value = PIECE_VALUES.get(moving.piece_type, 0) if moving else 0
        score += 10000 + 10 * victim_value - attacker_value

    if mv.promotion is not None:
        score += 9000 + PIECE_VALUES.get(mv.promotion, 0)

    if board.gives_check(mv):
        score += 3500
    if board.is_castling(mv):
        score += 800
    if mv.to_square in CENTER_SQUARES:
        score += 160
    elif mv.to_square in EXTENDED_CENTER:
        score += 60

    if moving is not None:
        if moving.piece_type in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 12:
            home_rank = 0 if moving.color == chess.WHITE else 7
            if chess.square_rank(mv.from_square) == home_rank:
                score += 220
        if moving.piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 90
    return score


def _evaluate_for_turn(board: chess.Board) -> int:
    score = _evaluate_white_perspective(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_perspective(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    endgame = _is_endgame(board)
    piece_map = board.piece_map()

    for sq, piece in piece_map.items():
        sign = 1 if piece.color == chess.WHITE else -1
        value = PIECE_VALUES[piece.piece_type]
        table = KING_END_TABLE if piece.piece_type == chess.KING and endgame else PST[piece.piece_type]
        table_sq = sq if piece.color == chess.WHITE else chess.square_mirror(sq)
        score += sign * (value + table[table_sq])

    score += _bishop_pair_bonus(board, chess.WHITE) - _bishop_pair_bonus(board, chess.BLACK)
    score += _rook_file_bonus(board, chess.WHITE) - _rook_file_bonus(board, chess.BLACK)
    score += _pawn_structure_score(board, chess.WHITE) - _pawn_structure_score(board, chess.BLACK)
    score += _king_safety_score(board, chess.WHITE) - _king_safety_score(board, chess.BLACK)

    # Small mobility term; computed by temporarily toggling turn rather than deep search.
    score += 2 * (_pseudo_mobility(board, chess.WHITE) - _pseudo_mobility(board, chess.BLACK))

    if board.turn == chess.WHITE and board.is_check():
        score -= 25
    elif board.turn == chess.BLACK and board.is_check():
        score += 25
    return score


def _is_endgame(board: chess.Board) -> bool:
    non_king_material = 0
    for piece_type, value in PIECE_VALUES.items():
        if piece_type in (chess.PAWN, chess.KING):
            continue
        non_king_material += value * (len(board.pieces(piece_type, chess.WHITE)) + len(board.pieces(piece_type, chess.BLACK)))
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    return queens == 0 or non_king_material <= 2600


def _bishop_pair_bonus(board: chess.Board, color: chess.Color) -> int:
    return 35 if len(board.pieces(chess.BISHOP, color)) >= 2 else 0


def _rook_file_bonus(board: chess.Board, color: chess.Color) -> int:
    bonus = 0
    enemy = not color
    for rook_sq in board.pieces(chess.ROOK, color):
        file_index = chess.square_file(rook_sq)
        own_pawns = [sq for sq in board.pieces(chess.PAWN, color) if chess.square_file(sq) == file_index]
        enemy_pawns = [sq for sq in board.pieces(chess.PAWN, enemy) if chess.square_file(sq) == file_index]
        if not own_pawns and not enemy_pawns:
            bonus += 24
        elif not own_pawns:
            bonus += 12
    return bonus


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    files: dict[int, int] = {}
    for sq in pawns:
        file_index = chess.square_file(sq)
        files[file_index] = files.get(file_index, 0) + 1

    score = 0
    for sq in pawns:
        file_index = chess.square_file(sq)
        rank = chess.square_rank(sq)
        advancement = rank if color == chess.WHITE else 7 - rank
        score += advancement * 3
        if files.get(file_index, 0) > 1:
            score -= 10
        if files.get(file_index - 1, 0) == 0 and files.get(file_index + 1, 0) == 0:
            score -= 12
    return score


def _king_safety_score(board: chess.Board, color: chess.Color) -> int:
    king_sq = board.king(color)
    if king_sq is None:
        return -500
    enemy = not color
    score = 0

    # Pawn shield in front of king.
    direction = 1 if color == chess.WHITE else -1
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)
    for df in (-1, 0, 1):
        file_index = king_file + df
        rank = king_rank + direction
        if 0 <= file_index <= 7 and 0 <= rank <= 7:
            sq = chess.square(file_index, rank)
            piece = board.piece_at(sq)
            if piece and piece.color == color and piece.piece_type == chess.PAWN:
                score += 12

    ring = chess.SquareSet(chess.BB_KING_ATTACKS[king_sq])
    attacked = 0
    for sq in ring:
        if board.is_attacked_by(enemy, sq):
            attacked += 1
    score -= 7 * attacked
    if board.is_attacked_by(enemy, king_sq):
        score -= 35
    return score


def _pseudo_mobility(board: chess.Board, color: chess.Color) -> int:
    saved_turn = board.turn
    board.turn = color
    try:
        # Cap the count to keep this term small and predictable.
        count = 0
        for _ in board.legal_moves:
            count += 1
            if count >= 40:
                break
        return count
    finally:
        board.turn = saved_turn
