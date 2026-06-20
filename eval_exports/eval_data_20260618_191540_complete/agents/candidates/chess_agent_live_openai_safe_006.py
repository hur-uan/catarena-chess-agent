"""Safe self-contained CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation intentionally avoids network calls, subprocesses, dynamic imports,
file I/O, eval/exec, and non-standard dependencies beyond python-chess.
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
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# White-oriented piece-square tables. Black uses mirrored squares.
PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_TABLE = [
    0, 0, 0, 5, 5, 0, 0, 0,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
QUEEN_TABLE = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -10, 5, 5, 5, 5, 5, 0, -10,
    0, 0, 5, 5, 5, 5, 0, -5,
    -5, 0, 5, 5, 5, 5, 0, -5,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_TABLE = [
    20, 30, 10, 0, 0, 10, 30, 20,
    20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
]
PST = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE,
}

# Small deterministic opening preferences. Keys are first four FEN fields.
OPENING_BOOK = {
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -": "g1f3",
    "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq -": "g8f6",
    "rnbqkb1r/pppppppp/5n2/8/8/5N2/PPPPPPPP/RNBQKB1R w KQkq -": "d2d4",
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -": "c7c5",
    "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq -": "g8f6",
}


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

    chosen = None
    try:
        chosen = _book_move(board)
        if chosen is None:
            chosen = _find_mate_in_one(board)
        if chosen is None:
            chosen = _search_move(board, time_limit_ms)
    except Exception:
        chosen = None

    if chosen not in legal_moves:
        chosen = _fallback_move(board)
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
    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _format_move(board: chess.Board, move_obj: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def _book_key(board: chess.Board) -> str:
    parts = board.fen().split()
    return " ".join(parts[:4]) if len(parts) >= 4 else board.fen()


def _book_move(board: chess.Board) -> chess.Move | None:
    uci = OPENING_BOOK.get(_book_key(board))
    if not uci:
        return None
    try:
        candidate = chess.Move.from_uci(uci)
    except ValueError:
        return None
    return candidate if candidate in board.legal_moves else None


def _find_mate_in_one(board: chess.Board) -> chess.Move | None:
    for move_obj in _ordered_moves(board, None):
        board.push(move_obj)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return move_obj
    return None


def _search_move(board: chess.Board, time_limit_ms: int) -> chess.Move | None:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None

    safe_ms = max(8, min(int(time_limit_ms or 100), 250))
    deadline = time.perf_counter() + (safe_ms * 0.82 / 1000.0)
    node_limit = max(1000, min(18000, safe_ms * 90))
    state = {"nodes": 0, "deadline": deadline, "node_limit": node_limit, "stop": False}
    tt: dict[tuple[str, int], int] = {}

    best_move = _fallback_move(board)
    best_score = -INF
    max_depth = 4 if safe_ms >= 70 else 3
    if board.fullmove_number <= 8 and safe_ms >= 90:
        max_depth = 5

    for depth in range(1, max_depth + 1):
        if _time_up(state):
            break
        current_best = None
        current_score = -INF
        alpha = -INF
        beta = INF
        for move_obj in _ordered_moves(board, best_move):
            if _time_up(state):
                break
            board.push(move_obj)
            score = -_negamax(board, depth - 1, -beta, -alpha, 1, state, tt)
            board.pop()
            if state["stop"]:
                break
            if score > current_score:
                current_score = score
                current_best = move_obj
            if score > alpha:
                alpha = score
        if not state["stop"] and current_best is not None:
            best_move = current_best
            best_score = current_score
            if best_score >= MATE_SCORE - 100:
                break
        if state["stop"]:
            break
    return best_move


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    ply: int,
    state: dict[str, Any],
    tt: dict[tuple[str, int], int],
) -> int:
    if _time_up(state):
        state["stop"] = True
        return 0

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    key = (board.transposition_key() if hasattr(board, "transposition_key") else board.board_fen(), depth)
    cached = tt.get(key)
    if cached is not None:
        return cached

    if depth <= 0:
        return _quiescence(board, alpha, beta, ply, state)

    best = -INF
    for move_obj in _ordered_moves(board, None):
        board.push(move_obj)
        score = -_negamax(board, depth - 1, -beta, -alpha, ply + 1, state, tt)
        board.pop()
        if state["stop"]:
            return 0
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    tt[key] = best
    return best


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    ply: int,
    state: dict[str, Any],
) -> int:
    if _time_up(state):
        state["stop"] = True
        return 0
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    tactical_moves = []
    if board.is_check():
        tactical_moves = list(board.legal_moves)
    else:
        for move_obj in board.legal_moves:
            if board.is_capture(move_obj) or move_obj.promotion:
                tactical_moves.append(move_obj)
    tactical_moves.sort(key=lambda mv: _move_order_score(board, mv, None), reverse=True)

    for move_obj in tactical_moves[:24]:
        board.push(move_obj)
        score = -_quiescence(board, -beta, -alpha, ply + 1, state)
        board.pop()
        if state["stop"]:
            return 0
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate(board: chess.Board) -> int:
    score = 0
    white_bishops = 0
    black_bishops = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        table = PST[piece.piece_type]
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        positional = table[pst_square]
        piece_score = value + positional
        if piece.color == chess.WHITE:
            score += piece_score
            if piece.piece_type == chess.BISHOP:
                white_bishops += 1
        else:
            score -= piece_score
            if piece.piece_type == chess.BISHOP:
                black_bishops += 1

    if white_bishops >= 2:
        score += 30
    if black_bishops >= 2:
        score -= 30

    # Lightweight mobility term keeps positions active without expensive analysis.
    turn = board.turn
    try:
        white_mobility = len(list(board.legal_moves)) if turn == chess.WHITE else 0
        board.turn = not turn
        black_mobility = len(list(board.legal_moves)) if turn == chess.WHITE else len(list(board.legal_moves))
    except Exception:
        white_mobility = 0
        black_mobility = 0
    finally:
        board.turn = turn
    if turn == chess.WHITE:
        score += 2 * white_mobility
    else:
        score -= 2 * black_mobility

    return score if board.turn == chess.WHITE else -score


def _ordered_moves(board: chess.Board, preferred: chess.Move | None) -> list[chess.Move]:
    moves = list(board.legal_moves)
    moves.sort(key=lambda mv: _move_order_score(board, mv, preferred), reverse=True)
    return moves


def _move_order_score(board: chess.Board, move_obj: chess.Move, preferred: chess.Move | None) -> int:
    if preferred is not None and move_obj == preferred:
        return 1_000_000
    score = 0
    if move_obj.promotion:
        score += 80_000 + PIECE_VALUES.get(move_obj.promotion, 0)
    if board.is_capture(move_obj):
        victim = board.piece_at(move_obj.to_square)
        if victim is None and board.is_en_passant(move_obj):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(move_obj.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 1) if attacker else 1
        score += 60_000 + 10 * victim_value - attacker_value
    if board.gives_check(move_obj):
        score += 20_000
    piece = board.piece_at(move_obj.from_square)
    if piece:
        to_sq = move_obj.to_square if piece.color == chess.WHITE else chess.square_mirror(move_obj.to_square)
        from_sq = move_obj.from_square if piece.color == chess.WHITE else chess.square_mirror(move_obj.from_square)
        score += PST[piece.piece_type][to_sq] - PST[piece.piece_type][from_sq]
    return score


def _fallback_move(board: chess.Board) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return chess.Move.null()
    return max(legal_moves, key=lambda mv: _move_order_score(board, mv, None))


def _time_up(state: dict[str, Any]) -> bool:
    state["nodes"] += 1
    if state["nodes"] >= state["node_limit"]:
        return True
    if state["nodes"] % 128 == 0 and time.perf_counter() >= state["deadline"]:
        return True
    return False
