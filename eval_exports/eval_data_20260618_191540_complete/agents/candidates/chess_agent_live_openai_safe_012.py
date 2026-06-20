"""Self-contained safe CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent performs no network access, no subprocess calls, no arbitrary file I/O,
and no dynamic code execution. Every returned move is validated with python-chess.
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
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 920,
    chess.KING: 0,
}

# Piece-square tables from White's perspective. Black uses mirrored squares.
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
    -10, 0, 10, 15, 15, 10, 0, -10,
    -10, 5, 5, 15, 15, 5, 5, -10,
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

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {chess.C3, chess.D3, chess.E3, chess.F3, chess.C4, chess.F4, chess.C5, chess.F5, chess.C6, chess.D6, chess.E6, chess.F6}


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

    # Fast tactical win: never spend search time if mate in one is available.
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return _format_move(board, mv, output_format)

    chosen = _search_best_move(board, time_limit_ms)
    if chosen not in legal_moves:
        chosen = _safe_fallback(board, legal_moves)
    return _format_move(board, chosen, output_format)


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

    board = chess.Board()
    if isinstance(observation, dict):
        history = observation.get("moves") or observation.get("move_history") or observation.get("history") or []
        if isinstance(history, list):
            for item in history:
                token = ""
                if isinstance(item, str):
                    token = item.strip()
                elif isinstance(item, dict):
                    raw = item.get("move") or item.get("uci") or item.get("san")
                    token = str(raw).strip() if raw is not None else ""
                if not token:
                    continue
                try:
                    mv = chess.Move.from_uci(token)
                    if mv in board.legal_moves:
                        board.push(mv)
                        continue
                except ValueError:
                    pass
                try:
                    board.push_san(token)
                except ValueError:
                    break
    return board


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(mv)
        except Exception:
            return mv.uci()
    return mv.uci()


def _search_best_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    legal_moves = list(board.legal_moves)
    fallback = _safe_fallback(board, legal_moves)
    if len(legal_moves) == 1:
        return fallback

    # Conservative budget leaves room for host overhead and Python scheduling jitter.
    requested = max(10, int(time_limit_ms or 100))
    budget = min(max(requested * 0.72, 6.0), 120.0) / 1000.0
    deadline = time.perf_counter() + budget

    state = {"nodes": 0, "deadline": deadline, "stop": False}
    best_move = fallback
    best_score = -INF
    max_depth = 4 if requested >= 75 else 3
    if requested >= 140:
        max_depth = 5
    if requested <= 25:
        max_depth = 2

    ordered = _ordered_moves(board, legal_moves)
    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        for mv in ordered:
            if time.perf_counter() >= deadline:
                state["stop"] = True
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -INF, -alpha, state)
            board.pop()
            if state["stop"]:
                break
            if score > current_score or (score == current_score and _move_tiebreak(board, mv) > _move_tiebreak(board, current_best)):
                current_score = score
                current_best = mv
            alpha = max(alpha, score)
        if not state["stop"]:
            best_move = current_best
            best_score = current_score
            ordered = [best_move] + [mv for mv in ordered if mv != best_move]
            if best_score > MATE_SCORE - 1000:
                break
        else:
            break
    return best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, state: dict[str, Any]) -> int:
    state["nodes"] += 1
    if state["nodes"] & 255 == 0 and time.perf_counter() >= state["deadline"]:
        state["stop"] = True
        return _evaluate(board)

    if board.is_checkmate():
        return -MATE_SCORE + board.ply()
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, state)

    best = -INF
    moves = _ordered_moves(board, list(board.legal_moves))
    for mv in moves:
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, state)
        board.pop()
        if state["stop"]:
            return score
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(board: chess.Board, alpha: int, beta: int, state: dict[str, Any]) -> int:
    stand_pat = _evaluate(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat
    if state["nodes"] & 255 == 0 and time.perf_counter() >= state["deadline"]:
        state["stop"] = True
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            tactical.append(mv)
    for mv in _ordered_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, state)
        board.pop()
        if state["stop"]:
            return alpha
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate(board: chess.Board) -> int:
    """Return score from side-to-move perspective."""
    if board.is_checkmate():
        return -MATE_SCORE + board.ply()
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    non_pawn_material = 0
    for color in (chess.WHITE, chess.BLACK):
        sign = 1 if color == chess.WHITE else -1
        bishops = 0
        pawns_by_file = [0] * 8
        for square, piece in board.piece_map().items():
            if piece.color != color:
                continue
            ptype = piece.piece_type
            value = PIECE_VALUES[ptype]
            if ptype != chess.PAWN:
                non_pawn_material += value
            idx = square if color == chess.WHITE else chess.square_mirror(square)
            if ptype == chess.KING:
                pst = KING_END_PST[idx] if non_pawn_material < 2400 else KING_MID_PST[idx]
            else:
                pst = PSTS[ptype][idx]
            score += sign * (value + pst)
            if ptype == chess.BISHOP:
                bishops += 1
            elif ptype == chess.PAWN:
                pawns_by_file[chess.square_file(square)] += 1
                rank = chess.square_rank(square) if color == chess.WHITE else 7 - chess.square_rank(square)
                if rank >= 4:
                    score += sign * (8 * (rank - 3))
        if bishops >= 2:
            score += sign * 35
        for count in pawns_by_file:
            if count > 1:
                score -= sign * 12 * (count - 1)

    # Lightweight mobility and center control.
    turn = board.turn
    own_mobility = board.legal_moves.count()
    board.turn = not turn
    try:
        opp_mobility = board.legal_moves.count()
    finally:
        board.turn = turn
    score += (1 if turn == chess.WHITE else -1) * (2 * (own_mobility - opp_mobility))

    for sq in CENTER_SQUARES:
        attackers_w = len(board.attackers(chess.WHITE, sq))
        attackers_b = len(board.attackers(chess.BLACK, sq))
        score += 5 * (attackers_w - attackers_b)
    for sq in EXTENDED_CENTER:
        attackers_w = len(board.attackers(chess.WHITE, sq))
        attackers_b = len(board.attackers(chess.BLACK, sq))
        score += 2 * (attackers_w - attackers_b)

    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 10
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 10
    if board.is_check():
        score -= 25

    return score if board.turn == chess.WHITE else -score


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_tiebreak(board, mv), reverse=True)


def _move_tiebreak(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        attacker = board.piece_at(mv.from_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 1) if attacker else 1
        score += 10000 + 10 * victim_value - attacker_value
    if mv.promotion:
        score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.gives_check(mv):
        score += 2500
    if mv.to_square in CENTER_SQUARES:
        score += 120
    elif mv.to_square in EXTENDED_CENTER:
        score += 50
    piece = board.piece_at(mv.from_square)
    if piece:
        score += PIECE_VALUES[piece.piece_type] // 20
    # Deterministic final tie-break, independent of set/list ordering.
    score += 63 - mv.from_square
    score += mv.to_square // 2
    return score


def _safe_fallback(board: chess.Board, legal_moves: list[chess.Move] | None = None) -> chess.Move:
    moves = legal_moves if legal_moves is not None else list(board.legal_moves)
    if not moves:
        return chess.Move.null()
    return _ordered_moves(board, moves)[0]
