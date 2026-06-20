"""Safe self-contained CATArena chess agent.

Public entry point:
    select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation is intentionally deterministic, bounded, and match-safe:
- no network access
- no subprocess usage
- no arbitrary file I/O
- no eval/exec/dynamic imports
- every returned move is validated with python-chess legal_moves
"""

from __future__ import annotations

import json
import time
from typing import Any

import chess


MATE_SCORE = 100000
INF = 100000000

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Piece-square tables are from White's perspective. Black uses mirrored squares.
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
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


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

    requested_ms = _safe_int(time_limit_ms, 100)
    budget_ms = max(5, min(250, requested_ms))
    deadline = time.perf_counter() + max(0.002, (budget_ms - 3) / 1000.0)

    hinted = _extract_legal_hint_moves(observation, board)
    opening = _opening_book_move(board, hinted)
    if opening is not None:
        return _format_move(board, opening, output_format)

    mate_move = _find_immediate_mate(board)
    if mate_move is not None:
        return _format_move(board, mate_move, output_format)

    best = _search_best_move(board, legal_moves, hinted, deadline, budget_ms)
    if best not in legal_moves:
        best = _fallback_move(board, hinted)
    if best not in legal_moves:
        best = legal_moves[0]
    return _format_move(board, best, output_format)


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
            if isinstance(value, str):
                board = _board_from_string(value)
                if board is not None:
                    return board
        nested = observation.get("observation")
        if nested is not None and nested is not observation:
            return _parse_observation(nested)

    if isinstance(observation, str):
        text = observation.strip()
        if text:
            if text.startswith("{") and text.endswith("}"):
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    payload = None
                if payload is not None:
                    return _parse_observation(payload)
            board = _board_from_string(text)
            if board is not None:
                return board

    return chess.Board()


def _board_from_string(text: str) -> chess.Board | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    try:
        return chess.Board(cleaned)
    except ValueError:
        pass
    # Some servers send only the board part; assume default side/castling fields only if usable.
    if "/" in cleaned and " " not in cleaned:
        try:
            return chess.Board(cleaned + " w KQkq - 0 1")
        except ValueError:
            return None
    return None


def _extract_legal_hint_moves(observation: Any, board: chess.Board) -> list[chess.Move]:
    raw_items: list[Any] = []
    if isinstance(observation, dict):
        for key in ("legal_moves", "legalMoves", "moves", "valid_moves", "validMoves"):
            value = observation.get(key)
            if isinstance(value, (list, tuple, set)):
                raw_items.extend(value)
    legal = set(board.legal_moves)
    hinted: list[chess.Move] = []
    seen: set[chess.Move] = set()
    for item in raw_items:
        try:
            mv = chess.Move.from_uci(str(item).strip())
        except ValueError:
            continue
        if mv in legal and mv not in seen:
            hinted.append(mv)
            seen.add(mv)
    return hinted


def _opening_book_move(board: chess.Board, hinted: list[chess.Move]) -> chess.Move | None:
    # Tiny deterministic book for reliability and speed. All moves are validated before use.
    book = {
        chess.STARTING_FEN: ["e2e4", "d2d4", "g1f3", "c2c4"],
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1": ["c7c5", "e7e5", "e7e6"],
        "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1": ["g8f6", "d7d5", "e7e6"],
        "rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR b KQkq - 0 1": ["e7e5", "g8f6", "c7c5"],
        "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq - 1 1": ["d7d5", "g8f6", "c7c5"],
    }
    candidates = book.get(board.fen())
    if not candidates:
        return None
    legal = set(board.legal_moves)
    hint_set = set(hinted)
    for uci in candidates:
        mv = chess.Move.from_uci(uci)
        if mv in legal and (not hint_set or mv in hint_set):
            return mv
    return None


def _find_immediate_mate(board: chess.Board) -> chess.Move | None:
    for mv in _ordered_moves(board, list(board.legal_moves)):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _search_best_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
    hinted: list[chess.Move],
    deadline: float,
    budget_ms: int,
) -> chess.Move:
    best = _fallback_move(board, hinted)
    ordered = _ordered_moves(board, legal_moves)
    if hinted:
        hint_set = set(hinted)
        ordered.sort(key=lambda mv: 0 if mv in hint_set else 1)

    max_depth = 2
    if budget_ms >= 25:
        max_depth = 3
    if budget_ms >= 90 and len(legal_moves) <= 38:
        max_depth = 4
    if _non_king_material(board) <= 2200 and budget_ms >= 70:
        max_depth = max(max_depth, 4)
    if len(legal_moves) <= 8 and budget_ms >= 40:
        max_depth = max(max_depth, 4)

    last_complete = best
    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        try:
            score, move_at_depth = _root_search(board, ordered, depth, deadline)
        except TimeoutError:
            break
        if move_at_depth in legal_moves:
            last_complete = move_at_depth
            best = move_at_depth
        if score >= MATE_SCORE - 1000:
            break
    return last_complete if last_complete in legal_moves else best


def _root_search(
    board: chess.Board,
    moves: list[chess.Move],
    depth: int,
    deadline: float,
) -> tuple[int, chess.Move | None]:
    alpha = -INF
    beta = INF
    best_score = -INF
    best_move: chess.Move | None = None
    for mv in moves:
        if time.perf_counter() >= deadline:
            raise TimeoutError
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, 1)
        board.pop()
        if score > best_score:
            best_score = score
            best_move = mv
        if score > alpha:
            alpha = score
    return best_score, best_move


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    best = -INF
    moves = _ordered_moves(board, list(board.legal_moves))
    for mv in moves:
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > best:
            best = score
        if score > alpha:
            alpha = score
    return best


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError
    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    noisy = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            noisy.append(mv)
    for mv in _ordered_moves(board, noisy)[:18]:
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
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if mv.promotion:
        score += PIECE_VALUES.get(mv.promotion, 0) + 800
    if board.is_capture(mv):
        victim_type = board.piece_type_at(mv.to_square)
        if victim_type is None and board.is_en_passant(mv):
            victim_type = chess.PAWN
        attacker_type = board.piece_type_at(mv.from_square)
        score += 1000 + 10 * PIECE_VALUES.get(victim_type, 0) - PIECE_VALUES.get(attacker_type, 0)
    if board.gives_check(mv):
        score += 500
    if mv.to_square in CENTER_SQUARES:
        score += 50
    elif mv.to_square in EXTENDED_CENTER:
        score += 20
    if board.is_castling(mv):
        score += 80
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
    endgame = _non_king_material(board) <= 2400

    for color in (chess.WHITE, chess.BLACK):
        sign = 1 if color == chess.WHITE else -1
        bishop_count = 0
        for piece_type in chess.PIECE_TYPES:
            for sq in board.pieces(piece_type, color):
                if piece_type == chess.KING:
                    table = KING_END_PST if endgame else KING_MID_PST
                    pst_value = table[sq if color == chess.WHITE else chess.square_mirror(sq)]
                else:
                    pst_value = PST[piece_type][sq if color == chess.WHITE else chess.square_mirror(sq)]
                score += sign * (PIECE_VALUES[piece_type] + pst_value)
                if piece_type == chess.BISHOP:
                    bishop_count += 1
                if piece_type == chess.PAWN:
                    rank = chess.square_rank(sq) if color == chess.WHITE else 7 - chess.square_rank(sq)
                    score += sign * max(0, rank - 1) * 4
        if bishop_count >= 2:
            score += sign * 35

    # Mobility: small and cheap approximation.
    turn = board.turn
    try:
        board.turn = chess.WHITE
        white_mobility = board.legal_moves.count() if not board.is_checkmate() else 0
        board.turn = chess.BLACK
        black_mobility = board.legal_moves.count() if not board.is_checkmate() else 0
    finally:
        board.turn = turn
    score += 2 * (white_mobility - black_mobility)

    # Castling rights and king safety incentives.
    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 12
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 12
    if board.is_check():
        score += -25 if board.turn == chess.WHITE else 25

    return score


def _non_king_material(board: chess.Board) -> int:
    total = 0
    for piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += PIECE_VALUES[piece_type] * (len(board.pieces(piece_type, chess.WHITE)) + len(board.pieces(piece_type, chess.BLACK)))
    return total


def _fallback_move(board: chess.Board, hinted: list[chess.Move] | None = None) -> chess.Move:
    legal = list(board.legal_moves)
    if not legal:
        return chess.Move.null()
    hinted = hinted or []
    for mv in hinted:
        if mv in legal:
            return mv
    ordered = _ordered_moves(board, legal)
    return ordered[0] if ordered else legal[0]


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    if mv not in board.legal_moves:
        legal = list(board.legal_moves)
        if not legal:
            return ""
        mv = legal[0]
    fmt = (output_format or "uci").lower().strip()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(mv)
        except (ValueError, AssertionError):
            return mv.uci()
    return mv.uci()


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
