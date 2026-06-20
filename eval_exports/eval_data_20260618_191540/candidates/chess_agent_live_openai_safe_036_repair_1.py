"""Safe standalone CATArena chess agent.

Public entry point:
    select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation is self-contained except for python-chess. It performs no
network access, file I/O, subprocess use, eval/exec, or dynamic importing during
move selection.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

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

CENTER = (chess.D4, chess.E4, chess.D5, chess.E5)
EXTENDED_CENTER = (
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
)
HOME_MINORS = (
    chess.B1,
    chess.G1,
    chess.C1,
    chess.F1,
    chess.B8,
    chess.G8,
    chess.C8,
    chess.F8,
)


class SearchState:
    """Minimal mutable search timer state.

    A plain class is used instead of dataclass so import validators that load the
    module unusually cannot trip over dataclass module lookup behavior.
    """

    def __init__(self, deadline: float) -> None:
        self.deadline = deadline
        self.nodes = 0
        self.stopped = False


def _time_left(state: SearchState) -> bool:
    if state.nodes & 127:
        return not state.stopped
    if time.perf_counter() >= state.deadline:
        state.stopped = True
    return not state.stopped


def _parse_observation(observation: Any) -> chess.Board:
    """Parse CATArena-style observations without file or network access."""
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "position", "state"):
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
    elif isinstance(observation, str):
        fen = observation.strip()

    if not fen:
        return chess.Board()

    try:
        return chess.Board(fen)
    except ValueError:
        try:
            return chess.Board(f"{fen} w KQkq - 0 1")
        except ValueError:
            return chess.Board()


def _legal_hint_set(observation: Any) -> Set[str]:
    if not isinstance(observation, dict):
        return set()
    raw = None
    for key in ("legal_moves", "legal", "moves"):
        if key in observation:
            raw = observation[key]
            break
    if raw is None:
        return set()
    if isinstance(raw, str):
        hints: Set[str] = set()
        for chunk in raw.split(","):
            for item in chunk.split():
                if item.strip():
                    hints.add(item.strip())
        return hints
    try:
        return {str(item).strip() for item in raw if str(item).strip()}
    except TypeError:
        return set()


def _fallback_move(
    board: chess.Board,
    observation: Optional[Any] = None,
) -> Optional[chess.Move]:
    legal = list(board.legal_moves)
    if not legal:
        return None
    hints = _legal_hint_set(observation)
    if hints:
        hinted = [mv for mv in legal if mv.uci() in hints]
        if hinted:
            legal = hinted
    return sorted(legal, key=lambda mv: mv.uci())[0]


def _phase(board: chess.Board) -> int:
    total = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += len(board.pieces(piece_type, chess.WHITE)) * PIECE_VALUES[piece_type]
        total += len(board.pieces(piece_type, chess.BLACK)) * PIECE_VALUES[piece_type]
    return total


def _center_distance(square: chess.Square) -> int:
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    return abs(file_idx - 3) + abs(file_idx - 4) + abs(rank_idx - 3) + abs(rank_idx - 4)


def _piece_square_bonus(
    piece_type: chess.PieceType,
    square: chess.Square,
    color: chess.Color,
    phase: int,
) -> int:
    if color == chess.WHITE:
        rank = chess.square_rank(square)
    else:
        rank = 7 - chess.square_rank(square)
    dist = _center_distance(square)
    if piece_type == chess.PAWN:
        bonus = rank * 5
        file_idx = chess.square_file(square)
        if file_idx in (3, 4):
            bonus += 8
        return bonus
    if piece_type == chess.KNIGHT:
        return 34 - 5 * dist + rank * 2
    if piece_type == chess.BISHOP:
        return 24 - 3 * dist + rank
    if piece_type == chess.ROOK:
        return 8 + rank * 2
    if piece_type == chess.QUEEN:
        return 12 - 2 * dist
    if piece_type == chess.KING:
        if phase > 2400:
            return -4 * dist
        return 24 - 4 * _center_distance(square)
    return 0


def _pawn_structure(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    enemy_pawns = board.pieces(chess.PAWN, not color)
    score = 0
    files: Dict[int, int] = {}
    for sq in pawns:
        file_idx = chess.square_file(sq)
        files[file_idx] = files.get(file_idx, 0) + 1
    for sq in pawns:
        file_idx = chess.square_file(sq)
        rank = chess.square_rank(sq)
        if files.get(file_idx, 0) > 1:
            score -= 10
        if files.get(file_idx - 1, 0) == 0 and files.get(file_idx + 1, 0) == 0:
            score -= 9
        passed = True
        for enemy_file in (file_idx - 1, file_idx, file_idx + 1):
            if enemy_file < 0 or enemy_file > 7:
                continue
            for enemy_sq in enemy_pawns:
                if chess.square_file(enemy_sq) != enemy_file:
                    continue
                enemy_rank = chess.square_rank(enemy_sq)
                if color == chess.WHITE and enemy_rank > rank:
                    passed = False
                if color == chess.BLACK and enemy_rank < rank:
                    passed = False
        if passed:
            advance = rank if color == chess.WHITE else 7 - rank
            score += 15 + advance * advance * 2
    return score


def _king_safety(board: chess.Board, color: chess.Color) -> int:
    king = board.king(color)
    if king is None:
        return -500
    score = 0
    enemy = not color
    ring = chess.SquareSet(chess.BB_KING_ATTACKS[king])
    attacked = 0
    for sq in ring:
        if board.is_attacked_by(enemy, sq):
            attacked += 1
        piece = board.piece_at(sq)
        if piece and piece.color == color:
            if piece.piece_type == chess.PAWN:
                score += 7
            else:
                score += 3
    if board.is_attacked_by(enemy, king):
        score -= 75
    score -= attacked * 5
    return score


def _undeveloped_minors(board: chess.Board, color: chess.Color) -> int:
    if color == chess.WHITE:
        squares = (chess.B1, chess.G1, chess.C1, chess.F1)
    else:
        squares = (chess.B8, chess.G8, chess.C8, chess.F8)
    count = 0
    for sq in squares:
        piece = board.piece_at(sq)
        if piece and piece.color == color:
            count += 1
    return count


def _evaluate_white(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    phase = _phase(board)
    score = 0
    bishops = {chess.WHITE: 0, chess.BLACK: 0}

    for color in (chess.WHITE, chess.BLACK):
        sign = 1 if color == chess.WHITE else -1
        for piece_type in PIECE_VALUES:
            squares = board.pieces(piece_type, color)
            if piece_type == chess.BISHOP:
                bishops[color] = len(squares)
            for sq in squares:
                bonus = _piece_square_bonus(piece_type, sq, color, phase)
                score += sign * (PIECE_VALUES[piece_type] + bonus)
        score += sign * _pawn_structure(board, color)
        score += sign * _king_safety(board, color)

    if bishops[chess.WHITE] >= 2:
        score += 35
    if bishops[chess.BLACK] >= 2:
        score -= 35

    try:
        mobility = board.legal_moves.count()
    except Exception:
        mobility = 0
    score += (1 if board.turn == chess.WHITE else -1) * min(60, mobility * 2)

    for sq in CENTER:
        if board.is_attacked_by(chess.WHITE, sq):
            score += 8
        if board.is_attacked_by(chess.BLACK, sq):
            score -= 8
    for sq in EXTENDED_CENTER:
        if board.is_attacked_by(chess.WHITE, sq):
            score += 2
        if board.is_attacked_by(chess.BLACK, sq):
            score -= 2

    if board.fullmove_number <= 12:
        score -= _undeveloped_minors(board, chess.WHITE) * 12
        score += _undeveloped_minors(board, chess.BLACK) * 12

    return score


def _evaluate(board: chess.Board) -> int:
    val = _evaluate_white(board)
    return val if board.turn == chess.WHITE else -val


def _move_score(
    board: chess.Board,
    move: chess.Move,
    pv_move: Optional[chess.Move] = None,
) -> int:
    if pv_move is not None and move == pv_move:
        return 1_000_000
    score = 0
    if move.promotion:
        score += 80_000 + PIECE_VALUES.get(move.promotion, 0)
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        if victim is None and board.is_en_passant(move):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(move.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 50_000 + victim_value * 12 - attacker_value
    if board.gives_check(move):
        score += 20_000
    if board.is_castling(move):
        score += 5_000
    if move.to_square in CENTER:
        score += 900
    elif move.to_square in EXTENDED_CENTER:
        score += 250
    piece = board.piece_at(move.from_square)
    if piece and board.fullmove_number <= 12:
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            if move.from_square in HOME_MINORS:
                score += 700
        if piece.piece_type == chess.QUEEN:
            score -= 250
        if piece.piece_type == chess.ROOK:
            score -= 120
    return score


def _ordered_moves(
    board: chess.Board,
    pv_move: Optional[chess.Move] = None,
) -> List[chess.Move]:
    moves = list(board.legal_moves)
    return sorted(
        moves,
        key=lambda mv: _move_score(board, mv, pv_move),
        reverse=True,
    )


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    state: SearchState,
) -> int:
    state.nodes += 1
    if not _time_left(state):
        return _evaluate(board)
    stand = _evaluate(board)
    if stand >= beta:
        return beta
    if stand > alpha:
        alpha = stand

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            tactical.append(mv)
    tactical.sort(key=lambda mv: _move_score(board, mv), reverse=True)

    for mv in tactical[:18]:
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, state)
        board.pop()
        if state.stopped:
            return alpha
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    state: SearchState,
    ply: int = 0,
) -> int:
    state.nodes += 1
    if not _time_left(state):
        return _evaluate(board)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_draw():
        return 0

    if depth <= 0:
        if board.is_check():
            depth = 1
        else:
            return _quiescence(board, alpha, beta, state)

    best = -INF
    for mv in _ordered_moves(board):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, state, ply + 1)
        board.pop()
        if state.stopped:
            return best if best > -INF else _evaluate(board)
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _immediate_mate(board: chess.Board) -> Optional[chess.Move]:
    for mv in _ordered_moves(board):
        board.push(mv)
        mate = board.is_checkmate()
        board.pop()
        if mate:
            return mv
    return None


def _search_best_move(
    board: chess.Board,
    time_limit_ms: int,
) -> Optional[chess.Move]:
    legal = list(board.legal_moves)
    if not legal:
        return None
    if len(legal) == 1:
        return legal[0]

    mate = _immediate_mate(board)
    if mate is not None:
        return mate

    try:
        requested_ms = int(time_limit_ms or 100)
    except Exception:
        requested_ms = 100
    budget_ms = max(8, min(requested_ms, 500))
    usable = max(0.006, (budget_ms - 6) / 1000.0)
    state = SearchState(time.perf_counter() + usable)

    best_move = _fallback_move(board)
    best_score = -INF

    piece_count = len(board.piece_map())
    if budget_ms < 40:
        max_depth = 2
    elif budget_ms < 90:
        max_depth = 3
    elif piece_count <= 12:
        max_depth = 5
    else:
        max_depth = 4

    root_moves = _ordered_moves(board)
    for depth in range(1, max_depth + 1):
        if not _time_left(state):
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        beta = INF
        for mv in root_moves:
            if not _time_left(state):
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -beta, -alpha, state, 1)
            board.pop()
            if state.stopped:
                break
            tie_better = False
            if current_best is not None and score == current_score:
                tie_better = mv.uci() < current_best.uci()
            if score > current_score or tie_better:
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score
        if not state.stopped and current_best is not None:
            best_move = current_best
            best_score = current_score
            ordered = _ordered_moves(board, best_move)
            root_moves = [best_move] + [mv for mv in ordered if mv != best_move]
            if best_score >= MATE_SCORE - 10:
                break

    if best_move in board.legal_moves:
        return best_move
    return _fallback_move(board)


def _format_move(
    board: chess.Board,
    mv: Optional[chess.Move],
    output_format: str,
) -> str:
    if mv is None or mv not in board.legal_moves:
        return ""
    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(mv)
        except Exception:
            return mv.uci()
    return mv.uci()


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
    if board.is_game_over(claim_draw=False):
        return ""
    try:
        mv = _search_best_move(board, time_limit_ms)
    except Exception:
        mv = _fallback_move(board, observation)
    if mv not in board.legal_moves:
        mv = _fallback_move(board, observation)
    return _format_move(board, mv, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)
