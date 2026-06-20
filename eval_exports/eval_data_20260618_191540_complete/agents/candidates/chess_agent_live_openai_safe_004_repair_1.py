"""Self-contained safe CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation is deterministic, uses only python-chess legal moves, performs no
network or file I/O, and avoids subprocess/eval/exec/dynamic imports.
"""

from __future__ import annotations

import time
from typing import Any

import chess

MATE_SCORE = 100000
INF = 10**9
DEFAULT_NODE_LIMIT = 9000

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Compact piece-square tables from White's perspective. Values are intentionally
# modest so tactics/material dominate, but development and king safety still help.
PST = {
    chess.PAWN: [
        0, 0, 0, 0, 0, 0, 0, 0,
        45, 50, 50, 10, 10, 50, 50, 45,
        12, 15, 20, 30, 30, 20, 15, 12,
        6, 8, 12, 25, 25, 12, 8, 6,
        2, 4, 8, 18, 18, 8, 4, 2,
        2, 2, 4, 8, 8, 4, 2, 2,
        0, 0, 0, -12, -12, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0,
    ],
    chess.KNIGHT: [
        -45, -25, -15, -10, -10, -15, -25, -45,
        -25, -10, 4, 8, 8, 4, -10, -25,
        -15, 8, 16, 22, 22, 16, 8, -15,
        -10, 10, 22, 30, 30, 22, 10, -10,
        -10, 8, 20, 28, 28, 20, 8, -10,
        -15, 6, 14, 20, 20, 14, 6, -15,
        -25, -8, 2, 6, 6, 2, -8, -25,
        -45, -25, -15, -10, -10, -15, -25, -45,
    ],
    chess.BISHOP: [
        -18, -8, -8, -6, -6, -8, -8, -18,
        -8, 8, 6, 8, 8, 6, 8, -8,
        -8, 10, 14, 16, 16, 14, 10, -8,
        -6, 8, 16, 20, 20, 16, 8, -6,
        -6, 8, 16, 20, 20, 16, 8, -6,
        -8, 8, 14, 16, 16, 14, 8, -8,
        -8, 6, 8, 8, 8, 8, 6, -8,
        -18, -8, -8, -6, -6, -8, -8, -18,
    ],
    chess.ROOK: [
        0, 0, 4, 8, 8, 4, 0, 0,
        0, 4, 8, 12, 12, 8, 4, 0,
        -2, 0, 4, 8, 8, 4, 0, -2,
        -2, 0, 4, 8, 8, 4, 0, -2,
        -2, 0, 4, 8, 8, 4, 0, -2,
        -2, 0, 4, 8, 8, 4, 0, -2,
        0, 4, 8, 12, 12, 8, 4, 0,
        0, 0, 4, 8, 8, 4, 0, 0,
    ],
    chess.QUEEN: [
        -16, -8, -8, -4, -4, -8, -8, -16,
        -8, 0, 4, 4, 4, 4, 0, -8,
        -8, 4, 8, 8, 8, 8, 4, -8,
        -4, 4, 8, 10, 10, 8, 4, -4,
        -4, 4, 8, 10, 10, 8, 4, -4,
        -8, 4, 8, 8, 8, 8, 4, -8,
        -8, 0, 4, 4, 4, 4, 0, -8,
        -16, -8, -8, -4, -4, -8, -8, -16,
    ],
    chess.KING: [
        20, 30, 10, 0, 0, 10, 30, 20,
        20, 20, 0, 0, 0, 0, 20, 20,
        -10, -20, -20, -30, -30, -20, -20, -10,
        -20, -30, -30, -40, -40, -30, -30, -20,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
    ],
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


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


class _Searcher:
    def __init__(self, deadline: float, node_limit: int) -> None:
        self.deadline = deadline
        self.node_limit = node_limit
        self.nodes = 0
        self.stopped = False

    def out_of_time(self) -> bool:
        if self.nodes >= self.node_limit:
            return True
        return time.perf_counter() >= self.deadline

    def search_root(self, board: chess.Board, depth: int) -> chess.Move | None:
        best_move = None
        best_score = -INF
        alpha = -INF
        beta = INF
        moves = self.order_moves(board, list(board.legal_moves))
        for mv in moves:
            if self.out_of_time():
                self.stopped = True
                break
            board.push(mv)
            score = -self.negamax(board, depth - 1, -beta, -alpha, 1)
            board.pop()
            if self.stopped:
                break
            if score > best_score:
                best_score = score
                best_move = mv
            if score > alpha:
                alpha = score
        return best_move

    def negamax(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
    ) -> int:
        self.nodes += 1
        if self.out_of_time():
            self.stopped = True
            return self.static_eval(board)
        if board.is_checkmate():
            return -MATE_SCORE + ply
        if _is_drawish(board):
            return 0
        if depth <= 0:
            return self.quiescence(board, alpha, beta, ply)

        best = -INF
        for mv in self.order_moves(board, list(board.legal_moves)):
            board.push(mv)
            score = -self.negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if self.stopped:
                return score
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        return best

    def quiescence(
        self,
        board: chess.Board,
        alpha: int,
        beta: int,
        ply: int,
    ) -> int:
        self.nodes += 1
        stand_pat = self.static_eval(board)
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
        if self.out_of_time() or ply >= 8:
            if self.out_of_time():
                self.stopped = True
            return alpha

        noisy = []
        for mv in board.legal_moves:
            if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
                noisy.append(mv)
        for mv in self.order_moves(board, noisy):
            board.push(mv)
            if board.is_checkmate():
                score = MATE_SCORE - ply
            else:
                score = -self.quiescence(board, -beta, -alpha, ply + 1)
            board.pop()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    def order_moves(self, board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
        return sorted(moves, key=lambda mv: self.move_order_score(board, mv), reverse=True)

    def move_order_score(self, board: chess.Board, mv: chess.Move) -> int:
        score = 0
        if board.gives_check(mv):
            score += 7000
        if mv.promotion:
            score += PIECE_VALUES.get(mv.promotion, 0) + 6000
        if board.is_capture(mv):
            victim = board.piece_at(mv.to_square)
            if victim is None and board.is_en_passant(mv):
                victim_value = PIECE_VALUES[chess.PAWN]
            else:
                victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
            attacker = board.piece_at(mv.from_square)
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
            score += 10000 + 10 * victim_value - attacker_value
        piece = board.piece_at(mv.from_square)
        if piece:
            if mv.to_square in CENTER:
                score += 80
            elif mv.to_square in EXTENDED_CENTER:
                score += 35
            if _is_early_minor_development(board, piece, mv):
                score += 70
            if _is_castling_move(piece, mv):
                score += 120
        return score

    def static_eval(self, board: chess.Board) -> int:
        if board.is_checkmate():
            return -MATE_SCORE
        if board.is_stalemate() or board.is_insufficient_material():
            return 0

        score = 0
        for sq, piece in board.piece_map().items():
            value = PIECE_VALUES[piece.piece_type]
            pst_sq = sq if piece.color == chess.WHITE else chess.square_mirror(sq)
            value += PST[piece.piece_type][pst_sq]
            if piece.color == chess.WHITE:
                score += value
            else:
                score -= value

        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += 35
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= 35

        turn = board.turn
        board.turn = chess.WHITE
        white_mobility = board.legal_moves.count() if not board.is_checkmate() else 0
        board.turn = chess.BLACK
        black_mobility = board.legal_moves.count() if not board.is_checkmate() else 0
        board.turn = turn
        score += 2 * (white_mobility - black_mobility)

        if _has_any_castling_rights(board, chess.WHITE):
            score += 10
        if _has_any_castling_rights(board, chess.BLACK):
            score -= 10

        return score if board.turn == chess.WHITE else -score


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

    hinted = _extract_legal_hint_set(observation)
    hinted_legal = [mv for mv in legal_moves if mv.uci() in hinted]
    if hinted_legal:
        legal_moves = hinted_legal

    for mv in _ordered_fallback_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return _format_move(board, mv, output_format)

    book_move = _opening_move(board, legal_moves)
    if book_move is not None and max(1, int(time_limit_ms)) <= 20:
        return _format_move(board, book_move, output_format)

    safe_ms = max(5, min(int(time_limit_ms or 100), 250))
    deadline = time.perf_counter() + max(0.003, (safe_ms - 4) / 1000.0)
    if safe_ms >= 80:
        node_limit = DEFAULT_NODE_LIMIT
    else:
        node_limit = max(1200, DEFAULT_NODE_LIMIT * safe_ms // 80)
    searcher = _Searcher(deadline=deadline, node_limit=node_limit)

    best = None
    max_depth = 2
    if safe_ms >= 45:
        max_depth = 3
    if safe_ms >= 120 and len(legal_moves) <= 28:
        max_depth = 4

    for depth in range(1, max_depth + 1):
        if searcher.out_of_time():
            break
        candidate = searcher.search_root(board, depth)
        if not searcher.stopped and candidate in legal_moves:
            best = candidate
        if searcher.stopped:
            break

    if best is None:
        if book_move in legal_moves:
            best = book_move
        else:
            best = _safe_fallback(board, legal_moves)
    if best not in board.legal_moves:
        best = _safe_fallback(board, list(board.legal_moves))
    return _format_move(board, best, output_format)


def _parse_observation(observation: Any) -> chess.Board:
    fen = None
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    if isinstance(observation, str):
        fen = observation.strip()
    elif isinstance(observation, dict):
        for key in ("fen", "board", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
    else:
        value = getattr(observation, "fen", None)
        if callable(value):
            try:
                fen = value()
            except Exception:
                fen = None
        elif isinstance(value, str):
            fen = value

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _extract_legal_hint_set(observation: Any) -> set[str]:
    hints: set[str] = set()
    if not isinstance(observation, dict):
        return hints
    for key in ("legal_moves", "legalMoves", "moves"):
        raw = observation.get(key)
        if isinstance(raw, (list, tuple, set)):
            for item in raw:
                text = str(item).strip()
                if text:
                    hints.add(text)
    return hints


def _opening_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move | None:
    if board.fullmove_number > 8:
        return None
    preferred_white = [
        "e2e4",
        "d2d4",
        "g1f3",
        "c2c4",
        "b1c3",
        "f1c4",
        "f1b5",
        "e1g1",
    ]
    preferred_black = [
        "e7e5",
        "c7c5",
        "e7e6",
        "d7d5",
        "g8f6",
        "b8c6",
        "f8c5",
        "f8b4",
        "e8g8",
    ]
    legal = {mv.uci(): mv for mv in legal_moves}
    preferred = preferred_white if board.turn == chess.WHITE else preferred_black
    for uci in preferred:
        mv = legal.get(uci)
        if mv is not None:
            return mv
    return None


def _safe_fallback(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    ordered = _ordered_fallback_moves(board, legal_moves)
    return ordered[0] if ordered else next(iter(board.legal_moves))


def _ordered_fallback_moves(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> list[chess.Move]:
    def key(mv: chess.Move) -> int:
        score = 0
        if board.gives_check(mv):
            score += 5000
        if mv.promotion:
            score += 4000 + PIECE_VALUES.get(mv.promotion, 0)
        if board.is_capture(mv):
            victim_value = _captured_piece_value(board, mv)
            attacker = board.piece_at(mv.from_square)
            if attacker:
                attacker_value = PIECE_VALUES.get(attacker.piece_type, 0)
            else:
                attacker_value = 0
            score += 3000 + 10 * victim_value - attacker_value
        piece = board.piece_at(mv.from_square)
        if piece:
            if mv.to_square in CENTER:
                score += 100
            if _is_early_minor_development(board, piece, mv):
                score += 60
            if _is_castling_move(piece, mv):
                score += 120
        return score

    return sorted(legal_moves, key=lambda mv: (key(mv), mv.uci()), reverse=True)


def _captured_piece_value(board: chess.Board, mv: chess.Move) -> int:
    if board.is_en_passant(mv):
        return PIECE_VALUES[chess.PAWN]
    victim = board.piece_at(mv.to_square)
    if victim:
        return PIECE_VALUES.get(victim.piece_type, 0)
    return 0


def _is_castling_move(piece: chess.Piece, mv: chess.Move) -> bool:
    if piece.piece_type != chess.KING:
        return False
    file_delta = abs(chess.square_file(mv.to_square) - chess.square_file(mv.from_square))
    return file_delta == 2


def _is_early_minor_development(
    board: chess.Board,
    piece: chess.Piece,
    mv: chess.Move,
) -> bool:
    if piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return False
    if board.fullmove_number > 12:
        return False
    home_rank = chess.BB_RANK_1 if piece.color == chess.WHITE else chess.BB_RANK_8
    return bool(chess.BB_SQUARES[mv.from_square] & home_rank)


def _has_any_castling_rights(board: chess.Board, color: chess.Color) -> bool:
    return (
        board.has_kingside_castling_rights(color)
        or board.has_queenside_castling_rights(color)
    )


def _is_drawish(board: chess.Board) -> bool:
    return (
        board.is_stalemate()
        or board.is_insufficient_material()
        or board.can_claim_fifty_moves()
        or board.can_claim_threefold_repetition()
    )


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").lower().strip()
    if mv not in board.legal_moves:
        mv = _safe_fallback(board, list(board.legal_moves))
    if fmt == "san":
        try:
            return board.san(mv)
        except Exception:
            return mv.uci()
    return mv.uci()


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)
