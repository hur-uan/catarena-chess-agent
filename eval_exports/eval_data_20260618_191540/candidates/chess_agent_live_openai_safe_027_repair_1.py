"""Safe standalone CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent uses python-chess only, performs bounded deterministic search, and
validates every selected move against legal_moves before returning it.
"""

from __future__ import annotations

import time
from typing import Any, Optional

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
    chess.C3,
    chess.D3,
    chess.E3,
    chess.F3,
    chess.C4,
    chess.D4,
    chess.E4,
    chess.F4,
    chess.C5,
    chess.D5,
    chess.E5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
}


class SearchTimeout(Exception):
    """Raised internally when the move budget is exhausted."""


class ChessAgent:
    """Small wrapper compatible with common arena integrations."""

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

    fmt = (output_format or "uci").strip().lower()
    if fmt == "san":
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
    """Parse direct Boards, FEN strings, and common CATArena dictionaries."""
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    if isinstance(observation, str):
        fen = observation.strip()
    elif isinstance(observation, dict):
        for key in ("fen", "board", "state", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        if fen is None:
            nested = observation.get("observation")
            if isinstance(nested, dict):
                value = nested.get("fen")
                if isinstance(value, str) and value.strip():
                    fen = value.strip()

    if fen:
        try:
            return chess.Board(fen)
        except Exception:
            pass
    return chess.Board()


def _choose_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
    time_limit_ms: int,
) -> chess.Move:
    mate = _find_mate_in_one(board, legal_moves)
    if mate is not None:
        return mate

    safe_limit = max(8, int(time_limit_ms or 100))
    budget = max(0.004, (safe_limit - 3) / 1000.0)
    deadline = time.perf_counter() + budget

    if safe_limit < 35:
        max_depth = 2
    elif safe_limit < 90:
        max_depth = 3
    elif len(legal_moves) <= 12:
        max_depth = 4
    else:
        max_depth = 3

    ordered = _order_moves(board, legal_moves)
    best_move = ordered[0]
    best_score = -INF

    try:
        for depth in range(1, max_depth + 1):
            _check_time(deadline)
            depth_best = best_move
            depth_score = -INF
            alpha = -INF
            beta = INF

            for mv in ordered:
                _check_time(deadline)
                board.push(mv)
                score = -_negamax(board, depth - 1, -beta, -alpha, 1, deadline)
                allows_mate = _has_mate_in_one(board, deadline)
                board.pop()

                score += _root_practical_bonus(board, mv)
                if allows_mate:
                    score -= MATE_SCORE // 2

                if score > depth_score:
                    depth_score = score
                    depth_best = mv
                if score > alpha:
                    alpha = score

            best_move = depth_best
            best_score = depth_score
            ordered = [best_move] + [mv for mv in ordered if mv != best_move]
            if best_score >= MATE_SCORE - 10:
                break
    except SearchTimeout:
        pass
    except Exception:
        return _fallback_move(board, legal_moves)

    if best_move not in legal_moves:
        return _fallback_move(board, legal_moves)
    return best_move


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    ply: int,
    deadline: float,
) -> int:
    _check_time(deadline)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_draw():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, ply, deadline, 0)

    best = -INF
    moves = _order_moves(board, list(board.legal_moves))
    if not moves:
        return _evaluate_for_side_to_move(board)

    for mv in moves:
        _check_time(deadline)
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, ply + 1, deadline)
        board.pop()

        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    ply: int,
    deadline: float,
    qdepth: int,
) -> int:
    _check_time(deadline)

    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if qdepth >= 5:
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion is not None:
            tactical.append(mv)
    tactical = _order_moves(board, tactical)

    for mv in tactical:
        _check_time(deadline)
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, ply + 1, deadline, qdepth + 1)
        board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _find_mate_in_one(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> Optional[chess.Move]:
    for mv in _order_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _has_mate_in_one(board: chess.Board, deadline: float) -> bool:
    """Return True if side to move can immediately checkmate."""
    for mv in _order_moves(board, list(board.legal_moves)):
        _check_time(deadline)
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return True
    return False


def _order_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    piece = board.piece_at(mv.from_square)
    victim = board.piece_at(mv.to_square)

    if mv.promotion is not None:
        score += 7000 + PIECE_VALUES.get(mv.promotion, 0)
    if victim is not None:
        attacker_value = PIECE_VALUES.get(piece.piece_type, 0) if piece else 0
        victim_value = PIECE_VALUES.get(victim.piece_type, 0)
        score += 5000 + 10 * victim_value - attacker_value
    elif board.is_en_passant(mv):
        score += 5600

    if board.gives_check(mv):
        score += 2500
    if board.is_castling(mv):
        score += 800
    if mv.to_square in CENTER:
        score += 260
    elif mv.to_square in EXTENDED_CENTER:
        score += 100

    if piece is not None:
        from_rank = chess.square_rank(mv.from_square)
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and from_rank in (0, 7):
            score += 180
        if piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 120
        if piece.piece_type == chess.ROOK and board.fullmove_number <= 10:
            score -= 60
    return score


def _root_practical_bonus(board: chess.Board, mv: chess.Move) -> int:
    bonus = 0
    if board.is_castling(mv):
        bonus += 25
    if mv.to_square in CENTER:
        bonus += 8
    if board.gives_check(mv):
        bonus += 5
    return bonus


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    white = _evaluate_color(board, chess.WHITE)
    black = _evaluate_color(board, chess.BLACK)
    score = white - black
    return score if board.turn == chess.WHITE else -score


def _evaluate_color(board: chess.Board, color: chess.Color) -> int:
    score = 0
    bishops = 0

    for sq, piece in board.piece_map().items():
        if piece.color != color:
            continue
        piece_type = piece.piece_type
        score += PIECE_VALUES.get(piece_type, 0)
        score += _piece_square_bonus(piece_type, sq, color)
        if piece_type == chess.BISHOP:
            bishops += 1

    if bishops >= 2:
        score += 35
    if board.turn == color:
        score += min(60, board.legal_moves.count() * 2)

    score += _king_safety(board, color)
    score += _pawn_structure(board, color)
    return score


def _piece_square_bonus(
    piece_type: chess.PieceType,
    square: chess.Square,
    color: chess.Color,
) -> int:
    rank = chess.square_rank(square)
    file_idx = chess.square_file(square)
    if color == chess.BLACK:
        rank = 7 - rank

    center_distance = abs(file_idx - 3.5) + abs(rank - 3.5)
    bonus = 0

    if piece_type == chess.PAWN:
        bonus += rank * 7
        if file_idx in (3, 4):
            bonus += 8
    elif piece_type == chess.KNIGHT:
        bonus += int(28 - 8 * center_distance)
        if rank >= 2:
            bonus += 8
    elif piece_type == chess.BISHOP:
        bonus += int(22 - 5 * center_distance)
        if rank >= 2:
            bonus += 6
    elif piece_type == chess.ROOK:
        if rank >= 6:
            bonus += 18
        elif rank >= 4:
            bonus += 7
    elif piece_type == chess.QUEEN:
        bonus += int(10 - 2 * center_distance)
    elif piece_type == chess.KING:
        if rank == 0 and file_idx in (1, 2, 6):
            bonus += 25
        if rank >= 3:
            bonus -= 20
    return bonus


def _king_safety(board: chess.Board, color: chess.Color) -> int:
    king_sq = board.king(color)
    if king_sq is None:
        return -MATE_SCORE // 2

    score = 0
    enemy = not color
    if board.is_attacked_by(enemy, king_sq):
        score -= 80

    rank_dir = 1 if color == chess.WHITE else -1
    k_file = chess.square_file(king_sq)
    k_rank = chess.square_rank(king_sq)

    for df in (-1, 0, 1):
        file_idx = k_file + df
        rank = k_rank + rank_dir
        if 0 <= file_idx <= 7 and 0 <= rank <= 7:
            sq = chess.square(file_idx, rank)
            piece = board.piece_at(sq)
            if piece and piece.color == color and piece.piece_type == chess.PAWN:
                score += 10
    return score


def _pawn_structure(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    if not pawns:
        return 0

    score = 0
    files = [0] * 8
    for sq in pawns:
        files[chess.square_file(sq)] += 1

    for file_count in files:
        if file_count > 1:
            score -= 10 * (file_count - 1)

    for sq in pawns:
        file_idx = chess.square_file(sq)
        isolated = True
        for near_file in (file_idx - 1, file_idx + 1):
            if 0 <= near_file <= 7 and files[near_file] > 0:
                isolated = False
        if isolated:
            score -= 8

        rank = chess.square_rank(sq)
        advance = rank if color == chess.WHITE else 7 - rank
        if advance >= 4:
            score += 8 + 4 * (advance - 4)
    return score


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    mate = _find_mate_in_one(board, legal_moves)
    if mate is not None:
        return mate
    ordered = _order_moves(board, legal_moves)
    return ordered[0] if ordered else chess.Move.null()


def _check_time(deadline: float) -> None:
    if time.perf_counter() >= deadline:
        raise SearchTimeout
