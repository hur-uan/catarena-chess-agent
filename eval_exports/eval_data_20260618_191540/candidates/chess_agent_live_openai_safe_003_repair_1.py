"""Standalone safe CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent is deterministic, uses only python-chess, performs no network or file
access, and validates every selected move against board.legal_moves before
returning it.
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

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
NEAR_CENTER_SQUARES = {
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


class ChessAgent:
    """Small class wrapper for arena integrations that instantiate agents."""

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
    """Choose a legal move for the supplied chess observation."""
    board = _parse_board(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    chosen = _find_mate_in_one(board, legal_moves)
    if chosen is None:
        chosen = _search_move(board, time_limit_ms)

    if chosen not in board.legal_moves:
        chosen = legal_moves[0]

    if output_format.lower() == "san":
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


def _parse_board(observation: Any) -> chess.Board:
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
        fen = observation.strip()
    else:
        value = getattr(observation, "fen", None)
        if isinstance(value, str) and value.strip():
            fen = value.strip()

    if not fen or fen.lower() == "startpos":
        return chess.Board()

    try:
        return chess.Board(fen)
    except Exception:
        return chess.Board()


def _find_mate_in_one(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move | None:
    ordered = sorted(legal_moves, key=lambda mv: _move_order_score(board, mv))
    for mv in reversed(ordered):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _search_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return chess.Move.null()

    safe_ms = max(8, min(int(time_limit_ms * 0.70), max(8, time_limit_ms - 8)))
    deadline = time.perf_counter() + safe_ms / 1000.0
    node_budget = 12000 if time_limit_ms >= 80 else 5000
    if len(legal_moves) > 34:
        node_budget = int(node_budget * 0.70)

    ordered = sorted(
        legal_moves,
        key=lambda mv: _move_order_score(board, mv),
        reverse=True,
    )
    best_move = ordered[0]
    best_score = -INF
    nodes = [0]

    piece_count = len(board.piece_map())
    max_depth = 4 if piece_count <= 12 and len(legal_moves) <= 28 else 3
    if time_limit_ms < 45:
        max_depth = 2

    for depth in range(1, max_depth + 1):
        if nodes[0] >= node_budget or time.perf_counter() >= deadline:
            break

        completed = True
        current_best = best_move
        current_score = -INF
        alpha = -INF

        for mv in ordered:
            if nodes[0] >= node_budget or time.perf_counter() >= deadline:
                completed = False
                break
            board.push(mv)
            score = -_negamax(
                board,
                depth - 1,
                -INF,
                -alpha,
                deadline,
                nodes,
                node_budget,
            )
            board.pop()

            if score > current_score:
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score

        if completed:
            best_move = current_best
            best_score = current_score
            ordered.sort(
                key=lambda mv: (mv == best_move, _move_order_score(board, mv)),
                reverse=True,
            )
            if best_score >= MATE_SCORE - 1000:
                break

    return best_move if best_move in board.legal_moves else legal_moves[0]


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    nodes: list[int],
    node_budget: int,
) -> int:
    nodes[0] += 1
    if nodes[0] >= node_budget or time.perf_counter() >= deadline:
        return _evaluate(board)

    if board.is_checkmate():
        return -MATE_SCORE + min(len(board.move_stack), 200)
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_draw():
        return -8

    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, nodes, node_budget, 0)

    moves = list(board.legal_moves)
    moves.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)

    best = -INF
    for mv in moves:
        if nodes[0] >= node_budget or time.perf_counter() >= deadline:
            break
        board.push(mv)
        score = -_negamax(
            board,
            depth - 1,
            -beta,
            -alpha,
            deadline,
            nodes,
            node_budget,
        )
        board.pop()

        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break

    return best if best > -INF else _evaluate(board)


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    nodes: list[int],
    node_budget: int,
    ply: int,
) -> int:
    nodes[0] += 1
    stand_pat = _evaluate(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    if ply >= 4 or nodes[0] >= node_budget or time.perf_counter() >= deadline:
        return alpha

    noisy = [mv for mv in board.legal_moves if board.is_capture(mv) or mv.promotion]
    noisy.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)

    for mv in noisy:
        if nodes[0] >= node_budget or time.perf_counter() >= deadline:
            break
        board.push(mv)
        score = -_quiescence(
            board,
            -beta,
            -alpha,
            deadline,
            nodes,
            node_budget,
            ply + 1,
        )
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


def _evaluate(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE + min(len(board.move_stack), 200)
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    bishops = {chess.WHITE: 0, chess.BLACK: 0}

    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        score += sign * PIECE_VALUES[piece.piece_type]
        score += sign * _piece_square_bonus(piece, square)
        if piece.piece_type == chess.BISHOP:
            bishops[piece.color] += 1

    if bishops[chess.WHITE] >= 2:
        score += 30
    if bishops[chess.BLACK] >= 2:
        score -= 30

    score += _pawn_structure_score(board, chess.WHITE)
    score -= _pawn_structure_score(board, chess.BLACK)

    if board.has_kingside_castling_rights(chess.WHITE):
        score += 8
    if board.has_queenside_castling_rights(chess.WHITE):
        score += 5
    if board.has_kingside_castling_rights(chess.BLACK):
        score -= 8
    if board.has_queenside_castling_rights(chess.BLACK):
        score -= 5

    if board.is_check():
        score += -25 if board.turn == chess.WHITE else 25

    return score if board.turn == chess.WHITE else -score


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = board.pieces(chess.PAWN, color)
    files = [0] * 8
    for square in pawns:
        files[chess.square_file(square)] += 1

    score = 0
    for file_idx, count in enumerate(files):
        if count > 1:
            score -= 10 * (count - 1)
        if count:
            left = files[file_idx - 1] if file_idx > 0 else 0
            right = files[file_idx + 1] if file_idx < 7 else 0
            if left == 0 and right == 0:
                score -= 12
    return score


def _piece_square_bonus(piece: chess.Piece, square: chess.Square) -> int:
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    rank_for_color = rank_idx if piece.color == chess.WHITE else 7 - rank_idx
    center_file_distance = abs(file_idx - 3.5)
    center_rank_distance = abs(rank_idx - 3.5)

    if piece.piece_type == chess.PAWN:
        bonus = rank_for_color * 8
        if file_idx in (3, 4):
            bonus += 8
        return bonus
    if piece.piece_type == chess.KNIGHT:
        return int(34 - 8 * center_file_distance - 8 * center_rank_distance)
    if piece.piece_type == chess.BISHOP:
        return int(20 - 4 * center_file_distance - 4 * center_rank_distance)
    if piece.piece_type == chess.ROOK:
        return 8 if rank_for_color >= 5 else 0
    if piece.piece_type == chess.QUEEN:
        return 8 if square in CENTER_SQUARES or square in NEAR_CENTER_SQUARES else 0
    if piece.piece_type == chess.KING:
        if rank_for_color <= 1 and file_idx in (1, 2, 6):
            return 18
        if rank_for_color >= 5:
            return -18
    return 0


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0

    if mv.promotion:
        score += PIECE_VALUES.get(mv.promotion, 0) + 800

    if board.is_capture(mv):
        victim_type = board.piece_type_at(mv.to_square)
        if victim_type is None and board.is_en_passant(mv):
            victim_type = chess.PAWN
        attacker_type = board.piece_type_at(mv.from_square)
        victim_value = PIECE_VALUES.get(victim_type, 0)
        attacker_value = PIECE_VALUES.get(attacker_type, 0)
        score += 1000 + victim_value - attacker_value // 10

    if board.gives_check(mv):
        score += 450
    if mv.to_square in CENTER_SQUARES:
        score += 30
    elif mv.to_square in NEAR_CENTER_SQUARES:
        score += 12

    piece = board.piece_at(mv.from_square)
    if piece is not None and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        home_rank = 0 if piece.color == chess.WHITE else 7
        if chess.square_rank(mv.from_square) == home_rank:
            score += 15

    if piece is not None and piece.piece_type == chess.KING:
        if abs(chess.square_file(mv.to_square) - chess.square_file(mv.from_square)) == 2:
            score += 40

    return score
