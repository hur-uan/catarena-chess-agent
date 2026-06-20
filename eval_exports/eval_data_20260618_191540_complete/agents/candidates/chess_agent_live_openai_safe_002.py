from __future__ import annotations

import json
import time
from typing import Any

import chess

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

MATE_SCORE = 100000
INF = 100000000

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}

BOOK = {
    chess.STARTING_FEN: ["e2e4", "d2d4", "g1f3", "c2c4"],
}


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def select_move(observation: Any, output_format: str = "uci", time_limit_ms: int = 100) -> str:
    """Choose a legal chess move for the supplied observation.

    The returned move is always checked against python-chess legal moves. If no
    legal move exists, an empty string is returned.
    """
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    legal_set = {mv.uci(): mv for mv in legal_moves}

    book_move = _book_move(board, legal_set)
    if book_move is not None:
        return _format_move(board, book_move, output_format)

    mate_move = _find_immediate_mate(board, legal_moves)
    if mate_move is not None:
        return _format_move(board, mate_move, output_format)

    fallback = _fallback_move(board, legal_moves)
    chosen = fallback

    safe_ms = max(5, min(int(time_limit_ms) if isinstance(time_limit_ms, int) else 100, 1000))
    deadline = time.perf_counter() + (safe_ms / 1000.0) * 0.82
    node_cap = 1200 if safe_ms < 40 else 2600 if safe_ms < 90 else 5200
    max_depth = 2 if safe_ms < 25 else 3 if safe_ms < 85 else 4
    if len(legal_moves) <= 12 and safe_ms >= 60:
        max_depth += 1

    nodes = [0]
    ordered = _order_moves(board, legal_moves)
    try:
        for depth in range(1, max_depth + 1):
            if time.perf_counter() >= deadline:
                break
            best_at_depth = None
            best_score = -INF
            alpha = -INF
            beta = INF
            for mv in ordered:
                if time.perf_counter() >= deadline or nodes[0] >= node_cap:
                    raise TimeoutError
                board.push(mv)
                score = -_negamax(board, depth - 1, -beta, -alpha, deadline, nodes, node_cap, 1)
                board.pop()
                if score > best_score:
                    best_score = score
                    best_at_depth = mv
                if score > alpha:
                    alpha = score
            if best_at_depth is not None:
                chosen = best_at_depth
                ordered = [best_at_depth] + [mv for mv in ordered if mv != best_at_depth]
    except TimeoutError:
        pass

    if chosen not in legal_moves:
        chosen = fallback
    return _format_move(board, chosen, output_format)


def _parse_observation(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    data = observation
    if isinstance(observation, str):
        text = observation.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = text
        else:
            data = text

    fen = None
    if isinstance(data, dict):
        for key in ("fen", "board", "state", "position"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
    elif isinstance(data, str) and data:
        fen = data

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    legal = set(board.legal_moves)
    if mv not in legal:
        return next(iter(legal)).uci() if legal else ""
    fmt = (output_format or "uci").strip().lower()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(mv)
        except ValueError:
            return mv.uci()
    return mv.uci()


def _book_move(board: chess.Board, legal_set: dict[str, chess.Move]) -> chess.Move | None:
    if board.fullmove_number > 6:
        return None
    candidates = BOOK.get(board.board_fen() + " " + ("w" if board.turn == chess.WHITE else "b") + " - - 0 1")
    if candidates is None and board.fen() == chess.STARTING_FEN:
        candidates = BOOK[chess.STARTING_FEN]
    if not candidates:
        return None
    for uci in candidates:
        mv = legal_set.get(uci)
        if mv is not None:
            return mv
    return None


def _find_immediate_mate(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move | None:
    for mv in _order_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    ordered = _order_moves(board, legal_moves)
    return ordered[0] if ordered else legal_moves[0]


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    nodes: list[int],
    node_cap: int,
    ply: int,
) -> int:
    nodes[0] += 1
    if nodes[0] % 128 == 0:
        if nodes[0] >= node_cap or time.perf_counter() >= deadline:
            raise TimeoutError

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, nodes, node_cap, ply)

    best = -INF
    moves = list(board.legal_moves)
    if not moves:
        return 0
    for mv in _order_moves(board, moves):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, nodes, node_cap, ply + 1)
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
    deadline: float,
    nodes: list[int],
    node_cap: int,
    ply: int,
) -> int:
    nodes[0] += 1
    if nodes[0] % 128 == 0:
        if nodes[0] >= node_cap or time.perf_counter() >= deadline:
            raise TimeoutError

    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    if ply > 8:
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion:
            tactical.append(mv)
    for mv in _order_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, nodes, node_cap, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    score = _evaluate_white_perspective(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_perspective(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE

    score = 0
    white_bishops = 0
    black_bishops = 0
    for sq, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        positional = _positional_bonus(piece.piece_type, sq, piece.color)
        if piece.color == chess.WHITE:
            score += value + positional
            if piece.piece_type == chess.BISHOP:
                white_bishops += 1
        else:
            score -= value + positional
            if piece.piece_type == chess.BISHOP:
                black_bishops += 1

    if white_bishops >= 2:
        score += 28
    if black_bishops >= 2:
        score -= 28

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

    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 10
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 10
    if board.is_check():
        score += -18 if board.turn == chess.WHITE else 18
    return score


def _positional_bonus(piece_type: int, square: chess.Square, color: chess.Color) -> int:
    sq = square if color == chess.WHITE else chess.square_mirror(square)
    file_idx = chess.square_file(sq)
    rank_idx = chess.square_rank(sq)
    center_distance = abs(file_idx - 3.5) + abs(rank_idx - 3.5)

    if piece_type == chess.PAWN:
        bonus = rank_idx * 7
        if sq in CENTER_SQUARES:
            bonus += 10
        return int(bonus)
    if piece_type == chess.KNIGHT:
        return int(34 - 10 * center_distance)
    if piece_type == chess.BISHOP:
        return int(24 - 6 * center_distance)
    if piece_type == chess.ROOK:
        return 8 if rank_idx >= 4 else 0
    if piece_type == chess.QUEEN:
        return int(8 - 2 * center_distance)
    if piece_type == chess.KING:
        return int(-12 * center_distance) if rank_idx <= 1 else int(6 * (3.5 - center_distance))
    return 0


def _order_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if mv.promotion:
        score += PIECE_VALUES.get(mv.promotion, 0) + 800
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        attacker = board.piece_at(mv.from_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 1000 + 10 * victim_value - attacker_value
    if board.gives_check(mv):
        score += 120
    if mv.to_square in CENTER_SQUARES:
        score += 35
    elif mv.to_square in EXTENDED_CENTER:
        score += 15
    piece = board.piece_at(mv.from_square)
    if piece and piece.piece_type in {chess.KNIGHT, chess.BISHOP} and board.fullmove_number <= 10:
        home_rank = 0 if piece.color == chess.WHITE else 7
        if chess.square_rank(mv.from_square) == home_rank:
            score += 25
    return score
