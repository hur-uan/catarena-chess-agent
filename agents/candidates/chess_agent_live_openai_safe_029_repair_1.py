"""Safe self-contained CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

No network calls, subprocesses, file I/O, eval/exec, or dynamic imports are used.
Every returned move is checked against python-chess legal_moves, with a legal
fallback if anything unexpected happens.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
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

OPENING_MOVES = (
    "e2e4",
    "d2d4",
    "g1f3",
    "c2c4",
    "e7e5",
    "d7d5",
    "g8f6",
    "c7c5",
)


@dataclass
class SearchLimits:
    deadline: float
    node_limit: int
    nodes: int = 0
    stopped: bool = False


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
        chosen = _choose_move(board, legal_moves, time_limit_ms)
    except Exception:
        chosen = _fallback_move(board, legal_moves)

    if chosen not in legal_moves:
        chosen = _fallback_move(board, legal_moves)

    fmt = str(output_format or "uci").strip().lower()
    if fmt in {"san", "algebraic"}:
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
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    moves: list[str] = []

    if isinstance(observation, dict):
        for key in ("fen", "board", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        raw_moves = observation.get("moves")
        if raw_moves is None:
            raw_moves = observation.get("move_history")
        if raw_moves is None:
            raw_moves = observation.get("history")
        moves = _parse_move_history(raw_moves)
    elif isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text
    else:
        maybe_fen = getattr(observation, "fen", None)
        if isinstance(maybe_fen, str) and maybe_fen.strip():
            fen = maybe_fen.strip()

    try:
        board = chess.Board(fen) if fen else chess.Board()
    except Exception:
        board = chess.Board()

    for text_move in moves:
        try:
            parsed = chess.Move.from_uci(text_move)
        except Exception:
            continue
        if parsed in board.legal_moves:
            board.push(parsed)
    return board


def _parse_move_history(raw_moves: Any) -> list[str]:
    if isinstance(raw_moves, str):
        tokens: list[str] = []
        current: list[str] = []
        for char in raw_moves:
            if char == "," or char.isspace():
                if current:
                    tokens.append("".join(current).strip())
                    current = []
            else:
                current.append(char)
        if current:
            tokens.append("".join(current).strip())
        return [token for token in tokens if token]
    if isinstance(raw_moves, (list, tuple)):
        return [str(item).strip() for item in raw_moves if str(item).strip()]
    return []


def _choose_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
    time_limit_ms: int,
) -> chess.Move:
    mate_move = _find_immediate_mate(board, legal_moves)
    if mate_move is not None:
        return mate_move

    book_move = _opening_move(board, legal_moves)
    if book_move is not None:
        return book_move

    safe_ms = max(8, min(int(time_limit_ms or 100), 250))
    margin = 0.006 if safe_ms >= 40 else 0.003
    deadline = time.perf_counter() + max(0.004, safe_ms / 1000.0 - margin)
    if safe_ms < 60:
        node_limit = 1800
    elif safe_ms < 120:
        node_limit = 5000
    else:
        node_limit = 9000
    limits = SearchLimits(deadline=deadline, node_limit=node_limit)

    best_move = _best_static_move(board, legal_moves)
    best_score = -INF
    max_depth = _depth_for(board, safe_ms)
    ordered = _order_moves(board, legal_moves)

    for depth in range(1, max_depth + 1):
        if _time_up(limits):
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        beta = INF
        for mv in ordered:
            if _time_up(limits):
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -beta, -alpha, limits, 0)
            board.pop()
            if limits.stopped:
                break
            if score > current_score:
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score
        if not limits.stopped and current_best in legal_moves:
            best_move = current_best
            best_score = current_score
            ordered = [best_move] + [mv for mv in ordered if mv != best_move]
        if best_score > MATE_SCORE - 1000:
            break

    if best_move in legal_moves:
        return best_move
    return _fallback_move(board, legal_moves)


def _opening_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move | None:
    if board.fullmove_number > 2 or len(board.move_stack) > 2:
        return None
    legal_set = set(legal_moves)
    for text_move in OPENING_MOVES:
        mv = chess.Move.from_uci(text_move)
        if mv in legal_set:
            return mv
    return None


def _depth_for(board: chess.Board, safe_ms: int) -> int:
    pieces = len(board.piece_map())
    if safe_ms < 35:
        return 1
    if safe_ms < 80:
        return 2
    if pieces <= 12 and safe_ms >= 90:
        return 4
    return 3


def _time_up(limits: SearchLimits) -> bool:
    if limits.stopped:
        return True
    if limits.nodes >= limits.node_limit:
        limits.stopped = True
        return True
    if limits.nodes % 128 == 0 and time.perf_counter() >= limits.deadline:
        limits.stopped = True
        return True
    return False


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    limits: SearchLimits,
    ply: int,
) -> int:
    limits.nodes += 1
    if _time_up(limits):
        return _evaluate_for_turn(board)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if _is_drawish(board):
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, limits, ply, 0)

    best = -INF
    legal = list(board.legal_moves)
    if not legal:
        return _evaluate_for_turn(board)

    for mv in _order_moves(board, legal):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, limits, ply + 1)
        board.pop()
        if limits.stopped:
            return score
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
    limits: SearchLimits,
    ply: int,
    qdepth: int,
) -> int:
    limits.nodes += 1
    stand_pat = _evaluate_for_turn(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if qdepth >= 4 or _time_up(limits):
        return alpha

    tactical: list[chess.Move] = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion is not None:
            tactical.append(mv)
        elif board.is_check() and qdepth < 2:
            tactical.append(mv)

    for mv in _order_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, limits, ply + 1, qdepth + 1)
        board.pop()
        if limits.stopped:
            return alpha
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _is_drawish(board: chess.Board) -> bool:
    return (
        board.is_stalemate()
        or board.is_insufficient_material()
        or board.can_claim_fifty_moves()
        or board.can_claim_threefold_repetition()
    )


def _find_immediate_mate(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move | None:
    for mv in _order_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _best_static_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move:
    best = legal_moves[0]
    best_score = -INF
    for mv in _order_moves(board, legal_moves):
        board.push(mv)
        if board.is_checkmate():
            score = MATE_SCORE
        elif board.is_stalemate():
            score = 0
        else:
            score = -_evaluate_for_turn(board)
        board.pop()
        if score > best_score:
            best_score = score
            best = mv
    return best


def _fallback_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move:
    return sorted(legal_moves, key=lambda mv: (-_move_order_score(board, mv), mv.uci()))[0]


def _order_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: (-_move_order_score(board, mv), mv.uci()))


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    moving = board.piece_at(mv.from_square)
    victim = board.piece_at(mv.to_square)

    if board.is_capture(mv):
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker_value = PIECE_VALUES.get(moving.piece_type, 0) if moving else 0
        score += 10000 + 10 * victim_value - attacker_value

    if mv.promotion is not None:
        score += 9000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.gives_check(mv):
        score += 3500
    if board.is_castling(mv):
        score += 800
    if mv.to_square in CENTER_SQUARES:
        score += 160
    elif mv.to_square in EXTENDED_CENTER:
        score += 60

    if moving is not None:
        if moving.piece_type in (chess.KNIGHT, chess.BISHOP):
            home_rank = 0 if moving.color == chess.WHITE else 7
            if board.fullmove_number <= 12:
                if chess.square_rank(mv.from_square) == home_rank:
                    score += 220
        if moving.piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 90
    return score


def _evaluate_for_turn(board: chess.Board) -> int:
    score = _evaluate_white_perspective(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_perspective(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    endgame = _is_endgame(board)
    for sq, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        score += sign * PIECE_VALUES[piece.piece_type]
        score += sign * _piece_square_value(piece, sq, endgame)

    score += _bishop_pair_bonus(board, chess.WHITE)
    score -= _bishop_pair_bonus(board, chess.BLACK)
    score += _rook_file_bonus(board, chess.WHITE)
    score -= _rook_file_bonus(board, chess.BLACK)
    score += _pawn_structure_score(board, chess.WHITE)
    score -= _pawn_structure_score(board, chess.BLACK)
    score += _king_safety_score(board, chess.WHITE)
    score -= _king_safety_score(board, chess.BLACK)
    score += 2 * (_pseudo_mobility(board, chess.WHITE) - _pseudo_mobility(board, chess.BLACK))

    if board.turn == chess.WHITE and board.is_check():
        score -= 25
    elif board.turn == chess.BLACK and board.is_check():
        score += 25
    return score


def _piece_square_value(piece: chess.Piece, sq: chess.Square, endgame: bool) -> int:
    file_index = chess.square_file(sq)
    rank = chess.square_rank(sq)
    if piece.color == chess.BLACK:
        rank = 7 - rank
    center_file_dist = abs(file_index - 3.5)
    center_rank_dist = abs(rank - 3.5)
    center_bonus = int(14 - 4 * (center_file_dist + center_rank_dist))

    if piece.piece_type == chess.PAWN:
        return rank * 5 + (8 if file_index in (3, 4) else 0)
    if piece.piece_type == chess.KNIGHT:
        return center_bonus * 3 - (10 if rank in (0, 7) else 0)
    if piece.piece_type == chess.BISHOP:
        return center_bonus * 2
    if piece.piece_type == chess.ROOK:
        return 8 if rank in (6, 7) else 0
    if piece.piece_type == chess.QUEEN:
        return center_bonus
    if piece.piece_type == chess.KING:
        if endgame:
            return center_bonus * 2
        return 18 if file_index in (0, 1, 6, 7) and rank in (0, 1) else -center_bonus
    return 0


def _is_endgame(board: chess.Board) -> bool:
    material = 0
    for piece_type, value in PIECE_VALUES.items():
        if piece_type in (chess.PAWN, chess.KING):
            continue
        white_count = len(board.pieces(piece_type, chess.WHITE))
        black_count = len(board.pieces(piece_type, chess.BLACK))
        material += value * (white_count + black_count)
    queens = len(board.pieces(chess.QUEEN, chess.WHITE))
    queens += len(board.pieces(chess.QUEEN, chess.BLACK))
    return queens == 0 or material <= 2600


def _bishop_pair_bonus(board: chess.Board, color: chess.Color) -> int:
    return 35 if len(board.pieces(chess.BISHOP, color)) >= 2 else 0


def _rook_file_bonus(board: chess.Board, color: chess.Color) -> int:
    bonus = 0
    enemy = not color
    own_pawns_by_file = _pawn_file_counts(board, color)
    enemy_pawns_by_file = _pawn_file_counts(board, enemy)
    for rook_sq in board.pieces(chess.ROOK, color):
        file_index = chess.square_file(rook_sq)
        own_pawns = own_pawns_by_file.get(file_index, 0)
        enemy_pawns = enemy_pawns_by_file.get(file_index, 0)
        if own_pawns == 0 and enemy_pawns == 0:
            bonus += 24
        elif own_pawns == 0:
            bonus += 12
    return bonus


def _pawn_file_counts(board: chess.Board, color: chess.Color) -> dict[int, int]:
    files: dict[int, int] = {}
    for sq in board.pieces(chess.PAWN, color):
        file_index = chess.square_file(sq)
        files[file_index] = files.get(file_index, 0) + 1
    return files


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    files = _pawn_file_counts(board, color)
    score = 0
    for sq in pawns:
        file_index = chess.square_file(sq)
        rank = chess.square_rank(sq)
        advancement = rank if color == chess.WHITE else 7 - rank
        score += advancement * 3
        if files.get(file_index, 0) > 1:
            score -= 10
        if files.get(file_index - 1, 0) == 0 and files.get(file_index + 1, 0) == 0:
            score -= 12
    return score


def _king_safety_score(board: chess.Board, color: chess.Color) -> int:
    king_sq = board.king(color)
    if king_sq is None:
        return -500
    enemy = not color
    score = 0
    direction = 1 if color == chess.WHITE else -1
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)

    for df in (-1, 0, 1):
        file_index = king_file + df
        rank = king_rank + direction
        if 0 <= file_index <= 7 and 0 <= rank <= 7:
            sq = chess.square(file_index, rank)
            piece = board.piece_at(sq)
            if piece and piece.color == color and piece.piece_type == chess.PAWN:
                score += 12

    ring = chess.SquareSet(chess.BB_KING_ATTACKS[king_sq])
    attacked = 0
    for sq in ring:
        if board.is_attacked_by(enemy, sq):
            attacked += 1
    score -= 7 * attacked
    if board.is_attacked_by(enemy, king_sq):
        score -= 35
    return score


def _pseudo_mobility(board: chess.Board, color: chess.Color) -> int:
    saved_turn = board.turn
    board.turn = color
    try:
        count = 0
        for _ in board.legal_moves:
            count += 1
            if count >= 40:
                break
        return count
    finally:
        board.turn = saved_turn
