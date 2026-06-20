"""Self-contained safe CATArena chess agent.

Public entry point:
    select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation is intentionally local-only: no network calls, no subprocesses,
no file I/O, no dynamic imports, and every returned move is validated against
python-chess legal moves.
"""

from __future__ import annotations

import json
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

# Compact piece-square tables from White's perspective. Black uses mirrored squares.
PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    45, 50, 50, 55, 55, 50, 50, 45,
    18, 20, 25, 35, 35, 25, 20, 18,
    8, 10, 15, 28, 28, 15, 10, 8,
    0, 2, 8, 22, 22, 8, 2, 0,
    4, -4, -8, 8, 8, -8, -4, 4,
    4, 8, 8, -18, -18, 8, 8, 4,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_TABLE = [
    -55, -35, -25, -20, -20, -25, -35, -55,
    -35, -15, 0, 5, 5, 0, -15, -35,
    -25, 5, 15, 20, 20, 15, 5, -25,
    -20, 8, 22, 30, 30, 22, 8, -20,
    -20, 5, 22, 28, 28, 22, 5, -20,
    -25, 0, 15, 20, 20, 15, 0, -25,
    -35, -15, 0, 0, 0, 0, -15, -35,
    -55, -35, -25, -20, -20, -25, -35, -55,
]
BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 12, 12, 10, 10, -10,
    -10, 0, 14, 16, 16, 14, 0, -10,
    -10, 5, 12, 16, 16, 12, 5, -10,
    -10, 8, 8, 10, 10, 8, 8, -10,
    -10, 6, 0, 0, 0, 0, 6, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_TABLE = [
    0, 0, 4, 8, 8, 4, 0, 0,
    8, 12, 12, 14, 14, 12, 12, 8,
    -4, 0, 2, 4, 4, 2, 0, -4,
    -4, 0, 2, 4, 4, 2, 0, -4,
    -4, 0, 2, 4, 4, 2, 0, -4,
    -4, 0, 2, 4, 4, 2, 0, -4,
    -4, 0, 2, 4, 4, 2, 0, -4,
    0, 0, 4, 8, 8, 4, 0, 0,
]
QUEEN_TABLE = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 4, 0, 0, 0, 0, -10,
    -10, 4, 6, 6, 6, 6, 0, -10,
    -5, 0, 6, 8, 8, 6, 0, -5,
    0, 0, 6, 8, 8, 6, 0, -5,
    -10, 6, 6, 6, 6, 6, 0, -10,
    -10, 0, 6, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_MID_TABLE = [
    22, 28, 10, 0, 0, 10, 30, 22,
    20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -25, -25, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
]
KING_END_TABLE = [
    -50, -30, -20, -10, -10, -20, -30, -50,
    -30, -10, 10, 20, 20, 10, -10, -30,
    -20, 10, 25, 35, 35, 25, 10, -20,
    -10, 20, 35, 45, 45, 35, 20, -10,
    -10, 20, 35, 45, 45, 35, 20, -10,
    -20, 10, 25, 35, 35, 25, 10, -20,
    -30, -10, 10, 20, 20, 10, -10, -30,
    -50, -30, -20, -10, -10, -20, -30, -50,
]

PST = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
}


@dataclass
class SearchState:
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

    chosen = _choose_move(board, time_limit_ms)
    if chosen not in legal_moves:
        chosen = _fallback_move(board)
    if chosen not in legal_moves:
        return ""

    fmt = str(output_format or "uci").lower().strip()
    if fmt in {"san", "algebraic"}:
        return board.san(chosen)
    return chosen.uci()


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    """Parse common CATArena observation shapes without unsafe evaluation."""
    fen = ""
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
        if text.startswith("{") and text.endswith("}"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                value = payload.get("fen") or payload.get("board") or payload.get("state")
                if isinstance(value, str):
                    fen = value.strip()
        else:
            fen = text

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _choose_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    mate = _find_immediate_mate(board)
    if mate is not None:
        return mate

    book = _book_move(board)
    if book is not None and book in legal_moves:
        return book

    budget_ms = max(8, min(int(time_limit_ms), 500))
    deadline = time.monotonic() + max(0.004, (budget_ms - 3) / 1000.0)
    node_limit = max(500, min(35000, budget_ms * 110))
    state = SearchState(deadline=deadline, node_limit=node_limit)

    max_depth = 2
    if budget_ms >= 45:
        max_depth = 3
    if budget_ms >= 180:
        max_depth = 4

    best_move = _fallback_move(board)
    best_score = -INF

    ordered = _ordered_moves(board, legal_moves)
    for depth in range(1, max_depth + 1):
        if _time_up(state):
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        for mv in ordered:
            if _time_up(state):
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -INF, -alpha, state, 1)
            board.pop()
            if state.stopped:
                break
            if score > current_score:
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score
        if not state.stopped and current_best in legal_moves:
            best_move = current_best
            best_score = current_score
            ordered = [best_move] + [mv for mv in ordered if mv != best_move]
        if best_score > MATE_SCORE - 1000:
            break

    return best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, state: SearchState, ply: int) -> int:
    if _time_up(state):
        state.stopped = True
        return 0
    state.nodes += 1

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, state, ply)

    best = -INF
    moves = _ordered_moves(board, list(board.legal_moves))
    for mv in moves:
        board.push(mv)
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
    if _time_up(state):
        state.stopped = True
        return 0
    state.nodes += 1

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    stand_pat = _static_score(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    if board.is_check():
        candidates = list(board.legal_moves)
    else:
        candidates = [mv for mv in board.legal_moves if board.is_capture(mv) or mv.promotion]
    candidates = _ordered_moves(board, candidates)

    for mv in candidates[:18]:
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, state, ply + 1)
        board.pop()
        if state.stopped:
            return 0
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _static_score(board: chess.Board) -> int:
    material = 0
    phase_material = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        if piece.piece_type != chess.KING:
            phase_material += value
        table_bonus = _piece_square(piece, square, phase_material)
        signed = value + table_bonus
        material += signed if piece.color == chess.WHITE else -signed

    # Small mobility and king-safety terms; cheap and deterministic.
    turn = board.turn
    own_mobility = board.legal_moves.count()
    board.turn = not turn
    try:
        opp_mobility = board.legal_moves.count()
    finally:
        board.turn = turn
    material += 2 * (own_mobility - opp_mobility) * (1 if turn == chess.WHITE else -1)

    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        material += 8
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        material -= 8

    return material if board.turn == chess.WHITE else -material


def _piece_square(piece: chess.Piece, square: chess.Square, phase_material: int) -> int:
    idx = square if piece.color == chess.WHITE else chess.square_mirror(square)
    if piece.piece_type == chess.KING:
        table = KING_END_TABLE if phase_material < 1800 else KING_MID_TABLE
        return table[idx]
    table = PST.get(piece.piece_type)
    if table is None:
        return 0
    return table[idx]


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_at(mv.from_square)
    if mv.promotion:
        score += 7000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0
        score += 10000 + 10 * victim_value - attacker_value
    if board.gives_check(mv):
        score += 1200
    if board.is_castling(mv):
        score += 450
    file_idx = chess.square_file(mv.to_square)
    rank_idx = chess.square_rank(mv.to_square)
    if 2 <= file_idx <= 5 and 2 <= rank_idx <= 5:
        score += 80
    if moving_piece and moving_piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        home_rank = 0 if moving_piece.color == chess.WHITE else 7
        if chess.square_rank(mv.from_square) == home_rank:
            score += 120
    return score


def _find_immediate_mate(board: chess.Board) -> chess.Move | None:
    for mv in _ordered_moves(board, list(board.legal_moves)):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _fallback_move(board: chess.Board) -> chess.Move:
    legal = list(board.legal_moves)
    if not legal:
        return chess.Move.null()
    return _ordered_moves(board, legal)[0]


def _time_up(state: SearchState) -> bool:
    return state.nodes >= state.node_limit or time.monotonic() >= state.deadline


def _book_move(board: chess.Board) -> chess.Move | None:
    """Tiny deterministic book for common starts; every candidate is still legal-checked."""
    if board.fullmove_number > 6:
        return None
    board_key = board.board_fen()
    turn = "w" if board.turn == chess.WHITE else "b"
    key = board_key + " " + turn
    book = {
        chess.Board().board_fen() + " w": ["e2e4", "d2d4", "g1f3", "c2c4"],
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b": ["c7c5", "e7e5", "e7e6", "c7c6"],
        "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b": ["g8f6", "d7d5", "c7c5"],
        "rnbqkb1r/pppppppp/5n2/8/3P4/8/PPP1PPPP/RNBQKBNR w": ["c2c4", "g1f3"],
        "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w": ["g1f3", "d2d4"],
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w": ["g1f3", "f1c4", "b1c3"],
    }
    for uci in book.get(key, []):
        mv = chess.Move.from_uci(uci)
        if mv in board.legal_moves:
            return mv
    return None
