"""Self-contained safe CATArena chess agent.

Public entry point:
    select_move(observation, output_format="uci", time_limit_ms=100) -> str

Safety properties:
- no network calls
- no file I/O
- no subprocess/eval/exec/dynamic imports
- every returned move is validated against python-chess legal_moves
- bounded deterministic search with legal fallback
"""

import math
import time
from typing import Any, Iterable, Optional

import chess


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.F4, chess.C5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}
MATE_SCORE = 100000
INF = 10 ** 9

# Small piece-square tables from White perspective. Black uses mirrored squares.
PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, -20, -20, 10, 10, 5,
    5, -5, -10, 0, 0, -10, -5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, 5, 10, 25, 25, 10, 5, 5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_PST = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_PST = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_PST = [
    0, 0, 5, 10, 10, 5, 0, 0,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
QUEEN_PST = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -10, 5, 5, 5, 5, 5, 0, -10,
    0, 0, 5, 5, 5, 5, 0, -5,
    -5, 0, 5, 5, 5, 5, 0, -5,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_MID_PST = [
    20, 30, 10, 0, 0, 10, 30, 20,
    20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
]
PSTS = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
    chess.KING: KING_MID_PST,
}


class SearchRecord:
    """Tiny diagnostics container kept for compatibility with callers that inspect details."""

    def __init__(self, fen: str, selected_move: str, legal_moves: list[str], backend: str) -> None:
        self.fen = fen
        self.selected_move = selected_move
        self.legal_moves = legal_moves
        self.backend = backend
        self.depth = 0
        self.elapsed_ms = 0.0
        self.nodes = 0
        self.cp = 0
        self.mate_distance = None
        self.fallback_used = backend.endswith("fallback")


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


class _SearchState:
    def __init__(self, deadline: float, node_limit: int) -> None:
        self.deadline = deadline
        self.node_limit = node_limit
        self.nodes = 0
        self.timed_out = False

    def should_stop(self) -> bool:
        if self.nodes >= self.node_limit:
            self.timed_out = True
            return True
        if time.perf_counter() >= self.deadline:
            self.timed_out = True
            return True
        return False


def select_move(observation: Any, output_format: str = "uci", time_limit_ms: int = 100) -> str:
    """Choose a legal chess move for the supplied observation."""
    board = _safe_parse_board(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    hinted = _hinted_legal_moves(observation, legal_moves)
    candidates = [mv for mv in legal_moves if mv.uci() in hinted]
    if not candidates:
        candidates = legal_moves

    chosen = _choose_move(board, candidates, time_limit_ms)
    if chosen not in legal_moves:
        chosen = _fallback_move(board, candidates)
    if chosen is None or chosen not in legal_moves:
        chosen = legal_moves[0]

    return _format_move(board, chosen, output_format)


def select_move_details(observation: Any, output_format: str = "uci", time_limit_ms: int = 100) -> SearchRecord:
    board = _safe_parse_board(observation)
    legal_uci = [mv.uci() for mv in board.legal_moves]
    start = time.perf_counter()
    selected = select_move(observation, output_format="uci", time_limit_ms=time_limit_ms)
    rec = SearchRecord(board.fen(), selected, legal_uci, "self_contained_guarded_search")
    rec.elapsed_ms = (time.perf_counter() - start) * 1000.0
    return rec


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _safe_parse_board(observation: Any) -> chess.Board:
    fen = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "FEN"):
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


def _hinted_legal_moves(observation: Any, legal_moves: Iterable[chess.Move]) -> set[str]:
    legal = {mv.uci() for mv in legal_moves}
    hinted: set[str] = set()
    if isinstance(observation, dict):
        for key in ("legal_moves", "legalMoves", "moves", "valid_moves", "validMoves"):
            raw = observation.get(key)
            if isinstance(raw, str):
                hinted.update(part.strip() for part in raw.replace(",", " ").split())
            elif isinstance(raw, (list, tuple, set)):
                hinted.update(str(item).strip() for item in raw)
    hinted.discard("")
    inter = hinted.intersection(legal)
    return inter if inter else legal


def _choose_move(board: chess.Board, candidates: list[chess.Move], time_limit_ms: int) -> chess.Move:
    mate = _find_mate_in_one(board, candidates)
    if mate is not None:
        return mate

    # If time is extremely low, avoid search overhead and use deterministic tactics.
    if time_limit_ms < 25:
        fb = _fallback_move(board, candidates)
        return fb if fb is not None else candidates[0]

    budget_ms = max(10, min(int(time_limit_ms), 500))
    deadline = time.perf_counter() + (budget_ms * 0.82 / 1000.0)
    node_limit = 1200 if budget_ms <= 80 else 3500 if budget_ms <= 180 else 8000
    state = _SearchState(deadline, node_limit)

    ordered = _ordered_moves(board, candidates)
    best_move = _fallback_move(board, ordered)
    if best_move is None:
        best_move = ordered[0]

    max_depth = 2
    if budget_ms >= 90:
        max_depth = 3
    if budget_ms >= 250:
        max_depth = 4

    try:
        for depth in range(1, max_depth + 1):
            if state.should_stop():
                break
            current_best = best_move
            current_score = -INF
            alpha = -INF
            beta = INF
            for mv in ordered:
                if state.should_stop():
                    break
                board.push(mv)
                score = -_negamax(board, depth - 1, -beta, -alpha, state, 1)
                board.pop()
                if state.timed_out:
                    break
                if score > current_score or (score == current_score and mv.uci() < current_best.uci()):
                    current_score = score
                    current_best = mv
                if score > alpha:
                    alpha = score
            if not state.timed_out:
                best_move = current_best
    except Exception:
        fb = _fallback_move(board, candidates)
        return fb if fb is not None else candidates[0]

    return best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, state: _SearchState, ply: int) -> int:
    state.nodes += 1
    if state.should_stop():
        return _evaluate(board)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, state, ply, 0)

    best = -INF
    moves = _ordered_moves(board, list(board.legal_moves))
    for mv in moves:
        if state.should_stop():
            break
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, state, ply + 1)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(board: chess.Board, alpha: int, beta: int, state: _SearchState, ply: int, qdepth: int) -> int:
    state.nodes += 1
    stand_pat = _evaluate(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if qdepth >= 4 or state.should_stop():
        return alpha

    noisy = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            noisy.append(mv)
    for mv in _ordered_moves(board, noisy):
        if state.should_stop():
            break
        board.push(mv)
        if board.is_checkmate():
            score = MATE_SCORE - ply
        else:
            score = -_quiescence(board, -beta, -alpha, state, ply + 1, qdepth + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES.get(piece.piece_type, 0)
        pst = PSTS.get(piece.piece_type)
        if pst is not None:
            idx = square if piece.color == chess.WHITE else chess.square_mirror(square)
            value += pst[idx]
        if piece.color == chess.WHITE:
            score += value
        else:
            score -= value

    # Lightweight activity and king-pressure terms.
    white_mob = 0
    black_mob = 0
    turn = board.turn
    try:
        board.turn = chess.WHITE
        if not board.is_checkmate():
            white_mob = board.legal_moves.count()
        board.turn = chess.BLACK
        if not board.is_checkmate():
            black_mob = board.legal_moves.count()
    finally:
        board.turn = turn
    score += 2 * (white_mob - black_mob)

    if board.is_check():
        score += -35 if board.turn == chess.WHITE else 35

    return score if board.turn == chess.WHITE else -score


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: (-_move_order_score(board, mv), mv.uci()))


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    moving = board.piece_at(mv.from_square)
    captured = board.piece_at(mv.to_square)

    if board.is_capture(mv):
        if captured is None and board.is_en_passant(mv):
            victim = PIECE_VALUES[chess.PAWN]
        else:
            victim = PIECE_VALUES.get(captured.piece_type, 0) if captured else 0
        attacker = PIECE_VALUES.get(moving.piece_type, 0) if moving else 0
        score += 10000 + 10 * victim - attacker
    if mv.promotion:
        score += 9000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.gives_check(mv):
        score += 700
    if board.is_castling(mv):
        score += 250
    if mv.to_square in CENTER:
        score += 90
    elif mv.to_square in EXTENDED_CENTER:
        score += 35
    if moving and moving.piece_type in (chess.KNIGHT, chess.BISHOP):
        if (moving.color == chess.WHITE and chess.square_rank(mv.from_square) == 0) or (
            moving.color == chess.BLACK and chess.square_rank(mv.from_square) == 7
        ):
            score += 140
    return score


def _find_mate_in_one(board: chess.Board, candidates: list[chess.Move]) -> Optional[chess.Move]:
    for mv in _ordered_moves(board, candidates):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _fallback_move(board: chess.Board, candidates: list[chess.Move]) -> Optional[chess.Move]:
    best = None
    best_score = -INF
    for mv in candidates:
        if mv not in board.legal_moves:
            continue
        score = _fallback_score(board, mv)
        if best is None or score > best_score or (score == best_score and mv.uci() < best.uci()):
            best = mv
            best_score = score
    return best


def _fallback_score(board: chess.Board, mv: chess.Move) -> int:
    score = _move_order_score(board, mv)
    moving = board.piece_at(mv.from_square)
    captured = board.piece_at(mv.to_square)

    if moving and moving.piece_type == chess.PAWN:
        rank = chess.square_rank(mv.to_square)
        progress = rank if moving.color == chess.WHITE else 7 - rank
        score += progress * 8
        if board.fullmove_number <= 10 and mv.from_square in {chess.D2, chess.E2, chess.D7, chess.E7}:
            score += 40
    elif moving and moving.piece_type == chess.QUEEN and board.fullmove_number <= 8:
        score -= 60
    elif moving and moving.piece_type == chess.ROOK and board.fullmove_number <= 8:
        score -= 25

    board.push(mv)
    if board.is_checkmate():
        score += 50000
    elif moving is not None:
        # Penalize undefended tactical self-hangs when no material was gained.
        moved_value = PIECE_VALUES.get(moving.piece_type, 0)
        if captured is None and mv.promotion is None and board.is_attacked_by(board.turn, mv.to_square):
            defenders = board.attackers(not board.turn, mv.to_square)
            if not defenders:
                score -= moved_value // 2
            else:
                score -= moved_value // 4
    board.pop()
    return score


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    # CATArena expects UCI, but SAN is supported for callers that explicitly ask.
    fmt = (output_format or "uci").lower()
    if fmt == "san":
        try:
            return board.san(mv)
        except Exception:
            return mv.uci()
    return mv.uci()
