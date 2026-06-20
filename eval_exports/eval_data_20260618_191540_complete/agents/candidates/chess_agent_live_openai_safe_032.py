"""Self-contained safe CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent performs only local computation, never uses network/subprocess/file IO,
and validates every returned move against python-chess legal moves.
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
    chess.BISHOP: 335,
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
    chess.F4,
    chess.C5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
}

KNIGHT_TABLE = [
    -50, -35, -25, -20, -20, -25, -35, -50,
    -35, -20,   0,   5,   5,   0, -20, -35,
    -25,   5,  12,  18,  18,  12,   5, -25,
    -20,   8,  18,  25,  25,  18,   8, -20,
    -20,   5,  18,  25,  25,  18,   5, -20,
    -25,   5,  12,  18,  18,  12,   5, -25,
    -35, -20,   0,   5,   5,   0, -20, -35,
    -50, -35, -25, -20, -20, -25, -35, -50,
]

BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   0,  10,  15,  15,  10,   0, -10,
    -10,   5,  10,  15,  15,  10,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

PAWN_TABLE = [
      0,   0,   0,   0,   0,   0,   0,   0,
     50,  50,  50,  50,  50,  50,  50,  50,
     10,  10,  20,  30,  30,  20,  10,  10,
      5,   5,  10,  25,  25,  10,   5,   5,
      0,   0,   0,  18,  18,   0,   0,   0,
      5,  -5, -10,   0,   0, -10,  -5,   5,
      5,  10,  10, -20, -20,  10,  10,   5,
      0,   0,   0,   0,   0,   0,   0,   0,
]


def _mirror_index(square: chess.Square, color: chess.Color) -> int:
    return square if color == chess.WHITE else chess.square_mirror(square)


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
        move = _choose_move(board, max(1, int(time_limit_ms)))
        if move not in legal_moves:
            move = _fallback_move(board)
        return _format_move(board, move, output_format)
    except Exception:
        try:
            board = _parse_observation(observation)
            move = _fallback_move(board)
            return move.uci() if move is not None else ""
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
        fen = observation.get("fen") or observation.get("board") or observation.get("state")
        if isinstance(fen, str):
            return chess.Board(fen)
    if isinstance(observation, str):
        text = observation.strip()
        if text:
            return chess.Board(text)
    return chess.Board()


def _format_move(board: chess.Board, move_obj: chess.Move | None, output_format: str) -> str:
    if move_obj is None or move_obj not in board.legal_moves:
        return ""
    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def _fallback_move(board: chess.Board) -> chess.Move | None:
    legal = list(board.legal_moves)
    if not legal:
        return None
    ordered = sorted(legal, key=lambda mv: _move_order_score(board, mv), reverse=True)
    return ordered[0]


def _choose_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    legal = list(board.legal_moves)
    if len(legal) == 1:
        return legal[0]

    # Always take an immediate checkmate if available.
    for mv in _ordered_moves(board):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv

    start = time.perf_counter()
    budget = max(0.003, min(0.20, (time_limit_ms - 6) / 1000.0))
    deadline = start + budget

    piece_count = len(board.piece_map())
    if time_limit_ms < 45:
        max_depth = 2
    elif time_limit_ms < 90:
        max_depth = 3
    elif piece_count <= 12:
        max_depth = 4
    else:
        max_depth = 3

    best_move = _fallback_move(board) or legal[0]
    best_score = -INF
    ordered_root = _ordered_moves(board)

    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        beta = INF
        completed = True
        for mv in ordered_root:
            if time.perf_counter() >= deadline:
                completed = False
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -beta, -alpha, deadline, 1)
            board.pop()
            if score > current_score:
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score
        if completed:
            best_move = current_best
            best_score = current_score
            if best_score > MATE_SCORE - 1000:
                break
        else:
            break
    return best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, deadline: float, ply: int) -> int:
    if time.perf_counter() >= deadline:
        return _evaluate_relative(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    value = -INF
    for mv in _ordered_moves(board):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score > value:
            value = score
        if value > alpha:
            alpha = value
        if alpha >= beta:
            break
    return value


def _quiescence(board: chess.Board, alpha: int, beta: int, deadline: float, ply: int) -> int:
    if time.perf_counter() >= deadline:
        return _evaluate_relative(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    stand_pat = _evaluate_relative(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            tactical.append(mv)
    tactical.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)

    for mv in tactical[:18]:
        if time.perf_counter() >= deadline:
            break
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _ordered_moves(board: chess.Board) -> list[chess.Move]:
    moves = list(board.legal_moves)
    moves.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)
    return moves


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    moving = board.piece_at(mv.from_square)
    captured = board.piece_at(mv.to_square)
    if captured is None and board.is_en_passant(mv):
        captured = chess.Piece(chess.PAWN, not board.turn)
    if captured is not None:
        attacker_value = PIECE_VALUES.get(moving.piece_type if moving else chess.PAWN, 100)
        victim_value = PIECE_VALUES.get(captured.piece_type, 100)
        score += 10000 + 10 * victim_value - attacker_value
    if mv.promotion:
        score += 8500 + PIECE_VALUES.get(mv.promotion, 0)
    try:
        if board.gives_check(mv):
            score += 2500
    except Exception:
        pass
    if board.is_castling(mv):
        score += 650
    if mv.to_square in CENTER:
        score += 180
    elif mv.to_square in EXTENDED_CENTER:
        score += 70
    if moving is not None and moving.piece_type in (chess.KNIGHT, chess.BISHOP):
        rank = chess.square_rank(mv.from_square)
        if (moving.color == chess.WHITE and rank == 0) or (moving.color == chess.BLACK and rank == 7):
            score += 140
    if moving is not None and moving.piece_type == chess.QUEEN and board.fullmove_number <= 8:
        score -= 90
    return score


def _evaluate_relative(board: chess.Board) -> int:
    white_score = _evaluate_color(board, chess.WHITE) - _evaluate_color(board, chess.BLACK)
    mobility_turn = board.turn
    try:
        own_mobility = board.legal_moves.count()
        board.turn = not board.turn
        opp_mobility = board.legal_moves.count()
        board.turn = mobility_turn
        white_score += (own_mobility - opp_mobility) * (3 if mobility_turn == chess.WHITE else -3)
    except Exception:
        board.turn = mobility_turn
    return white_score if board.turn == chess.WHITE else -white_score


def _evaluate_color(board: chess.Board, color: chess.Color) -> int:
    score = 0
    bishops = 0
    pawns_by_file = [0] * 8

    for square, piece in board.piece_map().items():
        if piece.color != color:
            continue
        ptype = piece.piece_type
        score += PIECE_VALUES.get(ptype, 0)
        idx = _mirror_index(square, color)
        if ptype == chess.PAWN:
            score += PAWN_TABLE[idx]
            pawns_by_file[chess.square_file(square)] += 1
            score += _passed_pawn_bonus(board, square, color)
        elif ptype == chess.KNIGHT:
            score += KNIGHT_TABLE[idx]
        elif ptype == chess.BISHOP:
            bishops += 1
            score += BISHOP_TABLE[idx]
        elif ptype == chess.ROOK:
            score += _rook_file_bonus(board, square, color)
        elif ptype == chess.QUEEN:
            if square in CENTER:
                score += 8
        elif ptype == chess.KING:
            score += _king_safety(board, square, color)

        if square in CENTER:
            score += 16
        elif square in EXTENDED_CENTER:
            score += 6

    if bishops >= 2:
        score += 35
    for count in pawns_by_file:
        if count > 1:
            score -= 14 * (count - 1)
    for file_idx, count in enumerate(pawns_by_file):
        if count and not _has_neighbor_pawn(pawns_by_file, file_idx):
            score -= 10 * count
    return score


def _has_neighbor_pawn(pawns_by_file: list[int], file_idx: int) -> bool:
    return (file_idx > 0 and pawns_by_file[file_idx - 1] > 0) or (
        file_idx < 7 and pawns_by_file[file_idx + 1] > 0
    )


def _passed_pawn_bonus(board: chess.Board, square: chess.Square, color: chess.Color) -> int:
    file_idx = chess.square_file(square)
    rank = chess.square_rank(square)
    enemy = not color
    files = [f for f in (file_idx - 1, file_idx, file_idx + 1) if 0 <= f <= 7]
    if color == chess.WHITE:
        ahead_ranks = range(rank + 1, 8)
        advance = rank
    else:
        ahead_ranks = range(rank - 1, -1, -1)
        advance = 7 - rank
    for f in files:
        for r in ahead_ranks:
            piece = board.piece_at(chess.square(f, r))
            if piece is not None and piece.color == enemy and piece.piece_type == chess.PAWN:
                return 0
    return 8 + advance * advance * 3


def _rook_file_bonus(board: chess.Board, square: chess.Square, color: chess.Color) -> int:
    file_idx = chess.square_file(square)
    own_pawn = False
    enemy_pawn = False
    for rank in range(8):
        piece = board.piece_at(chess.square(file_idx, rank))
        if piece is not None and piece.piece_type == chess.PAWN:
            if piece.color == color:
                own_pawn = True
            else:
                enemy_pawn = True
    if not own_pawn and not enemy_pawn:
        return 28
    if not own_pawn and enemy_pawn:
        return 16
    return 0


def _king_safety(board: chess.Board, square: chess.Square, color: chess.Color) -> int:
    # In early/middlegame, prefer castled or shielded kings and penalize exposed kings.
    non_king_material = sum(
        PIECE_VALUES.get(piece.piece_type, 0)
        for piece in board.piece_map().values()
        if piece.piece_type != chess.KING
    )
    if non_king_material < 2400:
        return 0
    score = 0
    file_idx = chess.square_file(square)
    rank = chess.square_rank(square)
    home_rank = 0 if color == chess.WHITE else 7
    if rank == home_rank and file_idx in (1, 2, 6):
        score += 25
    pawn_rank = rank + (1 if color == chess.WHITE else -1)
    if 0 <= pawn_rank <= 7:
        for f in (file_idx - 1, file_idx, file_idx + 1):
            if 0 <= f <= 7:
                piece = board.piece_at(chess.square(f, pawn_rank))
                if piece is not None and piece.color == color and piece.piece_type == chess.PAWN:
                    score += 10
    enemy_attacks = 0
    for sq in chess.SquareSet(chess.BB_KING_ATTACKS[square]):
        if board.is_attacked_by(not color, sq):
            enemy_attacks += 1
    score -= 8 * enemy_attacks
    return score
