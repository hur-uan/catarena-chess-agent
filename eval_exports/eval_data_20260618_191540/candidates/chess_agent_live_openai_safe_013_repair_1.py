"""Safe self-contained CATArena chess agent."""

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

CENTER_SQUARES = {
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

OPENING_PREFERENCES = (
    "e2e4",
    "d2d4",
    "g1f3",
    "c2c4",
    "e7e5",
    "d7d5",
    "g8f6",
    "c7c5",
    "b1c3",
    "b8c6",
    "f1c4",
    "f8c5",
    "f1b5",
    "f8b4",
    "c1g5",
    "c8g4",
)


class SearchInfo:
    """Small diagnostics container without dataclass import-loader fragility."""

    def __init__(
        self,
        move: str,
        score: int,
        depth: int,
        elapsed_ms: float,
        legal_moves: list[str],
        fallback_used: bool = False,
    ) -> None:
        self.move = move
        self.score = score
        self.depth = depth
        self.elapsed_ms = elapsed_ms
        self.legal_moves = legal_moves
        self.fallback_used = fallback_used


class TimeoutSearch(Exception):
    """Raised internally when the bounded search reaches its time budget."""


class ChessAgent:
    """Compatibility wrapper for arena integrations expecting an object."""

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
    """Choose a legal move for a chess observation and return UCI by default."""
    board = parse_observation(observation)
    try:
        info = _select_move_info(board, max(1, int(time_limit_ms)))
        chosen = chess.Move.from_uci(info.move) if info.move else None
        if chosen not in board.legal_moves:
            chosen = _fallback_move(board)
    except Exception:
        chosen = _fallback_move(board)

    if chosen is None:
        return ""
    if str(output_format).strip().lower() == "san":
        try:
            return board.san(chosen)
        except Exception:
            return chosen.uci()
    return chosen.uci()


def select_move_details(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> SearchInfo:
    """Return move plus lightweight diagnostics while preserving legality."""
    board = parse_observation(observation)
    start = time.perf_counter()
    info = _select_move_info(board, max(1, int(time_limit_ms)))
    if str(output_format).strip().lower() == "san" and info.move:
        mv = chess.Move.from_uci(info.move)
        if mv in board.legal_moves:
            info.move = board.san(mv)
    info.elapsed_ms = (time.perf_counter() - start) * 1000.0
    return info


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def parse_observation(observation: Any) -> chess.Board:
    """Parse common CATArena observations safely."""
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    moves_value = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        moves_value = observation.get("moves") or observation.get("move_history")
        state = observation.get("state")
        if fen is None and isinstance(state, dict):
            value = state.get("fen") or state.get("board")
            if isinstance(value, str) and value.strip():
                fen = value.strip()
    elif isinstance(observation, str) and observation.strip():
        fen = observation.strip()

    if fen:
        try:
            return chess.Board(fen)
        except Exception:
            pass

    if isinstance(moves_value, list):
        board = chess.Board()
        for item in moves_value:
            try:
                mv = chess.Move.from_uci(str(item).strip())
            except Exception:
                break
            if mv in board.legal_moves:
                board.push(mv)
            else:
                break
        return board

    return chess.Board()


def _select_move_info(board: chess.Board, time_limit_ms: int) -> SearchInfo:
    legal = list(board.legal_moves)
    legal_uci = [mv.uci() for mv in legal]
    if not legal or board.is_game_over(claim_draw=False):
        return SearchInfo("", 0, 0, 0.0, legal_uci, True)

    start = time.perf_counter()
    budget = min(max(time_limit_ms, 1), 250)
    deadline = start + max(0.003, budget * 0.82 / 1000.0)

    mate = _mate_in_one(board)
    if mate is not None:
        elapsed = (time.perf_counter() - start) * 1000.0
        return SearchInfo(mate.uci(), MATE_SCORE, 1, elapsed, legal_uci)

    opening = _opening_move(board)
    if opening is not None and board.fullmove_number <= 5:
        elapsed = (time.perf_counter() - start) * 1000.0
        return SearchInfo(opening.uci(), 20, 1, elapsed, legal_uci)

    fallback = _fallback_move(board)
    best_move = fallback
    best_score = -INF
    completed_depth = 0
    max_depth = _depth_for_budget(board, budget)

    try:
        for depth in range(1, max_depth + 1):
            _check_time(deadline)
            score, candidate = _root_search(board, depth, deadline)
            if candidate is not None and candidate in board.legal_moves:
                best_move = candidate
                best_score = score
                completed_depth = depth
    except TimeoutSearch:
        pass
    except Exception:
        best_move = fallback

    if best_move not in board.legal_moves:
        best_move = fallback
    elapsed = (time.perf_counter() - start) * 1000.0
    score_out = int(best_score if best_score > -INF else 0)
    move_out = best_move.uci() if best_move is not None else ""
    return SearchInfo(move_out, score_out, completed_depth, elapsed, legal_uci)


def _depth_for_budget(board: chess.Board, budget_ms: int) -> int:
    legal_count = board.legal_moves.count()
    pieces = len(board.piece_map())
    if budget_ms < 25:
        return 2
    if budget_ms < 70:
        return 3
    if pieces <= 12 and legal_count <= 30:
        return 5
    if pieces <= 22 and budget_ms >= 120:
        return 4
    return 3


def _root_search(
    board: chess.Board,
    depth: int,
    deadline: float,
) -> tuple[int, chess.Move | None]:
    alpha = -INF
    beta = INF
    best_score = -INF
    best_move = None
    for mv in _ordered_moves(board):
        _check_time(deadline)
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, 1)
        board.pop()
        if score > best_score or best_move is None:
            best_score = score
            best_move = mv
        if score > alpha:
            alpha = score
    return best_score, best_move


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> int:
    _check_time(deadline)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if _is_drawish_terminal(board):
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    best = -INF
    for mv in _ordered_moves(board):
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
) -> int:
    _check_time(deadline)
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    noisy = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            noisy.append(mv)
    noisy.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)

    for mv in noisy[:16]:
        _check_time(deadline)
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _is_drawish_terminal(board: chess.Board) -> bool:
    return (
        board.is_stalemate()
        or board.is_insufficient_material()
        or board.can_claim_fifty_moves()
        or board.can_claim_threefold_repetition()
    )


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    score = _evaluate_white(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE

    score = 0
    bishops = {chess.WHITE: 0, chess.BLACK: 0}
    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        score += sign * PIECE_VALUES[piece.piece_type]
        if piece.piece_type == chess.BISHOP:
            bishops[piece.color] += 1
        score += sign * _piece_activity(piece, square)

    if bishops[chess.WHITE] >= 2:
        score += 35
    if bishops[chess.BLACK] >= 2:
        score -= 35

    turn = board.turn
    try:
        board.turn = chess.WHITE
        white_mobility = board.legal_moves.count()
        board.turn = chess.BLACK
        black_mobility = board.legal_moves.count()
    finally:
        board.turn = turn
    score += 2 * (white_mobility - black_mobility)

    if _has_any_castling_right(board, chess.WHITE):
        score += 8
    if _has_any_castling_right(board, chess.BLACK):
        score -= 8
    return score


def _piece_activity(piece: chess.Piece, square: chess.Square) -> int:
    rank = chess.square_rank(square)
    file_index = chess.square_file(square)
    if piece.color == chess.BLACK:
        rank = 7 - rank

    central = 14 - 4 * (abs(file_index - 3.5) + abs(rank - 3.5))
    if piece.piece_type == chess.PAWN:
        return int(rank * 7 + central * 0.6)
    if piece.piece_type == chess.KNIGHT:
        return int(central * 3)
    if piece.piece_type == chess.BISHOP:
        return int(central * 2)
    if piece.piece_type == chess.ROOK:
        return int(rank * 2 + central * 0.5)
    if piece.piece_type == chess.QUEEN:
        return int(central)
    if piece.piece_type == chess.KING:
        return int(-central * 1.5 if rank < 5 else central)
    return 0


def _has_any_castling_right(board: chess.Board, color: chess.Color) -> bool:
    return board.has_kingside_castling_rights(color) or board.has_queenside_castling_rights(
        color
    )


def _ordered_moves(board: chess.Board) -> list[chess.Move]:
    moves = list(board.legal_moves)
    moves.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)
    return moves


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if mv.promotion:
        score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        victim_value = PIECE_VALUES[chess.PAWN] if board.is_en_passant(mv) else 0
        if victim is not None:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0)
        attacker = board.piece_at(mv.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 1) if attacker else 1
        score += 5000 + 10 * victim_value - attacker_value
    if board.gives_check(mv):
        score += 3000
    if board.is_castling(mv):
        score += 500
    if mv.to_square in CENTER_SQUARES:
        score += 80
    piece = board.piece_at(mv.from_square)
    if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        home_rank = 0 if piece.color == chess.WHITE else 7
        if board.fullmove_number <= 10 and chess.square_rank(mv.from_square) == home_rank:
            score += 60
    return score


def _mate_in_one(board: chess.Board) -> chess.Move | None:
    for mv in _ordered_moves(board):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _opening_move(board: chess.Board) -> chess.Move | None:
    legal = set(board.legal_moves)
    for uci in OPENING_PREFERENCES:
        mv = chess.Move.from_uci(uci)
        if mv in legal:
            return mv
    return None


def _fallback_move(board: chess.Board) -> chess.Move | None:
    legal = list(board.legal_moves)
    if not legal:
        return None
    legal.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)

    best = legal[0]
    best_score = -INF
    for mv in legal[:12]:
        board.push(mv)
        if board.is_checkmate():
            score = MATE_SCORE
        else:
            score = -_evaluate_for_side_to_move(board)
            piece = board.piece_at(mv.to_square)
            if piece and piece.piece_type == chess.KING:
                if board.is_attacked_by(board.turn, mv.to_square):
                    score -= 10000
        board.pop()
        if score > best_score:
            best_score = score
            best = mv
    return best


def _check_time(deadline: float) -> None:
    if time.perf_counter() >= deadline:
        raise TimeoutSearch
