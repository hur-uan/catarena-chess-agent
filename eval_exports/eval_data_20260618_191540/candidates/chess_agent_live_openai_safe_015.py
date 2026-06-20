"""Standalone safe CATArena chess agent.

Public entry point:
    select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation is intentionally self-contained and avoids network, subprocess,
file I/O, eval/exec, or dynamic imports during play.  Every returned move is
validated against python-chess legal moves, with a deterministic legal fallback.
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

# Compact piece-square tables from White's perspective.  Black mirrors them.
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
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
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

PST = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
    chess.KING: KING_MID_PST,
}

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


class SearchTimeout(Exception):
    """Internal exception used only to stop bounded search."""


@dataclass
class SearchState:
    deadline: float
    node_limit: int
    nodes: int = 0
    qnodes: int = 0

    def tick(self) -> None:
        self.nodes += 1
        if self.nodes >= self.node_limit:
            raise SearchTimeout
        if (self.nodes & 127) == 0 and time.perf_counter() >= self.deadline:
            raise SearchTimeout

    def qtick(self) -> None:
        self.qnodes += 1
        if self.nodes + self.qnodes >= self.node_limit:
            raise SearchTimeout
        if (self.qnodes & 127) == 0 and time.perf_counter() >= self.deadline:
            raise SearchTimeout


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

    fallback = _deterministic_fallback(board, legal_moves)
    chosen = fallback

    # Immediate mates are cheap and more reliable than any heuristic search.
    mate_move = _find_immediate_mate(board, legal_moves)
    if mate_move is not None:
        chosen = mate_move
    else:
        try:
            searched = _search_best_move(board, legal_moves, time_limit_ms)
            if searched in legal_moves:
                chosen = searched
        except Exception:
            # Safety first: never crash or return an illegal move.
            chosen = fallback

    if chosen not in board.legal_moves:
        chosen = fallback
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
    moves: list[str] = []

    if isinstance(observation, dict):
        for key in ("fen", "board", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        raw_moves = observation.get("moves") or observation.get("history") or observation.get("move_history")
        if isinstance(raw_moves, str):
            moves = [part.strip() for part in raw_moves.replace(",", " ").split() if part.strip()]
        elif isinstance(raw_moves, (list, tuple)):
            moves = [str(part).strip() for part in raw_moves if str(part).strip()]
    elif isinstance(observation, str):
        text = observation.strip()
        fen = text if text else None
    else:
        fen = str(observation).strip() if observation is not None else None

    try:
        board = chess.Board(fen) if fen else chess.Board()
    except Exception:
        board = chess.Board()

    for uci in moves:
        try:
            mv = chess.Move.from_uci(uci)
        except Exception:
            continue
        if mv in board.legal_moves:
            board.push(mv)
    return board


def _format_move(board: chess.Board, move_obj: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").strip().lower()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def _find_immediate_mate(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move | None:
    for mv in _ordered_moves(board, legal_moves, None):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _search_best_move(board: chess.Board, legal_moves: list[chess.Move], time_limit_ms: int) -> chess.Move:
    safe_ms = max(8, min(int(time_limit_ms or 100), 500))
    # Leave margin for platform overhead.
    budget = max(0.006, safe_ms / 1000.0 * 0.72)
    deadline = time.perf_counter() + budget
    node_limit = max(700, min(60000, safe_ms * 190))
    state = SearchState(deadline=deadline, node_limit=node_limit)

    best_move = _deterministic_fallback(board, legal_moves)
    ordered = _ordered_moves(board, legal_moves, None)

    # Adaptive depth: most moves get depth 3; quiet/simple positions may reach 4.
    max_depth = 2
    if safe_ms >= 45:
        max_depth = 3
    if safe_ms >= 120 and len(legal_moves) <= 18:
        max_depth = 4

    previous_best: chess.Move | None = best_move
    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        alpha = -INF
        beta = INF
        current_best = previous_best or best_move
        best_score = -INF
        try:
            root_moves = _ordered_moves(board, legal_moves, previous_best)
            for mv in root_moves:
                state.tick()
                board.push(mv)
                score = -_negamax(board, depth - 1, -beta, -alpha, state, 1)
                board.pop()
                score += _root_tiebreak(board, mv)
                if score > best_score:
                    best_score = score
                    current_best = mv
                if score > alpha:
                    alpha = score
            previous_best = current_best
            best_move = current_best
        except SearchTimeout:
            break
    return best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, state: SearchState, ply: int) -> int:
    state.tick()

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, state, ply)

    best = -INF
    legal = list(board.legal_moves)
    for mv in _ordered_moves(board, legal, None):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, state, ply + 1)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(board: chess.Board, alpha: int, beta: int, state: SearchState, ply: int) -> int:
    state.qtick()
    if board.is_checkmate():
        return -MATE_SCORE + ply
    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    # Keep q-search bounded: captures, promotions, and checking moves only.
    tactical: list[chess.Move] = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            tactical.append(mv)
    tactical = _ordered_moves(board, tactical, None)[:18]

    for mv in tactical:
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, state, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    score = _evaluate_white_minus_black(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_minus_black(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    bishops = {chess.WHITE: 0, chess.BLACK: 0}

    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        table = PST[piece.piece_type]
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        positional = table[pst_square]
        piece_score = value + positional
        if piece.color == chess.WHITE:
            score += piece_score
        else:
            score -= piece_score
        if piece.piece_type == chess.BISHOP:
            bishops[piece.color] += 1

    if bishops[chess.WHITE] >= 2:
        score += 35
    if bishops[chess.BLACK] >= 2:
        score -= 35

    # Light mobility term.  push/null avoids expensive legal counting for both sides.
    turn = board.turn
    try:
        board.turn = chess.WHITE
        white_mobility = board.legal_moves.count()
        board.turn = chess.BLACK
        black_mobility = board.legal_moves.count()
    finally:
        board.turn = turn
    score += 2 * (white_mobility - black_mobility)

    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 8
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 8

    if board.is_check():
        score += -20 if board.turn == chess.WHITE else 20
    return score


def _ordered_moves(
    board: chess.Board,
    moves: list[chess.Move],
    preferred: chess.Move | None,
) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv, preferred), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move, preferred: chess.Move | None) -> int:
    if preferred is not None and mv == preferred:
        return 1_000_000

    score = 0
    if mv.promotion:
        score += PIECE_VALUES.get(mv.promotion, 0) + 7000
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        attacker = board.piece_at(mv.from_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 5000 + 10 * victim_value - attacker_value
    if board.gives_check(mv):
        score += 3500
    if board.is_castling(mv):
        score += 500
    if mv.to_square in CENTER_SQUARES:
        score += 120
    elif mv.to_square in EXTENDED_CENTER:
        score += 50

    moving_piece = board.piece_at(mv.from_square)
    if moving_piece is not None:
        if moving_piece.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(mv.from_square) in (0, 7):
            score += 80
        if moving_piece.piece_type == chess.PAWN:
            rank = chess.square_rank(mv.to_square)
            score += rank * 8 if moving_piece.color == chess.WHITE else (7 - rank) * 8
    return score


def _root_tiebreak(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if board.gives_check(mv):
        score += 6
    if board.is_capture(mv):
        score += 4
    if mv.promotion:
        score += 8
    if mv.to_square in CENTER_SQUARES:
        score += 2
    return score


def _deterministic_fallback(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    ordered = _ordered_moves(board, legal_moves, None)
    if ordered:
        return ordered[0]
    # This line is normally unreachable because callers check for legal moves.
    return next(iter(board.legal_moves))
