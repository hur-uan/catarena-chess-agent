"""Safe standalone CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent uses only python-chess, performs no file/network/subprocess access,
and always validates selected moves against legal_moves.
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


class SearchLimits:
    """Plain limits container; avoids dataclass import-loader edge cases."""

    def __init__(self, deadline: float, root_depth: int, q_depth: int) -> None:
        self.deadline = deadline
        self.root_depth = root_depth
        self.q_depth = q_depth


class _Timeout(Exception):
    pass


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

    immediate = _immediate_tactical_move(board, legal_moves)
    if immediate is not None:
        return _format_move(board, immediate, output_format)

    safe_ms = max(5, int(time_limit_ms or 100))
    budget = max(0.004, (safe_ms - 8) / 1000.0)
    limits = SearchLimits(time.perf_counter() + budget, _depth_for(board, legal_moves, safe_ms), 4)

    chosen = _book_move(board)
    if chosen is None:
        chosen = _search_best_move(board, legal_moves, limits)
    if chosen not in legal_moves:
        chosen = _fallback_move(board, legal_moves)
    return _format_move(board, chosen, output_format)


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
    if isinstance(observation, str):
        fen = observation.strip() or None
    elif isinstance(observation, dict):
        fen = _fen_from_dict(observation)
    else:
        value = getattr(observation, "fen", None)
        if callable(value):
            try:
                fen = value()
            except (TypeError, ValueError, AttributeError):
                fen = None
        elif isinstance(value, str):
            fen = value

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _fen_from_dict(data: dict[str, Any]) -> str | None:
    for key in ("fen", "board", "state", "position"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = data.get("observation")
    if isinstance(nested, dict):
        return _fen_from_dict(nested)
    return None


def _format_move(board: chess.Board, selected: chess.Move, output_format: str) -> str:
    if selected not in board.legal_moves:
        legal = list(board.legal_moves)
        if not legal:
            return ""
        selected = legal[0]
    fmt = (output_format or "uci").lower().strip()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(selected)
        except (ValueError, AssertionError):
            return selected.uci()
    return selected.uci()


def _depth_for(board: chess.Board, legal_moves: list[chess.Move], safe_ms: int) -> int:
    depth = 2
    if safe_ms >= 70 and len(legal_moves) <= 48:
        depth = 3
    if safe_ms >= 140 and len(legal_moves) <= 32:
        depth = 4
    if board.fullmove_number <= 8 and safe_ms < 120:
        depth = min(depth, 3)
    return depth


def _book_move(board: chess.Board) -> chess.Move | None:
    if board.fullmove_number > 6:
        return None
    key = " ".join(board.fen().split()[:4])
    book = {
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -": (
            "e2e4",
            "d2d4",
            "g1f3",
        ),
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -": (
            "c7c5",
            "e7e5",
            "e7e6",
        ),
        "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq -": (
            "g8f6",
            "d7d5",
            "e7e6",
        ),
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": (
            "g1f3",
            "b1c3",
            "f1c4",
        ),
    }
    legal = set(board.legal_moves)
    for uci in book.get(key, ()):
        mv = chess.Move.from_uci(uci)
        if mv in legal:
            return mv
    return None


def _immediate_tactical_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move | None:
    best_mate = None
    best_capture = None
    best_capture_score = -INF
    for mv in legal_moves:
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
        if board.is_capture(mv) or mv.promotion is not None:
            score = _move_order_score(board, mv)
            if score > best_capture_score:
                best_capture_score = score
                best_capture = mv
    if best_mate is not None:
        return best_mate
    if best_capture is not None and best_capture_score >= 15000:
        return best_capture
    return None


def _search_best_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
    limits: SearchLimits,
) -> chess.Move:
    best = _fallback_move(board, legal_moves)
    ordered = _ordered_moves(board, legal_moves)

    try:
        for depth in range(1, limits.root_depth + 1):
            if time.perf_counter() >= limits.deadline:
                break
            current_best = best
            current_score = -INF
            alpha = -INF
            beta = INF
            for mv in ordered:
                _check_time(limits)
                board.push(mv)
                score = -_negamax(board, depth - 1, -beta, -alpha, limits, 1)
                board.pop()
                better_tie = _move_tiebreak(board, mv) > _move_tiebreak(board, current_best)
                if score > current_score or (score == current_score and better_tie):
                    current_score = score
                    current_best = mv
                alpha = max(alpha, current_score)
            best = current_best
            ordered = [best] + [mv for mv in ordered if mv != best]
            if current_score >= MATE_SCORE - 32:
                break
    except _Timeout:
        pass
    return best if best in legal_moves else _fallback_move(board, legal_moves)


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    limits: SearchLimits,
    ply: int,
) -> int:
    _check_time(limits)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if _is_drawish(board):
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, limits, limits.q_depth, ply)

    best = -INF
    for mv in _ordered_moves(board, list(board.legal_moves)):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, limits, ply + 1)
        board.pop()
        best = max(best, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break
    return best


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    limits: SearchLimits,
    depth: int,
    ply: int,
) -> int:
    _check_time(limits)
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _static_score_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    alpha = max(alpha, stand_pat)
    if depth <= 0:
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion is not None:
            tactical.append(mv)
        elif board.is_check() and len(tactical) < 10:
            tactical.append(mv)

    for mv in _ordered_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, limits, depth - 1, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        alpha = max(alpha, score)
    return alpha


def _is_drawish(board: chess.Board) -> bool:
    return (
        board.is_stalemate()
        or board.is_insufficient_material()
        or board.can_claim_fifty_moves()
        or board.can_claim_threefold_repetition()
    )


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if mv.promotion is not None:
        score += 9000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.is_capture(mv):
        victim = board.piece_type_at(mv.to_square)
        if victim is None and board.is_en_passant(mv):
            victim = chess.PAWN
        attacker = board.piece_type_at(mv.from_square)
        score += 6000 + 10 * PIECE_VALUES.get(victim, 0)
        score -= PIECE_VALUES.get(attacker, 0)
    try:
        if board.gives_check(mv):
            score += 2500
    except AssertionError:
        pass
    if board.is_castling(mv):
        score += 700

    piece = board.piece_at(mv.from_square)
    if piece is not None:
        if mv.to_square in CENTER:
            score += 180
        elif mv.to_square in EXTENDED_CENTER:
            score += 70
        if board.fullmove_number <= 10:
            score += _opening_move_bonus(piece, mv)
    return score


def _opening_move_bonus(piece: chess.Piece, mv: chess.Move) -> int:
    bonus = 0
    if piece.color == chess.WHITE:
        home = {chess.B1, chess.G1, chess.C1, chess.F1}
    else:
        home = {chess.B8, chess.G8, chess.C8, chess.F8}
    if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and mv.from_square in home:
        bonus += 260
    if piece.piece_type == chess.QUEEN:
        bonus -= 180
    if piece.piece_type == chess.ROOK:
        bonus -= 100
    return bonus


def _move_tiebreak(board: chess.Board, mv: chess.Move) -> int:
    return _move_order_score(board, mv) + (63 - mv.from_square) + mv.to_square


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    return max(legal_moves, key=lambda mv: _move_order_score(board, mv))


def _check_time(limits: SearchLimits) -> None:
    if time.perf_counter() >= limits.deadline:
        raise _Timeout


def _static_score_for_side_to_move(board: chess.Board) -> int:
    score = _evaluate_white_minus_black(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_minus_black(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    non_king_material = 0
    pieces = board.piece_map()
    for square, piece in pieces.items():
        value = PIECE_VALUES[piece.piece_type]
        if piece.piece_type != chess.KING:
            non_king_material += value
        term = value + _piece_square_bonus(square, piece, non_king_material)
        score += term if piece.color == chess.WHITE else -term

    score += _bishop_pair_bonus(board, chess.WHITE) - _bishop_pair_bonus(board, chess.BLACK)
    score += _pawn_structure_score(board, chess.WHITE) - _pawn_structure_score(board, chess.BLACK)
    score += _king_safety_score(board, chess.WHITE) - _king_safety_score(board, chess.BLACK)
    score += _development_score(board, chess.WHITE) - _development_score(board, chess.BLACK)
    score += 2 * (_mobility(board, chess.WHITE) - _mobility(board, chess.BLACK))

    if board.turn == chess.WHITE and board.is_check():
        score -= 25
    elif board.turn == chess.BLACK and board.is_check():
        score += 25
    return int(max(-MATE_SCORE + 1000, min(MATE_SCORE - 1000, score)))


def _piece_square_bonus(square: chess.Square, piece: chess.Piece, material: int) -> int:
    sq = square if piece.color == chess.WHITE else chess.square_mirror(square)
    file_idx = chess.square_file(sq)
    rank_idx = chess.square_rank(sq)
    center_dist = abs(file_idx - 3.5) + abs(rank_idx - 3.5)

    if piece.piece_type == chess.PAWN:
        return int(rank_idx * 7 - center_dist * 3)
    if piece.piece_type == chess.KNIGHT:
        return int(32 - center_dist * 10)
    if piece.piece_type == chess.BISHOP:
        return int(24 - center_dist * 6)
    if piece.piece_type == chess.ROOK:
        return int(4 * rank_idx - abs(file_idx - 3.5) * 2)
    if piece.piece_type == chess.QUEEN:
        return int(12 - center_dist * 3)
    if material <= 2600:
        return int(30 - center_dist * 8)
    return int(-12 * rank_idx - center_dist * 4)


def _bishop_pair_bonus(board: chess.Board, color: chess.Color) -> int:
    return 35 if len(board.pieces(chess.BISHOP, color)) >= 2 else 0


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    if not pawns:
        return 0
    files = [chess.square_file(sq) for sq in pawns]
    occupied_files = set(files)
    score = 0
    for file_idx in range(8):
        count = files.count(file_idx)
        if count > 1:
            score -= 14 * (count - 1)
    for sq in pawns:
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        if file_idx - 1 not in occupied_files and file_idx + 1 not in occupied_files:
            score -= 10
        score += 3 * (rank_idx if color == chess.WHITE else 7 - rank_idx)
    return score


def _king_safety_score(board: chess.Board, color: chess.Color) -> int:
    king = board.king(color)
    if king is None:
        return -500
    enemy = not color
    score = 0
    for sq in chess.SquareSet(chess.BB_KING_ATTACKS[king]):
        if board.is_attacked_by(enemy, sq):
            score -= 9

    rank_dir = 1 if color == chess.WHITE else -1
    king_file = chess.square_file(king)
    king_rank = chess.square_rank(king)
    for df in (-1, 0, 1):
        file_idx = king_file + df
        rank_idx = king_rank + rank_dir
        if 0 <= file_idx <= 7 and 0 <= rank_idx <= 7:
            piece = board.piece_at(chess.square(file_idx, rank_idx))
            if piece is not None and piece.color == color and piece.piece_type == chess.PAWN:
                score += 12
    if board.has_kingside_castling_rights(color) or board.has_queenside_castling_rights(color):
        score += 8
    return score


def _development_score(board: chess.Board, color: chess.Color) -> int:
    if board.fullmove_number > 16:
        return 0
    score = 0
    if color == chess.WHITE:
        home_minor = [chess.B1, chess.G1, chess.C1, chess.F1]
        queen_home = chess.D1
    else:
        home_minor = [chess.B8, chess.G8, chess.C8, chess.F8]
        queen_home = chess.D8
    for sq in home_minor:
        piece = board.piece_at(sq)
        is_home_minor = (
            piece is not None
            and piece.color == color
            and piece.piece_type in (chess.KNIGHT, chess.BISHOP)
        )
        if is_home_minor:
            score -= 18
    queen = board.piece_at(queen_home)
    if queen is None or queen.color != color or queen.piece_type != chess.QUEEN:
        score -= 6
    return score


def _mobility(board: chess.Board, color: chess.Color) -> int:
    temp = board.copy(stack=False)
    temp.turn = color
    if temp.king(color) is None:
        return 0
    try:
        return min(60, temp.legal_moves.count())
    except (ValueError, AssertionError):
        return 0
