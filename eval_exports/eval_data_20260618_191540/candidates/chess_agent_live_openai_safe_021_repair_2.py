"""Safe self-contained CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent uses only python-chess, performs bounded deterministic search, and always
validates the chosen move against legal_moves before returning it.
"""

import json
import time
from typing import Any, Optional

import chess


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

MATE_SCORE = 100000
INF = 10**9


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

    selected = _choose_move(board, max(1, int(time_limit_ms or 100)))
    if selected not in legal_moves:
        selected = _fallback_move(board, legal_moves)
    if selected not in legal_moves:
        selected = legal_moves[0]
    return _format_move(board, selected, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    fen = _extract_fen(observation)
    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _extract_fen(observation: Any) -> str:
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and _looks_like_fen(value):
                return value.strip()
        nested = observation.get("observation")
        if nested is not None and nested is not observation:
            return _extract_fen(nested)

    if isinstance(observation, str):
        text = observation.strip()
        if _looks_like_fen(text):
            return text
        try:
            loaded = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return ""
        return _extract_fen(loaded)

    for attr in ("fen", "board"):
        value = getattr(observation, attr, None)
        if callable(value):
            try:
                value = value()
            except (TypeError, ValueError, AttributeError):
                value = None
        if isinstance(value, str) and _looks_like_fen(value):
            return value.strip()
    return ""


def _looks_like_fen(text: str) -> bool:
    parts = text.strip().split()
    return len(parts) >= 4 and "/" in parts[0] and parts[1] in {"w", "b"}


def _format_move(board: chess.Board, selected: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").strip().lower()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(selected)
        except (ValueError, AssertionError):
            return selected.uci()
    return selected.uci()


def _choose_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    mate = _mate_in_one(board)
    if mate is not None:
        return mate

    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    budget = max(0.004, min(time_limit_ms, 250) * 0.72 / 1000.0)
    deadline = time.perf_counter() + budget
    depth = _depth_for_position(board, time_limit_ms)

    best_move = _fallback_move(board, legal_moves)
    ordered = _ordered_moves(board, legal_moves)

    try:
        for current_depth in range(1, depth + 1):
            if time.perf_counter() >= deadline:
                break
            iteration_best = best_move
            iteration_score = -INF
            alpha = -INF
            beta = INF
            for mv in ordered:
                if time.perf_counter() >= deadline:
                    raise TimeoutError
                board.push(mv)
                score = -_negamax(board, current_depth - 1, -beta, -alpha, deadline, 1)
                board.pop()
                score += _root_tiebreak(board, mv)
                if score > iteration_score:
                    iteration_score = score
                    iteration_best = mv
                if score > alpha:
                    alpha = score
            best_move = iteration_best
            ordered = [best_move] + [mv for mv in ordered if mv != best_move]
    except TimeoutError:
        pass

    return best_move


def _depth_for_position(board: chess.Board, time_limit_ms: int) -> int:
    legal_count = board.legal_moves.count()
    material = _non_king_material(board)
    if time_limit_ms < 30:
        return 2
    if time_limit_ms < 80:
        return 3
    if legal_count <= 12 or material <= 2600:
        return 4
    return 3


def _non_king_material(board: chess.Board) -> int:
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        if piece_type == chess.KING:
            continue
        total += value * len(board.pieces(piece_type, chess.WHITE))
        total += value * len(board.pieces(piece_type, chess.BLACK))
    return total


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
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply, 0)

    best = -INF
    for mv in _ordered_moves(board, list(board.legal_moves)):
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
    qply: int,
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if qply >= 6:
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            tactical.append(mv)

    for mv in _ordered_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1, qply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        value += _piece_square_bonus(piece, square)
        value += _activity_bonus(board, piece, square)
        score += value if piece.color == chess.WHITE else -value

    score += _castling_rights_bonus(board, chess.WHITE)
    score -= _castling_rights_bonus(board, chess.BLACK)
    score += _pawn_structure_score(board, chess.WHITE)
    score -= _pawn_structure_score(board, chess.BLACK)

    if board.is_check():
        score += -25 if board.turn == chess.WHITE else 25

    return score if board.turn == chess.WHITE else -score


def _piece_square_bonus(piece: chess.Piece, square: chess.Square) -> int:
    rank = chess.square_rank(square)
    file_index = chess.square_file(square)
    if piece.color == chess.BLACK:
        rank = 7 - rank
    center_distance = abs(file_index - 3.5) + abs(rank - 3.5)
    center_bonus = int(14 - 4 * center_distance)

    if piece.piece_type == chess.PAWN:
        return rank * 5 + max(0, center_bonus // 2)
    if piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        return center_bonus * 2
    if piece.piece_type == chess.ROOK:
        return 4 if rank >= 6 else 0
    if piece.piece_type == chess.QUEEN:
        return center_bonus // 2
    if piece.piece_type == chess.KING:
        return _king_square_bonus(rank, file_index)
    return 0


def _king_square_bonus(rank: int, file_index: int) -> int:
    if rank <= 1 and file_index in {0, 1, 2, 5, 6, 7}:
        return 18
    if rank <= 1:
        return 8
    return -rank * 6


def _activity_bonus(board: chess.Board, piece: chess.Piece, square: chess.Square) -> int:
    if piece.piece_type == chess.PAWN:
        return 0
    if piece.piece_type == chess.KING:
        return 0
    attack_count = len(board.attacks(square))
    if piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        return min(20, attack_count * 2)
    if piece.piece_type == chess.ROOK:
        return min(16, attack_count)
    if piece.piece_type == chess.QUEEN:
        return min(14, attack_count)
    return 0


def _castling_rights_bonus(board: chess.Board, color: chess.Color) -> int:
    king_side = board.has_kingside_castling_rights(color)
    queen_side = board.has_queenside_castling_rights(color)
    return 10 if king_side or queen_side else 0


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    if not pawns:
        return 0
    files = [chess.square_file(square) for square in pawns]
    score = 0
    for square in pawns:
        file_index = chess.square_file(square)
        rank = chess.square_rank(square)
        advance = rank if color == chess.WHITE else 7 - rank
        score += advance * 2
        if files.count(file_index) > 1:
            score -= 8
        neighbor = file_index - 1 in files or file_index + 1 in files
        if not neighbor:
            score -= 7
    return score


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(mv.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 10000 + 10 * victim_value - attacker_value
    if mv.promotion:
        score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.gives_check(mv):
        score += 2500
    if board.is_castling(mv):
        score += 700

    to_file = chess.square_file(mv.to_square)
    to_rank = chess.square_rank(mv.to_square)
    if 2 <= to_file <= 5 and 2 <= to_rank <= 5:
        score += 90

    piece = board.piece_at(mv.from_square)
    if piece and piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        home_rank = 0 if piece.color == chess.WHITE else 7
        if chess.square_rank(mv.from_square) == home_rank:
            score += 120
    if piece and piece.piece_type == chess.PAWN:
        if mv.from_square in {chess.E2, chess.D2, chess.E7, chess.D7}:
            score += 45
    if piece and piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
        score -= 80
    return score


def _root_tiebreak(board: chess.Board, mv: chess.Move) -> int:
    mover = board.piece_at(mv.from_square)
    if mover is None:
        return 0

    score = 0
    board.push(mv)
    try:
        attackers = board.attackers(not mover.color, mv.to_square)
        if attackers:
            values = []
            for square in attackers:
                attacker = board.piece_at(square)
                if attacker is not None:
                    values.append(PIECE_VALUES.get(attacker.piece_type, 0))
            if values:
                lowest_attacker = min(values)
                moved_value = PIECE_VALUES.get(mover.piece_type, 0)
                if moved_value > lowest_attacker:
                    score -= min(120, (moved_value - lowest_attacker) // 4)
    finally:
        board.pop()
    return score


def _mate_in_one(board: chess.Board) -> Optional[chess.Move]:
    for mv in _ordered_moves(board, list(board.legal_moves)):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    mate = _mate_in_one(board)
    if mate is not None:
        return mate

    best = legal_moves[0]
    best_score = -INF
    for mv in legal_moves:
        score = _move_order_score(board, mv)
        board.push(mv)
        if board.is_checkmate():
            score += MATE_SCORE
        elif board.is_stalemate():
            score -= 50
        else:
            score += -_evaluate_for_side_to_move(board) // 20
        board.pop()
        if score > best_score:
            best_score = score
            best = mv
    return best
