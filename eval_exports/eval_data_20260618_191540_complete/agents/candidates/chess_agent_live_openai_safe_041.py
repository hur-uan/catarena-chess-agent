"""Safe self-contained CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str
"""

from __future__ import annotations

import time
from typing import Any

import chess

MATE_SCORE = 100000
INF = 10**9
NODE_LIMIT_DEFAULT = 12000

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
    chess.F4,
    chess.C5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
}

KNIGHT_PST = [
    -50, -35, -25, -20, -20, -25, -35, -50,
    -35, -15, 0, 5, 5, 0, -15, -35,
    -25, 5, 15, 20, 20, 15, 5, -25,
    -20, 10, 20, 28, 28, 20, 10, -20,
    -20, 10, 20, 28, 28, 20, 10, -20,
    -25, 5, 15, 20, 20, 15, 5, -25,
    -35, -15, 0, 5, 5, 0, -15, -35,
    -50, -35, -25, -20, -20, -25, -35, -50,
]

BISHOP_PST = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 15, 15, 10, 0, -10,
    -10, 5, 10, 15, 15, 10, 5, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, -15, -15, 10, 10, 5,
    5, -5, -10, 0, 0, -10, -5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, 5, 10, 25, 25, 10, 5, 5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
    0, 0, 0, 0, 0, 0, 0, 0,
]


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
        self.stop = False

    def tick(self) -> bool:
        self.nodes += 1
        if self.nodes >= self.node_limit or time.monotonic() >= self.deadline:
            self.stop = True
        return self.stop


def select_move(observation: Any, output_format: str = "uci", time_limit_ms: int = 100) -> str:
    """Choose a legal chess move for the supplied observation."""
    try:
        board = _parse_board(observation)
        legal_moves = list(board.legal_moves)
        if not legal_moves or board.is_game_over(claim_draw=False):
            return ""
        chosen = _choose_move(board, max(1, int(time_limit_ms)))
        if chosen not in legal_moves:
            chosen = legal_moves[0]
        return _format_move(board, chosen, output_format)
    except Exception:
        return _emergency_legal_move(observation, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_board(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    if isinstance(observation, dict):
        for key in ("fen", "board", "state", "observation"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                return chess.Board(value.strip())
        history = observation.get("moves") or observation.get("move_history") or observation.get("history")
        board = chess.Board()
        if isinstance(history, list):
            for item in history:
                token = str(item).strip()
                if not token:
                    continue
                try:
                    mv = chess.Move.from_uci(token)
                    if mv in board.legal_moves:
                        board.push(mv)
                    else:
                        board.push_san(token)
                except Exception:
                    break
        return board
    if isinstance(observation, str) and observation.strip():
        text = observation.strip()
        try:
            return chess.Board(text)
        except Exception:
            board = chess.Board()
            for token in text.replace(",", " ").split():
                try:
                    mv = chess.Move.from_uci(token)
                    if mv in board.legal_moves:
                        board.push(mv)
                    else:
                        board.push_san(token)
                except Exception:
                    continue
            return board
    return chess.Board()


def _choose_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    mate_move = _find_immediate_mate(board, legal_moves)
    if mate_move is not None:
        return mate_move

    budget = max(0.004, min(0.18, (time_limit_ms / 1000.0) * 0.82))
    deadline = time.monotonic() + budget
    node_limit = NODE_LIMIT_DEFAULT if time_limit_ms >= 80 else 4500
    state = _SearchState(deadline, node_limit)

    best_move = _best_static_move(board, legal_moves)
    max_depth = 3 if time_limit_ms >= 70 and len(legal_moves) <= 42 else 2
    if time_limit_ms >= 140 and len(legal_moves) <= 34:
        max_depth = 4

    for depth in range(1, max_depth + 1):
        score, candidate = _root_search(board, depth, state)
        if state.stop:
            break
        if candidate is not None:
            best_move = candidate
        if score >= MATE_SCORE - 20:
            break
    return best_move


def _root_search(board: chess.Board, depth: int, state: _SearchState) -> tuple[int, chess.Move | None]:
    alpha = -INF
    beta = INF
    best_score = -INF
    best_move = None
    for mv in _ordered_moves(board, list(board.legal_moves)):
        if state.tick():
            break
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, state, 1)
        board.pop()
        if state.stop:
            break
        if score > best_score or best_move is None:
            best_score = score
            best_move = mv
        if score > alpha:
            alpha = score
    return best_score, best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, state: _SearchState, ply: int) -> int:
    if state.tick():
        return _evaluate(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, state, ply, 0)

    best = -INF
    for mv in _ordered_moves(board, list(board.legal_moves)):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, state, ply + 1)
        board.pop()
        if state.stop:
            return _evaluate(board)
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(board: chess.Board, alpha: int, beta: int, state: _SearchState, ply: int, qdepth: int) -> int:
    stand_pat = _evaluate(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if qdepth >= 3 or state.tick():
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion:
            tactical.append(mv)
        elif board.gives_check(mv) and qdepth == 0:
            tactical.append(mv)
    for mv in _ordered_moves(board, tactical):
        board.push(mv)
        if board.is_checkmate():
            score = MATE_SCORE - ply
        else:
            score = -_quiescence(board, -beta, -alpha, state, ply + 1, qdepth + 1)
        board.pop()
        if state.stop:
            break
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _find_immediate_mate(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move | None:
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    if mv.promotion:
        score += 9000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(mv.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 5000 + 10 * victim_value - attacker_value
    if board.gives_check(mv):
        score += 1500
    piece = board.piece_at(mv.from_square)
    if piece:
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 10:
            back_rank = chess.square_rank(mv.from_square) in (0, 7)
            if back_rank:
                score += 260
        if piece.piece_type == chess.PAWN and mv.to_square in CENTER:
            score += 180
        if piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 140
        if piece.piece_type == chess.ROOK and board.fullmove_number <= 8:
            score -= 90
    if board.is_castling(mv):
        score += 500
    if mv.to_square in CENTER:
        score += 120
    elif mv.to_square in EXTENDED_CENTER:
        score += 45
    return score


def _best_static_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    best = legal_moves[0]
    best_score = -INF
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        if board.is_checkmate():
            score = MATE_SCORE
        else:
            score = -_evaluate(board)
        board.pop()
        if score > best_score:
            best_score = score
            best = mv
    return best


def _evaluate(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    white_score = 0
    black_score = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES.get(piece.piece_type, 0)
        value += _piece_square_bonus(piece, square)
        if piece.color == chess.WHITE:
            white_score += value
        else:
            black_score += value

    white_score += _side_activity(board, chess.WHITE)
    black_score += _side_activity(board, chess.BLACK)
    white_score += _king_safety(board, chess.WHITE)
    black_score += _king_safety(board, chess.BLACK)

    score = white_score - black_score
    return score if board.turn == chess.WHITE else -score


def _piece_square_bonus(piece: chess.Piece, square: chess.Square) -> int:
    idx = square if piece.color == chess.WHITE else chess.square_mirror(square)
    if piece.piece_type == chess.PAWN:
        return PAWN_PST[idx]
    if piece.piece_type == chess.KNIGHT:
        return KNIGHT_PST[idx]
    if piece.piece_type == chess.BISHOP:
        return BISHOP_PST[idx]
    if piece.piece_type == chess.ROOK:
        return 8 if chess.square_file(square) in (3, 4) else 0
    if piece.piece_type == chess.QUEEN:
        return 8 if square in CENTER or square in EXTENDED_CENTER else 0
    return 0


def _side_activity(board: chess.Board, color: chess.Color) -> int:
    old_turn = board.turn
    board.turn = color
    try:
        mobility = min(40, board.legal_moves.count())
    finally:
        board.turn = old_turn
    bishops = len(board.pieces(chess.BISHOP, color))
    bonus = mobility * 2
    if bishops >= 2:
        bonus += 35
    return bonus


def _king_safety(board: chess.Board, color: chess.Color) -> int:
    king_square = board.king(color)
    if king_square is None:
        return -500
    enemy = not color
    penalty = 0
    for sq in chess.SquareSet(chess.BB_KING_ATTACKS[king_square]):
        if board.is_attacked_by(enemy, sq):
            penalty += 8
    if board.is_attacked_by(enemy, king_square):
        penalty += 45
    shield = 0
    rank_dir = 1 if color == chess.WHITE else -1
    king_rank = chess.square_rank(king_square)
    king_file = chess.square_file(king_square)
    for file_delta in (-1, 0, 1):
        file_idx = king_file + file_delta
        rank_idx = king_rank + rank_dir
        if 0 <= file_idx <= 7 and 0 <= rank_idx <= 7:
            piece = board.piece_at(chess.square(file_idx, rank_idx))
            if piece and piece.color == color and piece.piece_type == chess.PAWN:
                shield += 10
    return shield - penalty


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(mv)
        except Exception:
            return mv.uci()
    return mv.uci()


def _emergency_legal_move(observation: Any, output_format: str) -> str:
    try:
        board = _parse_board(observation)
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return ""
        return _format_move(board, legal_moves[0], output_format)
    except Exception:
        board = chess.Board()
        legal_moves = list(board.legal_moves)
        return legal_moves[0].uci() if legal_moves else ""
