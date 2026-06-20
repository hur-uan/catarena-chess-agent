"""Safe self-contained CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation is deterministic, uses python-chess legal move validation for every
returned move, performs no network/file/subprocess operations, and keeps search bounded.
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
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Piece-square tables from White's point of view. They are intentionally modest:
# material and tactics dominate, tables only guide quiet choices.
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

OPENING_PREFERENCES = (
    "e2e4", "d2d4", "g1f3", "c2c4", "e7e5", "d7d5", "g8f6", "c7c5",
    "b1c3", "f1c4", "f1b5", "c1g5", "b8c6", "f8c5", "f8b4", "c8g4",
)


@dataclass
class SearchInfo:
    move: str
    score: int
    depth: int
    elapsed_ms: float
    legal_moves: list[str]
    fallback_used: bool = False


class TimeoutSearch(Exception):
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
    board = parse_observation(observation)
    try:
        info = _select_move_info(board, max(1, int(time_limit_ms)))
        move_obj = chess.Move.from_uci(info.move) if info.move else None
        if move_obj not in board.legal_moves:
            move_obj = _fallback_move(board)
    except Exception:
        move_obj = _fallback_move(board)

    if move_obj is None:
        return ""
    if str(output_format).lower().strip() == "san":
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def select_move_details(observation: Any, output_format: str = "uci", time_limit_ms: int = 100) -> SearchInfo:
    """Return lightweight diagnostics while preserving legal move safety."""
    board = parse_observation(observation)
    start = time.perf_counter()
    info = _select_move_info(board, max(1, int(time_limit_ms)))
    if output_format.lower().strip() == "san" and info.move:
        move_obj = chess.Move.from_uci(info.move)
        if move_obj in board.legal_moves:
            info.move = board.san(move_obj)
    info.elapsed_ms = (time.perf_counter() - start) * 1000.0
    return info


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def parse_observation(observation: Any) -> chess.Board:
    """Parse common CATArena observations without external dependencies."""
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        moves_value = observation.get("moves") or observation.get("move_history")
        if fen is None and isinstance(observation.get("state"), dict):
            state = observation["state"]
            value = state.get("fen") or state.get("board")
            if isinstance(value, str) and value.strip():
                fen = value.strip()
        if fen is None and isinstance(moves_value, list):
            board = chess.Board()
            for item in moves_value:
                try:
                    mv = chess.Move.from_uci(str(item).strip())
                    if mv in board.legal_moves:
                        board.push(mv)
                    else:
                        break
                except Exception:
                    break
            return board
    elif isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text

    if fen:
        try:
            return chess.Board(fen)
        except Exception:
            pass
    return chess.Board()


def _select_move_info(board: chess.Board, time_limit_ms: int) -> SearchInfo:
    legal = list(board.legal_moves)
    legal_uci = [m.uci() for m in legal]
    if not legal or board.is_game_over(claim_draw=False):
        return SearchInfo("", 0, 0, 0.0, legal_uci, fallback_used=True)

    start = time.perf_counter()
    # Leave a small safety margin for arena overhead and Python scheduling.
    budget = min(max(time_limit_ms, 1), 250)
    deadline = start + max(0.003, (budget * 0.82) / 1000.0)

    immediate = _mate_in_one(board)
    if immediate is not None:
        return SearchInfo(immediate.uci(), MATE_SCORE, 1, (time.perf_counter() - start) * 1000.0, legal_uci)

    opening = _opening_move(board)
    if opening is not None and board.fullmove_number <= 5:
        return SearchInfo(opening.uci(), 20, 1, (time.perf_counter() - start) * 1000.0, legal_uci)

    fallback = _fallback_move(board)
    best_move = fallback
    best_score = -INF
    completed_depth = 0

    max_depth = _depth_for_budget(board, budget)
    try:
        for depth in range(1, max_depth + 1):
            _check_time(deadline)
            score, candidate = _root_search(board, depth, deadline)
            if candidate is not None and candidate in board.legal_moves:
                best_move = candidate
                best_score = score
                completed_depth = depth
    except TimeoutSearch:
        pass
    except Exception:
        best_move = fallback

    if best_move not in board.legal_moves:
        best_move = fallback
    return SearchInfo(
        best_move.uci() if best_move is not None else "",
        int(best_score if best_score > -INF else 0),
        completed_depth,
        (time.perf_counter() - start) * 1000.0,
        legal_uci,
        fallback_used=completed_depth == 0,
    )


def _depth_for_budget(board: chess.Board, budget_ms: int) -> int:
    legal_count = board.legal_moves.count()
    pieces = len(board.piece_map())
    if budget_ms < 25:
        return 2
    if budget_ms < 70:
        return 3
    if pieces <= 12 and legal_count <= 30:
        return 5
    if pieces <= 22 and budget_ms >= 120:
        return 4
    return 3


def _root_search(board: chess.Board, depth: int, deadline: float) -> tuple[int, chess.Move | None]:
    alpha = -INF
    beta = INF
    best_score = -INF
    best_move = None
    for mv in _ordered_moves(board):
        _check_time(deadline)
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, 1)
        board.pop()
        if score > best_score or best_move is None:
            best_score = score
            best_move = mv
        if score > alpha:
            alpha = score
    return best_score, best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, deadline: float, ply: int) -> int:
    _check_time(deadline)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    best = -INF
    for mv in _ordered_moves(board):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(board: chess.Board, alpha: int, beta: int, deadline: float, ply: int) -> int:
    _check_time(deadline)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    noisy = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            noisy.append(mv)
    noisy.sort(key=lambda m: _move_order_score(board, m), reverse=True)

    # Hard cap prevents pathological checking/capture explosions.
    for mv in noisy[:16]:
        _check_time(deadline)
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    score = _evaluate_white(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    score = 0
    material_without_pawns = 0
    bishop_counts = {chess.WHITE: 0, chess.BLACK: 0}

    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        value = PIECE_VALUES[piece.piece_type]
        if piece.piece_type != chess.PAWN:
            material_without_pawns += value
        if piece.piece_type == chess.BISHOP:
            bishop_counts[piece.color] += 1
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        if piece.piece_type == chess.KING:
            table = KING_END_PST if material_without_pawns <= 2400 else KING_MID_PST
            pst = table[pst_square]
        else:
            pst = PSTS[piece.piece_type][pst_square]
        score += sign * (value + pst)

    if bishop_counts[chess.WHITE] >= 2:
        score += 35
    if bishop_counts[chess.BLACK] >= 2:
        score -= 35

    # Small mobility term; temporarily count pseudo-legal mobility for both sides.
    turn = board.turn
    try:
        board.turn = chess.WHITE
        white_mob = board.legal_moves.count() if not board.is_checkmate() else 0
        board.turn = chess.BLACK
        black_mob = board.legal_moves.count() if not board.is_checkmate() else 0
    finally:
        board.turn = turn
    score += 2 * (white_mob - black_mob)

    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 8
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 8
    return score


def _ordered_moves(board: chess.Board) -> list[chess.Move]:
    moves = list(board.legal_moves)
    moves.sort(key=lambda m: _move_order_score(board, m), reverse=True)
    return moves


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if mv.promotion:
        score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(mv.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 1) if attacker else 1
        score += 5000 + 10 * victim_value - attacker_value
    try:
        if board.gives_check(mv):
            score += 3000
    except Exception:
        pass
    if board.is_castling(mv):
        score += 500
    file_to = chess.square_file(mv.to_square)
    rank_to = chess.square_rank(mv.to_square)
    if file_to in (3, 4) and rank_to in (3, 4):
        score += 80
    piece = board.piece_at(mv.from_square)
    if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 10:
        home_rank = 0 if piece.color == chess.WHITE else 7
        if chess.square_rank(mv.from_square) == home_rank:
            score += 60
    return score


def _mate_in_one(board: chess.Board) -> chess.Move | None:
    for mv in _ordered_moves(board):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _opening_move(board: chess.Board) -> chess.Move | None:
    legal = set(board.legal_moves)
    for uci in OPENING_PREFERENCES:
        mv = chess.Move.from_uci(uci)
        if mv in legal:
            return mv
    return None


def _fallback_move(board: chess.Board) -> chess.Move | None:
    legal = list(board.legal_moves)
    if not legal:
        return None
    legal.sort(key=lambda m: _move_order_score(board, m), reverse=True)
    # Prefer a non-losing legal move if a cheap one-ply safety check is available.
    best = legal[0]
    best_score = -INF
    for mv in legal[:12]:
        board.push(mv)
        if board.is_checkmate():
            score = MATE_SCORE
        else:
            score = -_evaluate_for_side_to_move(board)
            # Penalize moving onto an attacked destination for non-capturing king moves.
            piece = board.piece_at(mv.to_square)
            if piece and piece.piece_type == chess.KING and board.is_attacked_by(board.turn, mv.to_square):
                score -= 10000
        board.pop()
        if score > best_score:
            best_score = score
            best = mv
    return best


def _check_time(deadline: float) -> None:
    if time.perf_counter() >= deadline:
        raise TimeoutSearch
