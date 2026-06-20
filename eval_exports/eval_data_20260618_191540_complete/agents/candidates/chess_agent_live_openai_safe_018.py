"""Standalone safe CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This file intentionally avoids network access, file IO, subprocesses, eval/exec,
and dynamic imports.  Every returned move is checked against python-chess legal
moves; on any unexpected issue it falls back to a deterministic legal move.
"""

from __future__ import annotations

import json
import math
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

# Piece-square tables from White's point of view.  Black uses mirrored squares.
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
    0, 0, 0, 5, 5, 0, 0, 0,
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
KING_PST = [
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
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
    chess.KING: KING_PST,
}

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


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
    try:
        board = parse_observation(observation)
        legal_moves = list(board.legal_moves)
        if not legal_moves or board.is_game_over(claim_draw=False):
            return ""

        move = choose_move(board, observation, time_limit_ms)
        if move not in board.legal_moves:
            move = fallback_move(board)
        return format_move(board, move, output_format)
    except Exception:
        # Last-resort safety.  Try to return a legal move from the parsed board;
        # otherwise return the standard opening move, which is legal from startpos.
        try:
            board = parse_observation(observation)
            legal_moves = list(board.legal_moves)
            if not legal_moves:
                return ""
            return legal_moves[0].uci()
        except Exception:
            return "g1f3"


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def parse_observation(observation: Any) -> chess.Board:
    """Parse common CATArena observations into a chess.Board."""
    fen = None
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        if fen is None and isinstance(observation.get("observation"), dict):
            nested = observation["observation"]
            value = nested.get("fen")
            if isinstance(value, str) and value.strip():
                fen = value.strip()
    elif isinstance(observation, str):
        text = observation.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                payload = json.loads(text)
                if isinstance(payload, dict):
                    return parse_observation(payload)
            except json.JSONDecodeError:
                pass
        fen = text

    if not fen or fen.lower() in {"startpos", "start"}:
        return chess.Board()
    try:
        return chess.Board(fen)
    except ValueError:
        return chess.Board()


def hinted_legal_move(board: chess.Board, observation: Any) -> chess.Move | None:
    """Use a legal move hint only if it is present and legal."""
    hints: list[str] = []
    if isinstance(observation, dict):
        for key in ("legal_moves", "legalMoves", "moves"):
            value = observation.get(key)
            if isinstance(value, list):
                hints.extend(str(item).strip() for item in value)
        value = observation.get("move")
        if isinstance(value, str):
            hints.append(value.strip())
    legal = {mv.uci(): mv for mv in board.legal_moves}
    for hint in hints:
        if hint in legal:
            return legal[hint]
    return None


def choose_move(board: chess.Board, observation: Any, time_limit_ms: int) -> chess.Move:
    """Deterministic bounded search with tactical pre-checks."""
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    # If the platform supplies a restricted legal-move list, it is still only a
    # hint; search is generally stronger, but this helps malformed payloads.
    hinted = hinted_legal_move(board, observation)

    mate_move = find_immediate_mate(board)
    if mate_move is not None:
        return mate_move

    book = opening_preference(board)
    if book is not None:
        return book

    start = time.perf_counter()
    safe_ms = max(8, min(int(time_limit_ms), 250))
    deadline = start + (safe_ms / 1000.0) * 0.82
    if time_limit_ms <= 25:
        max_depth = 2
    elif time_limit_ms <= 90:
        max_depth = 3
    else:
        max_depth = 4

    best_move = hinted if hinted is not None else fallback_move(board)
    best_score = -INF
    table: dict[tuple[str, int], int] = {}

    try:
        for depth in range(1, max_depth + 1):
            if time.perf_counter() >= deadline:
                break
            current_best = best_move
            current_score = -INF
            alpha = -INF
            beta = INF
            moves = ordered_moves(board, list(board.legal_moves), previous_best=best_move)
            completed = True
            for mv in moves:
                if time.perf_counter() >= deadline:
                    completed = False
                    break
                board.push(mv)
                score = -negamax(board, depth - 1, -beta, -alpha, deadline, 1, table)
                board.pop()
                if score > current_score:
                    current_score = score
                    current_best = mv
                if score > alpha:
                    alpha = score
            if completed and current_best is not None:
                best_move = current_best
                best_score = current_score
                if best_score > MATE_SCORE - 1000:
                    break
    except TimeoutError:
        pass

    if best_move not in board.legal_moves:
        return fallback_move(board)
    return best_move


def negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
    table: dict[tuple[str, int], int],
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    key = (board.transposition_key().hex() if hasattr(board, "transposition_key") else board.board_fen() + str(board.turn), depth)
    cached = table.get(key)
    if cached is not None:
        return cached

    if depth <= 0:
        return quiescence(board, alpha, beta, deadline, ply, 4)

    best = -INF
    moves = ordered_moves(board, list(board.legal_moves), previous_best=None)
    for mv in moves:
        board.push(mv)
        score = -negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1, table)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    table[key] = best
    return best


def quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
    qdepth: int,
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat
    if qdepth <= 0:
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion is not None:
            tactical.append(mv)
    tactical = ordered_moves(board, tactical, previous_best=None)

    for mv in tactical:
        board.push(mv)
        score = -quiescence(board, -beta, -alpha, deadline, ply + 1, qdepth - 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def find_immediate_mate(board: chess.Board) -> chess.Move | None:
    for mv in ordered_moves(board, list(board.legal_moves), previous_best=None):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def opening_preference(board: chess.Board) -> chess.Move | None:
    """Small deterministic opening bias, always legal-checked."""
    if board.fullmove_number > 3:
        return None
    if board.turn == chess.WHITE:
        preferred = (
            "e2e4", "d2d4", "g1f3", "c2c4", "b1c3",
            "f1c4", "f1b5", "e1g1",
        )
    else:
        preferred = (
            "e7e5", "c7c5", "g8f6", "d7d5", "b8c6",
            "f8c5", "f8b4", "e8g8",
        )
    legal = {mv.uci(): mv for mv in board.legal_moves}
    for uci in preferred:
        mv = legal.get(uci)
        if mv is not None:
            return mv
    return None


def ordered_moves(
    board: chess.Board,
    moves: list[chess.Move],
    previous_best: chess.Move | None,
) -> list[chess.Move]:
    def score_move(mv: chess.Move) -> int:
        score = 0
        if previous_best is not None and mv == previous_best:
            score += 100000
        if mv.promotion is not None:
            score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
        if board.is_capture(mv):
            victim = board.piece_at(mv.to_square)
            attacker = board.piece_at(mv.from_square)
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 100
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 100
            score += 6000 + 10 * victim_value - attacker_value
        if board.gives_check(mv):
            score += 2500
        if mv.to_square in CENTER_SQUARES:
            score += 80
        elif mv.to_square in EXTENDED_CENTER:
            score += 35
        piece = board.piece_at(mv.from_square)
        if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 8:
            score += 25
        return score

    return sorted(moves, key=lambda move_obj: (-score_move(move_obj), move_obj.uci()))


def evaluate_for_side_to_move(board: chess.Board) -> int:
    score = evaluate_white_minus_black(board)
    return score if board.turn == chess.WHITE else -score


def evaluate_white_minus_black(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    white_bishops = 0
    black_bishops = 0
    white_pawns = list(board.pieces(chess.PAWN, chess.WHITE))
    black_pawns = list(board.pieces(chess.PAWN, chess.BLACK))

    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        pst = PST[piece.piece_type]
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        term = value + pst[pst_square]
        if piece.color == chess.WHITE:
            score += term
            if piece.piece_type == chess.BISHOP:
                white_bishops += 1
        else:
            score -= term
            if piece.piece_type == chess.BISHOP:
                black_bishops += 1

    if white_bishops >= 2:
        score += 35
    if black_bishops >= 2:
        score -= 35

    # Mobility is useful but computed once to keep runtime bounded.
    turn = board.turn
    board.turn = chess.WHITE
    white_mobility = board.legal_moves.count()
    board.turn = chess.BLACK
    black_mobility = board.legal_moves.count()
    board.turn = turn
    score += 3 * (white_mobility - black_mobility)

    score += pawn_structure_score(board, chess.WHITE, white_pawns, black_pawns)
    score -= pawn_structure_score(board, chess.BLACK, black_pawns, white_pawns)
    score += castling_and_king_safety(board)

    return int(score)


def pawn_structure_score(
    board: chess.Board,
    color: chess.Color,
    own_pawns: list[int],
    enemy_pawns: list[int],
) -> int:
    del board
    score = 0
    files = [chess.square_file(sq) for sq in own_pawns]
    enemy_files = [chess.square_file(sq) for sq in enemy_pawns]
    for sq in own_pawns:
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        if files.count(file_idx) > 1:
            score -= 12
        if file_idx - 1 not in files and file_idx + 1 not in files:
            score -= 10
        passed = True
        for enemy_sq in enemy_pawns:
            enemy_file = chess.square_file(enemy_sq)
            enemy_rank = chess.square_rank(enemy_sq)
            if abs(enemy_file - file_idx) <= 1:
                if color == chess.WHITE and enemy_rank > rank_idx:
                    passed = False
                    break
                if color == chess.BLACK and enemy_rank < rank_idx:
                    passed = False
                    break
        if passed:
            advance = rank_idx if color == chess.WHITE else 7 - rank_idx
            score += 8 + advance * 6
        if file_idx in enemy_files:
            score += 2
    return score


def castling_and_king_safety(board: chess.Board) -> int:
    score = 0
    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 10
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 10
    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)
    if white_king is not None:
        if white_king in (chess.G1, chess.C1):
            score += 25
        score -= 8 * len(board.attackers(chess.BLACK, white_king))
    if black_king is not None:
        if black_king in (chess.G8, chess.C8):
            score -= 25
        score += 8 * len(board.attackers(chess.WHITE, black_king))
    return score


def fallback_move(board: chess.Board) -> chess.Move:
    legal = list(board.legal_moves)
    if not legal:
        return chess.Move.null()
    captures = [mv for mv in legal if board.is_capture(mv)]
    if captures:
        return ordered_moves(board, captures, previous_best=None)[0]
    return sorted(legal, key=lambda mv: mv.uci())[0]


def format_move(board: chess.Board, chosen: chess.Move, output_format: str) -> str:
    if chosen not in board.legal_moves:
        chosen = fallback_move(board)
    fmt = (output_format or "uci").strip().lower()
    if fmt == "san":
        return board.san(chosen)
    return chosen.uci()
