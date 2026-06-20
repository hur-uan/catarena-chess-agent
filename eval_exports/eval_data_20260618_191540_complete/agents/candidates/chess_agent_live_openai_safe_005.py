"""Self-contained safe CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation intentionally avoids network calls, subprocesses, file I/O,
eval/exec, and dynamic imports.  It relies only on python-chess, which is already
part of the chess arena environment.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import chess

MATE_SCORE = 100000
INF = 10**9
DEFAULT_TIME_MS = 100
MIN_TIME_MS = 8

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Simple piece-square tables from White's perspective.  Black uses mirrored
# squares.  Values are intentionally modest so tactics dominate.
PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    45, 45, 45, 35, 35, 45, 45, 45,
    12, 12, 20, 28, 28, 20, 12, 12,
    5, 5, 12, 24, 24, 12, 5, 5,
    0, 0, 5, 18, 18, 5, 0, 0,
    5, -5, -8, 0, 0, -8, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_PST = [
    -45, -25, -15, -10, -10, -15, -25, -45,
    -25, -5, 5, 8, 8, 5, -5, -25,
    -15, 8, 18, 24, 24, 18, 8, -15,
    -10, 10, 24, 32, 32, 24, 10, -10,
    -10, 8, 24, 32, 32, 24, 8, -10,
    -15, 5, 18, 22, 22, 18, 5, -15,
    -25, -5, 5, 8, 8, 5, -5, -25,
    -45, -25, -15, -10, -10, -15, -25, -45,
]
BISHOP_PST = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 8, 0, 0, 0, 0, 8, -10,
    -10, 10, 12, 12, 12, 12, 10, -10,
    -10, 0, 12, 16, 16, 12, 0, -10,
    -10, 5, 8, 16, 16, 8, 5, -10,
    -10, 0, 8, 12, 12, 8, 0, -10,
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


@dataclass
class SearchState:
    deadline: float
    nodes: int = 0
    node_limit: int = 18000
    stopped: bool = False

    def should_stop(self) -> bool:
        if self.stopped:
            return True
        self.nodes += 1
        if self.nodes >= self.node_limit or time.perf_counter() >= self.deadline:
            self.stopped = True
            return True
        return False


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = DEFAULT_TIME_MS) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(observation: Any, output_format: str = "uci", time_limit_ms: int = DEFAULT_TIME_MS) -> str:
    """Choose a legal chess move for the supplied observation."""
    try:
        board = _parse_observation(observation)
        if board.is_game_over(claim_draw=False):
            return ""
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return ""
        chosen = _choose_move(board, observation, time_limit_ms)
        if chosen not in legal_moves:
            chosen = _fallback_move(board, legal_moves)
        return _format_move(board, chosen, output_format)
    except Exception:
        # Last-resort safety path.  It still validates via python-chess on either
        # the parsed observation or the initial board.
        try:
            board = _parse_observation(observation)
        except Exception:
            board = chess.Board()
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return ""
        return legal_moves[0].uci()


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
        for key in ("fen", "board", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        if fen is None:
            nested = observation.get("observation") or observation.get("state")
            if isinstance(nested, dict):
                value = nested.get("fen")
                if isinstance(value, str) and value.strip():
                    fen = value.strip()
    elif isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text
    if fen:
        return chess.Board(fen)
    return chess.Board()


def _extract_legal_hints(observation: Any) -> set[str]:
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


def _format_move(board: chess.Board, selected: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").lower().strip()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(selected)
        except Exception:
            return selected.uci()
    return selected.uci()


def _choose_move(board: chess.Board, observation: Any, time_limit_ms: int) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    hinted = _extract_legal_hints(observation)
    hinted_legal = [mv for mv in legal_moves if mv.uci() in hinted]
    if hinted and hinted_legal:
        legal_moves = hinted_legal

    # Immediate mate is exact and cheap.
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv

    budget_ms = max(MIN_TIME_MS, int(time_limit_ms or DEFAULT_TIME_MS))
    safety_fraction = 0.82 if budget_ms <= 120 else 0.88
    deadline = time.perf_counter() + (budget_ms / 1000.0) * safety_fraction
    node_limit = 3500 if budget_ms <= 40 else 9000 if budget_ms <= 120 else 18000
    state = SearchState(deadline=deadline, node_limit=node_limit)

    max_depth = 2 if budget_ms <= 35 else 3 if budget_ms <= 130 else 4
    # In low branching tactical positions, depth 4 is often affordable even at
    # 100 ms; cap keeps runtime predictable.
    if len(legal_moves) <= 18 and budget_ms >= 80:
        max_depth = min(4, max_depth + 1)

    best_move = _fallback_move(board, legal_moves)
    best_score = -INF
    ordered_root = _ordered_moves(board, legal_moves)

    for depth in range(1, max_depth + 1):
        if state.should_stop():
            break
        depth_best = best_move
        depth_score = -INF
        alpha = -INF
        completed = True
        for mv in ordered_root:
            if state.should_stop():
                completed = False
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -INF, -alpha, state, 1)
            board.pop()
            if state.stopped:
                completed = False
                break
            if score > depth_score or (score == depth_score and _move_order_score(board, mv) > _move_order_score(board, depth_best)):
                depth_score = score
                depth_best = mv
            if score > alpha:
                alpha = score
        if completed:
            best_move = depth_best
            best_score = depth_score
            ordered_root = [best_move] + [mv for mv in ordered_root if mv != best_move]
        else:
            break

    if best_score <= -MATE_SCORE + 20:
        return _fallback_move(board, legal_moves)
    return best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, state: SearchState, ply: int) -> int:
    if state.should_stop():
        return _static_eval_side_to_move(board)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, state, ply)

    value = -INF
    legal = list(board.legal_moves)
    if not legal:
        return _static_eval_side_to_move(board)

    for mv in _ordered_moves(board, legal):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, state, ply + 1)
        board.pop()
        if state.stopped:
            return score
        if score > value:
            value = score
        if value > alpha:
            alpha = value
        if alpha >= beta:
            break
    return value


def _quiescence(board: chess.Board, alpha: int, beta: int, state: SearchState, ply: int) -> int:
    if state.should_stop():
        return _static_eval_side_to_move(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _static_eval_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    if board.is_check():
        candidate_moves = list(board.legal_moves)
    else:
        candidate_moves = [mv for mv in board.legal_moves if board.is_capture(mv) or mv.promotion]

    # Bound quiescence width to keep runtime stable in capture-heavy positions.
    ordered = _ordered_moves(board, candidate_moves)[:14]
    for mv in ordered:
        if not board.is_check() and not _is_tactically_relevant(board, mv):
            continue
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, state, ply + 1)
        board.pop()
        if state.stopped:
            return score
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
        score += 9000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.is_capture(mv):
        victim_value = 0
        if board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim = board.piece_at(mv.to_square)
            if victim is not None:
                victim_value = PIECE_VALUES.get(victim.piece_type, 0)
        attacker = board.piece_at(mv.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 7000 + 10 * victim_value - attacker_value
    if board.gives_check(mv):
        score += 3500
    piece = board.piece_at(mv.from_square)
    if piece is not None:
        # Prefer developing minor pieces and central moves when tactics are tied.
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            score += 70
        file_index = chess.square_file(mv.to_square)
        rank_index = chess.square_rank(mv.to_square)
        center_distance = abs(file_index - 3.5) + abs(rank_index - 3.5)
        score += int(28 - 4 * center_distance)
        if piece.piece_type == chess.KING and board.is_castling(mv):
            score += 500
    return score


def _is_tactically_relevant(board: chess.Board, mv: chess.Move) -> bool:
    if mv.promotion or board.gives_check(mv):
        return True
    if not board.is_capture(mv):
        return False
    attacker = board.piece_at(mv.from_square)
    if attacker is None:
        return True
    if board.is_en_passant(mv):
        victim_value = PIECE_VALUES[chess.PAWN]
    else:
        victim = board.piece_at(mv.to_square)
        victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
    return victim_value + 60 >= PIECE_VALUES.get(attacker.piece_type, 0)


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    # Deterministic safe fallback: mate, then check, then best ordered move.
    for mv in legal_moves:
        board.push(mv)
        mate = board.is_checkmate()
        board.pop()
        if mate:
            return mv
    checks = [mv for mv in legal_moves if board.gives_check(mv)]
    if checks:
        return _ordered_moves(board, checks)[0]
    return _ordered_moves(board, legal_moves)[0]


def _static_eval_side_to_move(board: chess.Board) -> int:
    value = _evaluate_white_perspective(board)
    return value if board.turn == chess.WHITE else -value


def _evaluate_white_perspective(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    non_pawn_material = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        non_pawn_material += len(board.pieces(piece_type, chess.WHITE)) * PIECE_VALUES[piece_type]
        non_pawn_material += len(board.pieces(piece_type, chess.BLACK)) * PIECE_VALUES[piece_type]
    endgame = non_pawn_material <= 2400

    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        base = PIECE_VALUES.get(piece.piece_type, 0)
        if piece.piece_type == chess.KING:
            table = KING_END_PST if endgame else KING_MID_PST
        else:
            table = PSTS.get(piece.piece_type)
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        pst = table[pst_square] if table is not None else 0
        score += sign * (base + pst)

    # Bishop pair and light mobility terms.
    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        score += 35
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        score -= 35

    turn = board.turn
    board.turn = chess.WHITE
    try:
        white_mobility = board.legal_moves.count()
    finally:
        board.turn = turn
    board.turn = chess.BLACK
    try:
        black_mobility = board.legal_moves.count()
    finally:
        board.turn = turn
    score += 2 * (white_mobility - black_mobility)

    # Penalize currently checked side a little; mate is handled separately.
    if board.is_check():
        score += -45 if board.turn == chess.WHITE else 45

    # Passed pawns and advanced pawns matter in simplified positions.
    score += _passed_pawn_score(board, chess.WHITE)
    score -= _passed_pawn_score(board, chess.BLACK)

    return int(score)


def _passed_pawn_score(board: chess.Board, color: chess.Color) -> int:
    total = 0
    enemy = not color
    for sq in board.pieces(chess.PAWN, color):
        file_index = chess.square_file(sq)
        rank_index = chess.square_rank(sq)
        blocked = False
        for adjacent_file in (file_index - 1, file_index, file_index + 1):
            if adjacent_file < 0 or adjacent_file > 7:
                continue
            for rank in range(8):
                target = chess.square(adjacent_file, rank)
                pawn = board.piece_at(target)
                if pawn is None or pawn.color != enemy or pawn.piece_type != chess.PAWN:
                    continue
                if color == chess.WHITE and rank > rank_index:
                    blocked = True
                if color == chess.BLACK and rank < rank_index:
                    blocked = True
        if not blocked:
            advance = rank_index if color == chess.WHITE else 7 - rank_index
            total += 12 + advance * advance * 3
    return total
