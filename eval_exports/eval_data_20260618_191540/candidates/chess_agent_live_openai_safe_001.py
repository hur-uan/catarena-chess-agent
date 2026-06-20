"""Safe self-contained CATArena chess agent.

Public interface:
    select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation intentionally avoids network calls, subprocesses, eval/exec,
file I/O, and third-party dependencies other than python-chess.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import chess


MATE_SCORE = 100000
INF = 100000000

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Piece-square tables from White's perspective. Values are intentionally modest:
# tactics/material remain dominant, while development and king safety improve
# shallow-search choices.
PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
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
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
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
KING_END_PST = [
    -50, -30, -30, -30, -30, -30, -30, -50,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -20, -10, 0, 0, -10, -20, -30,
    -50, -40, -30, -20, -20, -30, -40, -50,
]
PSTS = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
}

BOOK_BY_BOARD_FEN = {
    chess.STARTING_BOARD_FEN: "g1f3",
    "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R": "g8f6",
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR": "g8f6",
    "rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR": "b1c3",
}


@dataclass
class SearchState:
    deadline: float
    node_limit: int
    nodes: int = 0
    stopped: bool = False

    def tick(self) -> bool:
        self.nodes += 1
        if self.nodes >= self.node_limit:
            self.stopped = True
            return False
        if self.nodes % 128 == 0 and time.monotonic() >= self.deadline:
            self.stopped = True
            return False
        return True


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

    legal_by_uci = {move.uci(): move for move in legal_moves}

    # Deterministic tiny book, always validated against python-chess legality.
    book_uci = BOOK_BY_BOARD_FEN.get(board.board_fen())
    if book_uci in legal_by_uci and board.fullmove_number <= 3:
        return _format_move(board, legal_by_uci[book_uci], output_format)

    # Immediate tactical win: never miss mate in one.
    for move_candidate in _ordered_moves(board, legal_moves):
        board.push(move_candidate)
        gives_mate = board.is_checkmate()
        board.pop()
        if gives_mate:
            return _format_move(board, move_candidate, output_format)

    fallback = _safe_fallback(board, legal_moves)
    best_move = fallback

    budget_ms = max(5, min(int(time_limit_ms or 100), 1000))
    deadline = time.monotonic() + max(0.003, budget_ms / 1000.0 * 0.82)
    node_limit = _node_limit_for_budget(budget_ms)
    max_depth = _depth_for_budget(board, budget_ms)
    state = SearchState(deadline=deadline, node_limit=node_limit)

    try:
        best_score = -INF
        for depth in range(1, max_depth + 1):
            if time.monotonic() >= deadline or state.stopped:
                break
            current_best = best_move
            current_score = -INF
            alpha = -INF
            beta = INF
            for root_move in _ordered_moves(board, legal_moves):
                if time.monotonic() >= deadline or state.stopped:
                    state.stopped = True
                    break
                board.push(root_move)
                score = -_negamax(board, depth - 1, -beta, -alpha, 1, state)
                board.pop()
                if state.stopped:
                    break
                if score > current_score or (
                    score == current_score and root_move.uci() < current_best.uci()
                ):
                    current_score = score
                    current_best = root_move
                if score > alpha:
                    alpha = score
            if not state.stopped and current_score > -INF:
                best_move = current_best
                best_score = current_score
            if best_score >= MATE_SCORE - 100:
                break
    except Exception:
        best_move = fallback

    if best_move not in board.legal_moves:
        best_move = fallback
    return _format_move(board, best_move, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    payload = observation
    if isinstance(observation, str):
        text = observation.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                payload = json.loads(text)
            except Exception:
                payload = observation
        else:
            return _board_from_fen(text)

    if isinstance(payload, dict):
        fen = _find_fen(payload)
        if fen:
            return _board_from_fen(fen)

    return chess.Board()


def _find_fen(payload: dict[str, Any]) -> str | None:
    for key in ("fen", "FEN", "board", "state"):
        value = payload.get(key)
        if isinstance(value, str) and "/" in value:
            return value.strip()
    for key in ("observation", "game", "payload"):
        value = payload.get(key)
        if isinstance(value, dict):
            nested = _find_fen(value)
            if nested:
                return nested
    return None


def _board_from_fen(fen: str) -> chess.Board:
    try:
        return chess.Board(fen)
    except Exception:
        return chess.Board()


def _format_move(board: chess.Board, chosen: chess.Move, output_format: str) -> str:
    if chosen not in board.legal_moves:
        legal = list(board.legal_moves)
        if not legal:
            return ""
        chosen = _safe_fallback(board, legal)
    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(chosen)
        except Exception:
            return chosen.uci()
    return chosen.uci()


def _safe_fallback(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    ordered = sorted(legal_moves, key=lambda move_item: move_item.uci())
    for candidate in ordered:
        board.push(candidate)
        lost = board.is_checkmate()
        board.pop()
        if lost:
            return candidate
    captures = [candidate for candidate in ordered if board.is_capture(candidate)]
    if captures:
        return max(captures, key=lambda move_item: _capture_value(board, move_item))
    return ordered[0]


def _node_limit_for_budget(budget_ms: int) -> int:
    if budget_ms < 20:
        return 900
    if budget_ms < 60:
        return 2500
    if budget_ms < 150:
        return 7000
    if budget_ms < 400:
        return 16000
    return 32000


def _depth_for_budget(board: chess.Board, budget_ms: int) -> int:
    legal_count = board.legal_moves.count()
    if budget_ms < 20:
        return 2
    if budget_ms < 70:
        return 3
    if budget_ms < 180:
        return 4 if legal_count <= 32 else 3
    if budget_ms < 500:
        return 4
    return 5 if legal_count <= 34 else 4


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    ply: int,
    state: SearchState,
) -> int:
    if not state.tick():
        return _relative_eval(board)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, ply, state)

    best = -INF
    moves = list(board.legal_moves)
    for candidate in _ordered_moves(board, moves):
        board.push(candidate)
        score = -_negamax(board, depth - 1, -beta, -alpha, ply + 1, state)
        board.pop()
        if state.stopped:
            return best if best > -INF else _relative_eval(board)
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
    ply: int,
    state: SearchState,
) -> int:
    if not state.tick():
        return _relative_eval(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _relative_eval(board)
    if not board.is_check():
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

    if board.is_check():
        tactical_moves = list(board.legal_moves)
    else:
        tactical_moves = [
            candidate
            for candidate in board.legal_moves
            if board.is_capture(candidate) or candidate.promotion is not None
        ]

    for candidate in _ordered_moves(board, tactical_moves):
        if not board.is_check() and board.is_capture(candidate):
            # Delta pruning: skip hopeless low-value captures in quiet positions.
            if stand_pat + _capture_value(board, candidate) + 120 < alpha:
                continue
        board.push(candidate)
        score = -_quiescence(board, -beta, -alpha, ply + 1, state)
        board.pop()
        if state.stopped:
            return alpha
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _relative_eval(board: chess.Board) -> int:
    score = _evaluate_white(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    phase_material = 0
    for piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
        phase_material += len(board.pieces(piece_type, chess.WHITE)) * PIECE_VALUES[piece_type]
        phase_material += len(board.pieces(piece_type, chess.BLACK)) * PIECE_VALUES[piece_type]

    endgame = phase_material <= 2200
    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        score += sign * PIECE_VALUES[piece.piece_type]
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        if piece.piece_type == chess.KING:
            score += sign * (KING_END_PST[pst_square] if endgame else KING_MID_PST[pst_square])
        else:
            score += sign * PSTS[piece.piece_type][pst_square]

    # Bishop pair and modest mobility. Mobility is computed without changing turn
    # permanently and remains small to avoid overriding tactics.
    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        score += 25
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        score -= 25

    turn = board.turn
    try:
        board.turn = chess.WHITE
        white_mobility = board.legal_moves.count() if not board.is_checkmate() else 0
        board.turn = chess.BLACK
        black_mobility = board.legal_moves.count() if not board.is_checkmate() else 0
    finally:
        board.turn = turn
    score += 2 * (white_mobility - black_mobility)

    score += _passed_pawn_bonus(board, chess.WHITE)
    score -= _passed_pawn_bonus(board, chess.BLACK)

    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 8
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 8

    return score


def _passed_pawn_bonus(board: chess.Board, color: chess.Color) -> int:
    bonus = 0
    enemy = not color
    enemy_pawns = board.pieces(chess.PAWN, enemy)
    for square in board.pieces(chess.PAWN, color):
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)
        blocked = False
        for enemy_square in enemy_pawns:
            enemy_file = chess.square_file(enemy_square)
            enemy_rank = chess.square_rank(enemy_square)
            if abs(enemy_file - file_index) <= 1:
                if color == chess.WHITE and enemy_rank > rank_index:
                    blocked = True
                    break
                if color == chess.BLACK and enemy_rank < rank_index:
                    blocked = True
                    break
        if not blocked:
            advance = rank_index if color == chess.WHITE else 7 - rank_index
            bonus += 12 + advance * advance * 2
    return bonus


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda candidate: _move_order_score(board, candidate), reverse=True)


def _move_order_score(board: chess.Board, candidate: chess.Move) -> int:
    score = 0
    if candidate.promotion is not None:
        score += 8000 + PIECE_VALUES.get(candidate.promotion, 0)
    if board.is_capture(candidate):
        score += 10000 + _capture_value(board, candidate)
    if board.gives_check(candidate):
        score += 2500
    if board.is_castling(candidate):
        score += 250
    moving_piece = board.piece_at(candidate.from_square)
    if moving_piece is not None:
        to_square = candidate.to_square if moving_piece.color == chess.WHITE else chess.square_mirror(candidate.to_square)
        from_square = candidate.from_square if moving_piece.color == chess.WHITE else chess.square_mirror(candidate.from_square)
        table = PSTS.get(moving_piece.piece_type)
        if table is not None:
            score += table[to_square] - table[from_square]
    # Deterministic tie-breaker independent of Python hash randomization.
    score -= sum(ord(char) for char in candidate.uci()) % 17
    return score


def _capture_value(board: chess.Board, candidate: chess.Move) -> int:
    victim = board.piece_at(candidate.to_square)
    if victim is None and board.is_en_passant(candidate):
        victim_value = PIECE_VALUES[chess.PAWN]
    else:
        victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
    attacker = board.piece_at(candidate.from_square)
    attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
    return victim_value * 10 - attacker_value
