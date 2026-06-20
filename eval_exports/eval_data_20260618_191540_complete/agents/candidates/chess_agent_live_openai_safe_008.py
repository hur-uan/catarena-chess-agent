"""Self-contained safe CATArena chess agent.

Public interface:
    select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation intentionally avoids network access, subprocesses, file I/O,
eval/exec, and dynamic imports.  Every returned move is validated against
python-chess legal_moves, with a deterministic legal fallback.
"""

from __future__ import annotations

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

# Deterministic opening preferences.  These are not used as an illegal book:
# entries are only accepted when present in board.legal_moves.
PREFERRED_OPENING_MOVES = (
    "e2e4", "d2d4", "g1f3", "c2c4", "e7e5", "d7d5", "g8f6", "c7c5",
)


class SearchTimeout(Exception):
    """Internal control-flow exception for bounded search."""


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

    try:
        chosen = _choose_move(board, observation, time_limit_ms)
    except Exception:
        chosen = None

    if chosen not in legal_moves:
        chosen = _fallback_move(board, observation)
    if chosen not in legal_moves:
        chosen = legal_moves[0]

    return _format_move(board, chosen, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    """Parse common arena observations into a chess.Board.

    Supports official CATArena dicts containing ``fen``, direct FEN strings,
    python-chess Board objects, and nested common keys.  On malformed input we
    return the normal initial position rather than crashing.
    """
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    if isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text
    elif isinstance(observation, dict):
        for key in ("fen", "board_fen", "state", "board", "observation"):
            value = observation.get(key)
            if isinstance(value, chess.Board):
                return value.copy(stack=False)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
            if isinstance(value, dict) and isinstance(value.get("fen"), str):
                fen = value["fen"].strip()
                break

    if fen is not None:
        try:
            return chess.Board(fen)
        except Exception:
            pass
    return chess.Board()


def _choose_move(board: chess.Board, observation: Any, time_limit_ms: int) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    mate = _mate_in_one(board, legal_moves)
    if mate is not None:
        return mate

    opening = _opening_preference(board, legal_moves)
    if opening is not None and board.fullmove_number <= 2:
        return opening

    # Keep a conservative margin for the caller/arena overhead.
    budget_ms = max(5, min(int(time_limit_ms), 300))
    deadline = time.perf_counter() + max(0.003, (budget_ms - 3) / 1000.0)

    # Depth is capped for predictable runtime.  Quiescence supplies most of the
    # tactical extra strength without exploding the tree in normal positions.
    if budget_ms < 30:
        max_depth = 2
    elif budget_ms < 90:
        max_depth = 3
    else:
        max_depth = 4

    best_move = _fallback_move(board, observation)
    ordered_root = _order_moves(board, legal_moves, None)
    table: dict[tuple[str, int], tuple[int, chess.Move | None]] = {}

    for depth in range(1, max_depth + 1):
        try:
            score, move = _root_search(board, ordered_root, depth, deadline, table)
            if move in legal_moves:
                best_move = move
                # If we have a forced mate, no need to spend more time.
                if score > MATE_SCORE - 1000:
                    break
            ordered_root = _order_moves(board, legal_moves, best_move)
        except SearchTimeout:
            break

    return best_move


def _root_search(
    board: chess.Board,
    moves: list[chess.Move],
    depth: int,
    deadline: float,
    table: dict[tuple[str, int], tuple[int, chess.Move | None]],
) -> tuple[int, chess.Move | None]:
    alpha = -INF
    beta = INF
    best_score = -INF
    best_move = None

    for mv in moves:
        _check_time(deadline)
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, table, 1)
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
    table: dict[tuple[str, int], tuple[int, chess.Move | None]],
    ply: int,
) -> int:
    _check_time(deadline)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    key = (_position_key(board), depth)
    cached = table.get(key)
    if cached is not None:
        return cached[0]

    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    best = -INF
    best_move = None
    legal = list(board.legal_moves)
    ordered = _order_moves(board, legal, None)

    for mv in ordered:
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, table, ply + 1)
        board.pop()

        if score > best:
            best = score
            best_move = mv
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break

    table[key] = (best, best_move)
    return best


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> int:
    _check_time(deadline)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    stand_pat = _evaluate(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    noisy_moves = [
        mv for mv in board.legal_moves
        if board.is_capture(mv) or mv.promotion is not None
    ]
    for mv in _order_moves(board, noisy_moves, None):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate(board: chess.Board) -> int:
    """Static evaluation from the side-to-move perspective."""
    if board.is_checkmate():
        return -MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    bishops = {chess.WHITE: 0, chess.BLACK: 0}

    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        value = PIECE_VALUES[piece.piece_type]
        score += sign * value
        if piece.piece_type == chess.BISHOP:
            bishops[piece.color] += 1
        score += sign * _positional_bonus(piece, square, board)

    if bishops[chess.WHITE] >= 2:
        score += 35
    if bishops[chess.BLACK] >= 2:
        score -= 35

    # Small mobility and check-pressure terms.  They are deliberately cheap.
    turn = board.turn
    white_mob = _safe_mobility(board, chess.WHITE)
    black_mob = _safe_mobility(board, chess.BLACK)
    board.turn = turn
    score += 2 * (white_mob - black_mob)

    if board.is_check():
        score += -25 if board.turn == chess.WHITE else 25

    return score if board.turn == chess.WHITE else -score


def _positional_bonus(piece: chess.Piece, square: chess.Square, board: chess.Board) -> int:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    own_rank = rank_index if piece.color == chess.WHITE else 7 - rank_index
    center_distance = abs(file_index - 3.5) + abs(rank_index - 3.5)
    center_bonus = int(18 - 4 * center_distance)

    if piece.piece_type == chess.PAWN:
        bonus = own_rank * 8
        if file_index in (3, 4):
            bonus += 8
        if own_rank >= 5:
            bonus += 18
        return bonus
    if piece.piece_type == chess.KNIGHT:
        return center_bonus + (8 if own_rank >= 2 else -15)
    if piece.piece_type == chess.BISHOP:
        return center_bonus + 4
    if piece.piece_type == chess.ROOK:
        bonus = 5 if own_rank >= 4 else 0
        if _is_open_or_half_open_file(board, square, piece.color):
            bonus += 12
        return bonus
    if piece.piece_type == chess.QUEEN:
        return int(center_bonus / 2)
    if piece.piece_type == chess.KING:
        # Prefer castled/sheltered king in opening, activity in simplified endgames.
        non_pawn_material = _non_pawn_material(board)
        if non_pawn_material > 2600:
            edge_bonus = int(6 * center_distance)
            shelter = _king_shelter(board, square, piece.color)
            return edge_bonus + shelter
        return int(20 - 4 * center_distance)
    return 0


def _non_pawn_material(board: chess.Board) -> int:
    total = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += len(board.pieces(piece_type, chess.WHITE)) * PIECE_VALUES[piece_type]
        total += len(board.pieces(piece_type, chess.BLACK)) * PIECE_VALUES[piece_type]
    return total


def _king_shelter(board: chess.Board, square: chess.Square, color: chess.Color) -> int:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    direction = 1 if color == chess.WHITE else -1
    bonus = 0
    for df in (-1, 0, 1):
        f = file_index + df
        r = rank_index + direction
        if 0 <= f <= 7 and 0 <= r <= 7:
            piece = board.piece_at(chess.square(f, r))
            if piece is not None and piece.color == color and piece.piece_type == chess.PAWN:
                bonus += 8
    return bonus


def _is_open_or_half_open_file(board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
    file_index = chess.square_file(square)
    own_pawn = False
    for rank_index in range(8):
        piece = board.piece_at(chess.square(file_index, rank_index))
        if piece is not None and piece.piece_type == chess.PAWN and piece.color == color:
            own_pawn = True
            break
    return not own_pawn


def _safe_mobility(board: chess.Board, color: chess.Color) -> int:
    original_turn = board.turn
    try:
        board.turn = color
        if board.status() == chess.STATUS_VALID:
            return min(60, board.legal_moves.count())
    except Exception:
        return 0
    finally:
        board.turn = original_turn
    return 0


def _order_moves(
    board: chess.Board,
    moves: list[chess.Move],
    preferred: chess.Move | None,
) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv, preferred), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move, preferred: chess.Move | None) -> int:
    score = 0
    if preferred is not None and mv == preferred:
        score += 1000000
    if mv.promotion is not None:
        score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.is_capture(mv):
        victim_value = _captured_piece_value(board, mv)
        attacker = board.piece_at(mv.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 5000 + 10 * victim_value - attacker_value
    if board.gives_check(mv):
        score += 2500

    piece = board.piece_at(mv.from_square)
    if piece is not None:
        to_file = chess.square_file(mv.to_square)
        to_rank = chess.square_rank(mv.to_square)
        center_distance = abs(to_file - 3.5) + abs(to_rank - 3.5)
        score += int(20 - 3 * center_distance)
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 10:
            home_rank = 0 if piece.color == chess.WHITE else 7
            if chess.square_rank(mv.from_square) == home_rank:
                score += 35
        if piece.piece_type == chess.KING and board.is_castling(mv):
            score += 70
    return score


def _captured_piece_value(board: chess.Board, mv: chess.Move) -> int:
    if board.is_en_passant(mv):
        return PIECE_VALUES[chess.PAWN]
    victim = board.piece_at(mv.to_square)
    if victim is None:
        return 0
    return PIECE_VALUES.get(victim.piece_type, 0)


def _mate_in_one(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move | None:
    for mv in _order_moves(board, legal_moves, None):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _opening_preference(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move | None:
    legal_by_uci = {mv.uci(): mv for mv in legal_moves}
    for uci in PREFERRED_OPENING_MOVES:
        mv = legal_by_uci.get(uci)
        if mv is not None:
            return mv
    return None


def _fallback_move(board: chess.Board, observation: Any) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return chess.Move.null()

    hinted = _extract_hint_moves(observation)
    if hinted:
        legal_by_uci = {mv.uci(): mv for mv in legal_moves}
        for text in hinted:
            mv = legal_by_uci.get(text)
            if mv is not None:
                return mv

    mate = _mate_in_one(board, legal_moves)
    if mate is not None:
        return mate

    return _order_moves(board, legal_moves, None)[0]


def _extract_hint_moves(observation: Any) -> list[str]:
    if not isinstance(observation, dict):
        return []
    values: list[Any] = []
    for key in ("legal_moves", "legalMoves", "moves"):
        raw = observation.get(key)
        if isinstance(raw, list | tuple):
            values.extend(raw)
    result = []
    for item in values:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").strip().lower()
    if fmt in ("san", "algebraic"):
        try:
            return board.san(mv)
        except Exception:
            return mv.uci()
    return mv.uci()


def _position_key(board: chess.Board) -> str:
    # Avoid private python-chess APIs and keep keys compact enough for shallow use.
    return " ".join(board.fen().split(" ")[:4])


def _check_time(deadline: float) -> None:
    if time.perf_counter() >= deadline:
        raise SearchTimeout
