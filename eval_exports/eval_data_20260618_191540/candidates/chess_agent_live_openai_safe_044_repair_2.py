"""Safe standalone CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This module is deterministic, bounded, and uses only python-chess. It performs no
network calls, file I/O, subprocess calls, dynamic imports, eval/exec, or
self-modifying behavior during a match.
"""

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

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
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

# Legal-only opening preferences. These are not an external book; they simply
# break ties toward solid development in the first few moves.
OPENING_PRIORITIES = (
    "e2e4",
    "d2d4",
    "g1f3",
    "c2c4",
    "b1c3",
    "e7e5",
    "d7d5",
    "g8f6",
    "c7c5",
    "b8c6",
    "f1c4",
    "f8c5",
    "f1b5",
    "f8b4",
    "g2g3",
    "g7g6",
)


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
    """Choose a legal move for the supplied observation."""
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    try:
        chosen = _choose_move(board, max(1, int(time_limit_ms)))
    except Exception:
        chosen = None

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
    """Extract a board from common CATArena payload shapes."""
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "state", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
    elif isinstance(observation, str) and observation.strip():
        fen = observation.strip()

    if fen:
        try:
            return chess.Board(fen)
        except Exception:
            pass
    return chess.Board()


def _choose_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    mate_move = _find_immediate_mate(board, legal_moves)
    if mate_move is not None:
        return mate_move

    book_move = _opening_move(board, legal_moves)
    if book_move is not None and time_limit_ms <= 25:
        return book_move

    budget = max(0.005, (time_limit_ms - 3) / 1000.0)
    deadline = time.monotonic() + budget

    best_move = book_move if book_move is not None else _fallback_move(board, legal_moves)
    best_score = -INF

    if time_limit_ms < 35:
        max_depth = 1
    elif time_limit_ms < 90:
        max_depth = 2
    else:
        max_depth = 3

    ordered_root = _ordered_moves(board, legal_moves)
    for depth in range(1, max_depth + 1):
        if time.monotonic() >= deadline:
            break
        completed = True
        local_best = best_move
        local_score = -INF
        alpha = -INF
        beta = INF
        for mv in ordered_root:
            if time.monotonic() >= deadline:
                completed = False
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -beta, -alpha, deadline, 0)
            board.pop()
            if score > local_score or (score == local_score and mv.uci() < local_best.uci()):
                local_score = score
                local_best = mv
            if score > alpha:
                alpha = score
        if completed:
            best_move = local_best
            best_score = local_score
            if best_score >= MATE_SCORE - 1000:
                break
        else:
            break

    return best_move


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> int:
    if time.monotonic() >= deadline:
        return _evaluate_for_side_to_move(board)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply, 4)

    best = -INF
    legal_moves = list(board.legal_moves)
    for mv in _ordered_moves(board, legal_moves):
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


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
    qdepth: int,
) -> int:
    if time.monotonic() >= deadline:
        return _evaluate_for_side_to_move(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if qdepth <= 0:
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion:
            tactical.append(mv)

    for mv in _ordered_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1, qdepth - 1)
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
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        value = PIECE_VALUES[piece.piece_type]
        score += sign * value
        score += sign * _piece_square_bonus(piece, square)

    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        score += 25
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        score -= 25

    if _has_any_castling_right(board, chess.WHITE):
        score += 8
    if _has_any_castling_right(board, chess.BLACK):
        score -= 8

    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)
    if white_king in (chess.G1, chess.C1):
        score += 18
    if black_king in (chess.G8, chess.C8):
        score -= 18

    score += _pawn_structure_score(board, chess.WHITE)
    score -= _pawn_structure_score(board, chess.BLACK)

    score += 2 * _safe_mobility_difference(board)
    return score


def _has_any_castling_right(board: chess.Board, color: chess.Color) -> bool:
    return board.has_kingside_castling_rights(color) or board.has_queenside_castling_rights(
        color
    )


def _safe_mobility_difference(board: chess.Board) -> int:
    original_turn = board.turn
    white_mob = 0
    black_mob = 0
    try:
        board.turn = chess.WHITE
        white_mob = board.legal_moves.count()
        board.turn = chess.BLACK
        black_mob = board.legal_moves.count()
    except Exception:
        white_mob = 0
        black_mob = 0
    finally:
        board.turn = original_turn
    return white_mob - black_mob


def _piece_square_bonus(piece: chess.Piece, square: chess.Square) -> int:
    rank = chess.square_rank(square)
    file = chess.square_file(square)
    if piece.color == chess.BLACK:
        rank = 7 - rank

    center_distance = abs(file - 3.5) + abs(rank - 3.5)
    bonus = 0

    if piece.piece_type == chess.PAWN:
        bonus += rank * 4
        if square in CENTER_SQUARES:
            bonus += 8
    elif piece.piece_type == chess.KNIGHT:
        bonus += int(24 - 6 * center_distance)
        if rank >= 2:
            bonus += 6
    elif piece.piece_type == chess.BISHOP:
        bonus += int(18 - 4 * center_distance)
        if rank >= 2:
            bonus += 4
    elif piece.piece_type == chess.ROOK:
        bonus += 4 if rank >= 3 else 0
        bonus += 10 if rank == 6 else 0
    elif piece.piece_type == chess.QUEEN:
        bonus += int(8 - 2 * center_distance)
    elif piece.piece_type == chess.KING:
        bonus -= int(4 * max(0, 3 - rank))
    return bonus


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    files = [chess.square_file(sq) for sq in pawns]
    score = 0
    for file_index in range(8):
        count = files.count(file_index)
        if count > 1:
            score -= 10 * (count - 1)
    occupied_files = set(files)
    for file_index in files:
        if file_index - 1 not in occupied_files and file_index + 1 not in occupied_files:
            score -= 8
    return score


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: (-_move_order_score(board, mv), mv.uci()))


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_at(mv.from_square)
    captured_piece = board.piece_at(mv.to_square)

    if board.is_capture(mv):
        if captured_piece is None and board.is_en_passant(mv):
            captured_value = PIECE_VALUES[chess.PAWN]
        else:
            captured_value = 0
            if captured_piece is not None:
                captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
        attacker_value = 0
        if moving_piece is not None:
            attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0)
        score += 10000 + 10 * captured_value - attacker_value

    if mv.promotion:
        score += 9000 + PIECE_VALUES.get(mv.promotion, 0)

    if board.gives_check(mv):
        score += 2500

    if board.is_castling(mv):
        score += 1200

    if mv.to_square in CENTER_SQUARES:
        score += 220
    elif mv.to_square in EXTENDED_CENTER:
        score += 80

    if moving_piece is not None:
        if _is_early_minor_development(board, moving_piece, mv):
            score += 350
        if moving_piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 120
        if moving_piece.piece_type == chess.ROOK and board.fullmove_number <= 8:
            score -= 60

    return score


def _is_early_minor_development(
    board: chess.Board,
    moving_piece: chess.Piece,
    mv: chess.Move,
) -> bool:
    if moving_piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return False
    if board.fullmove_number > 10:
        return False
    home_rank = 0 if moving_piece.color == chess.WHITE else 7
    return chess.square_rank(mv.from_square) == home_rank


def _find_immediate_mate(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move | None:
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _opening_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move | None:
    if board.fullmove_number > 4:
        return None
    legal_by_uci = {mv.uci(): mv for mv in legal_moves}
    for uci in OPENING_PRIORITIES:
        mv = legal_by_uci.get(uci)
        if mv is not None:
            return mv
    return None


def _fallback_move(
    board: chess.Board,
    legal_moves: list[chess.Move] | None = None,
) -> chess.Move:
    moves = legal_moves if legal_moves is not None else list(board.legal_moves)
    if not moves:
        return chess.Move.null()
    return _ordered_moves(board, list(moves))[0]
