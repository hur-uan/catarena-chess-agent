"""Safer CATArena chess agent with local-engine search and tactical guardrails.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This version intentionally avoids optional external clients. It uses the in-repo
engine when available, and a small deterministic python-chess fallback otherwise.
Every returned move is validated against python-chess legal_moves.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import chess

try:
    from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
except Exception:  # pragma: no cover - fallback for standalone validation contexts
    EngineConfig = None  # type: ignore[assignment]
    select_move_record = None  # type: ignore[assignment]

    def cp_to_wdl(cp: int, mate_distance: int | None) -> dict[str, float]:
        if mate_distance is not None:
            return {"win": 1.0 if mate_distance > 0 else 0.0, "draw": 0.0, "loss": 0.0 if mate_distance > 0 else 1.0}
        clipped = max(-1000, min(1000, cp))
        win = 1.0 / (1.0 + 10.0 ** (-clipped / 400.0))
        return {"win": win, "draw": 0.0, "loss": 1.0 - win}

    @dataclass
    class SearchRecord:  # type: ignore[no-redef]
        fen: str
        selected_move: str
        cp: int = 0
        mate_distance: int | None = None
        wdl: dict[str, float] = field(default_factory=dict)
        depth: int = 0
        elapsed_ms: float = 0.0
        nodes: int = 0
        qnodes: int = 0
        legal_moves: list[str] = field(default_factory=list)
        principal_variation: list[str] = field(default_factory=list)
        fallback_used: bool = True
        backend: str = "fallback"
        engine_config: dict[str, object] = field(default_factory=dict)


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
MATE_SCORE = 100000
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
    return select_move_details(observation, output_format, time_limit_ms).selected_move


def select_move_details(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> SearchRecord:
    """Return the selected move and lightweight diagnostics."""
    start = time.perf_counter()
    board = _parse_board(observation)
    legal_moves = list(board.legal_moves)
    legal_uci = [move.uci() for move in legal_moves]

    if not legal_moves or board.is_game_over(claim_draw=False):
        return SearchRecord(
            fen=board.fen(),
            selected_move="",
            cp=0,
            mate_distance=None,
            wdl=cp_to_wdl(0, None),
            depth=0,
            elapsed_ms=_elapsed_ms(start),
            nodes=0,
            qnodes=0,
            legal_moves=legal_uci,
            fallback_used=True,
            backend="terminal",
        )

    mate_move = _find_mate_in_one(board)
    if mate_move is not None:
        return _make_record(board, mate_move, start, 1, 1, "mate_in_one", output_format)

    engine_move = _local_engine_move(observation, time_limit_ms)
    if engine_move in legal_uci:
        move_obj = chess.Move.from_uci(engine_move)
        guarded = _guard_against_mate_in_one(board, move_obj)
        return _make_record(board, guarded, start, 0, 0, "local_engine_guarded", output_format)

    fallback_move, depth, nodes = _fallback_search(board, time_limit_ms)
    guarded = _guard_against_mate_in_one(board, fallback_move)
    return _make_record(board, guarded, start, depth, nodes, "bounded_fallback", output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _local_engine_move(observation: Any, time_limit_ms: int) -> str:
    if EngineConfig is None or select_move_record is None:
        return ""
    try:
        config = EngineConfig()
        record = select_move_record(
            observation=observation,
            output_format="uci",
            time_limit_ms=max(1, int(time_limit_ms)),
            config=config,
        )
    except Exception:
        return ""
    return str(getattr(record, "selected_move", "")).strip()


def _parse_board(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    if isinstance(observation, dict):
        fen = observation.get("fen") or observation.get("board") or observation.get("state")
        if isinstance(fen, str):
            return _board_from_string(fen)
    if isinstance(observation, str):
        return _board_from_string(observation)
    return chess.Board()


def _board_from_string(value: str) -> chess.Board:
    text = value.strip()
    if not text:
        return chess.Board()
    try:
        return chess.Board(text)
    except ValueError:
        board = chess.Board()
        for token in text.replace("\n", " ").split():
            try:
                move = chess.Move.from_uci(token)
            except ValueError:
                continue
            if move in board.legal_moves:
                board.push(move)
        return board


def _find_mate_in_one(board: chess.Board) -> chess.Move | None:
    for candidate in _ordered_moves(board):
        board.push(candidate)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return candidate
    return None


def _allows_opponent_mate_in_one(board: chess.Board, move_obj: chess.Move) -> bool:
    if move_obj not in board.legal_moves:
        return True
    board.push(move_obj)
    mate = _find_mate_in_one(board) is not None
    board.pop()
    return mate


def _guard_against_mate_in_one(board: chess.Board, preferred: chess.Move) -> chess.Move:
    if preferred in board.legal_moves and not _allows_opponent_mate_in_one(board, preferred):
        return preferred
    best_safe: chess.Move | None = None
    best_score = -10**9
    for candidate in _ordered_moves(board):
        if _allows_opponent_mate_in_one(board, candidate):
            continue
        board.push(candidate)
        score = -_static_eval_for_side_to_move(board)
        board.pop()
        if score > best_score:
            best_score = score
            best_safe = candidate
    if best_safe is not None:
        return best_safe
    if preferred in board.legal_moves:
        return preferred
    return next(iter(board.legal_moves))


def _fallback_search(board: chess.Board, time_limit_ms: int) -> tuple[chess.Move, int, int]:
    legal = list(board.legal_moves)
    if len(legal) == 1:
        return legal[0], 1, 1
    budget_ms = max(5, min(80, int(time_limit_ms) - 6))
    deadline = time.perf_counter() + budget_ms / 1000.0
    max_depth = 3 if budget_ms >= 45 and len(legal) <= 42 else 2
    best_move = _ordered_moves(board)[0]
    best_score = -10**9
    nodes = 0
    completed_depth = 0
    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        depth_best = best_move
        depth_score = -10**9
        depth_complete = True
        alpha = -10**9
        beta = 10**9
        for candidate in _ordered_moves(board):
            if time.perf_counter() >= deadline:
                depth_complete = False
                break
            board.push(candidate)
            score, searched = _negamax(board, depth - 1, -beta, -alpha, deadline)
            score = -score
            nodes += searched + 1
            board.pop()
            if score > depth_score:
                depth_score = score
                depth_best = candidate
            if score > alpha:
                alpha = score
        if depth_complete:
            best_move = depth_best
            best_score = depth_score
            completed_depth = depth
        else:
            break
    _ = best_score
    return best_move, completed_depth, nodes


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, deadline: float) -> tuple[int, int]:
    if time.perf_counter() >= deadline:
        return _static_eval_for_side_to_move(board), 0
    if board.is_checkmate():
        return -MATE_SCORE, 1
    if board.is_stalemate() or board.is_insufficient_material():
        return 0, 1
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, 3)
    nodes = 1
    value = -10**9
    for candidate in _ordered_moves(board):
        if time.perf_counter() >= deadline:
            break
        board.push(candidate)
        score, child_nodes = _negamax(board, depth - 1, -beta, -alpha, deadline)
        score = -score
        nodes += child_nodes
        board.pop()
        if score > value:
            value = score
        if value > alpha:
            alpha = value
        if alpha >= beta:
            break
    return value, nodes


def _quiescence(board: chess.Board, alpha: int, beta: int, deadline: float, depth: int) -> tuple[int, int]:
    stand_pat = _static_eval_for_side_to_move(board)
    if stand_pat >= beta or depth <= 0 or time.perf_counter() >= deadline:
        return stand_pat, 1
    if stand_pat > alpha:
        alpha = stand_pat
    nodes = 1
    noisy = [move for move in _ordered_moves(board) if board.is_capture(move) or move.promotion or board.gives_check(move)]
    for candidate in noisy[:18]:
        if time.perf_counter() >= deadline:
            break
        board.push(candidate)
        score, child_nodes = _quiescence(board, -beta, -alpha, deadline, depth - 1)
        score = -score
        nodes += child_nodes
        board.pop()
        if score >= beta:
            return beta, nodes
        if score > alpha:
            alpha = score
    return alpha, nodes


def _ordered_moves(board: chess.Board) -> list[chess.Move]:
    moves = list(board.legal_moves)
    moves.sort(key=lambda candidate: _move_order_score(board, candidate), reverse=True)
    return moves


def _move_order_score(board: chess.Board, move_obj: chess.Move) -> int:
    score = 0
    if move_obj.promotion:
        score += 9000 + PIECE_VALUES.get(move_obj.promotion, 0)
    if board.is_capture(move_obj):
        victim = board.piece_at(move_obj.to_square)
        if victim is None and board.is_en_passant(move_obj):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(move_obj.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 5000 + 10 * victim_value - attacker_value
    if board.gives_check(move_obj):
        score += 2500
    if board.is_castling(move_obj):
        score += 700
    if move_obj.to_square in CENTER_SQUARES:
        score += 180
    elif move_obj.to_square in EXTENDED_CENTER:
        score += 70
    piece = board.piece_at(move_obj.from_square)
    if piece and piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        rank = chess.square_rank(move_obj.to_square)
        score += 20 * (rank if piece.color == chess.WHITE else 7 - rank)
    return score


def _static_eval_for_side_to_move(board: chess.Board) -> int:
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
    mobility = min(40, board.legal_moves.count()) * 2
    score = white_score - black_score
    score += mobility if board.turn == chess.WHITE else -mobility
    return score if board.turn == chess.WHITE else -score


def _piece_square_bonus(piece: chess.Piece, square: chess.Square) -> int:
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    if piece.color == chess.BLACK:
        rank_idx = 7 - rank_idx
    center_distance = abs(file_idx - 3.5) + abs(rank_idx - 3.5)
    if piece.piece_type == chess.PAWN:
        return rank_idx * 5 - int(center_distance * 2)
    if piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        return 24 - int(center_distance * 7) + rank_idx * 2
    if piece.piece_type == chess.ROOK:
        return rank_idx * 2
    if piece.piece_type == chess.QUEEN:
        return 8 - int(center_distance * 2)
    if piece.piece_type == chess.KING:
        return -int(center_distance * 3) if rank_idx <= 5 else int(center_distance * 2)
    return 0


def _make_record(
    board: chess.Board,
    move_obj: chess.Move,
    start: float,
    depth: int,
    nodes: int,
    backend: str,
    output_format: str,
) -> SearchRecord:
    legal = list(board.legal_moves)
    if move_obj not in legal:
        move_obj = legal[0]
    selected = _format_move(board, move_obj, output_format)
    cp = _score_move_for_record(board, move_obj)
    return SearchRecord(
        fen=board.fen(),
        selected_move=selected,
        cp=cp,
        mate_distance=1 if backend == "mate_in_one" else None,
        wdl=cp_to_wdl(cp, 1 if backend == "mate_in_one" else None),
        depth=depth,
        elapsed_ms=_elapsed_ms(start),
        nodes=nodes,
        qnodes=0,
        legal_moves=[move.uci() for move in legal],
        principal_variation=[move_obj.uci()],
        fallback_used=backend != "local_engine_guarded",
        backend=backend,
        engine_config={"external_clients": False, "mate_guard": True},
    )


def _score_move_for_record(board: chess.Board, move_obj: chess.Move) -> int:
    board.push(move_obj)
    if board.is_checkmate():
        score = MATE_SCORE - 1
    else:
        score = -_static_eval_for_side_to_move(board)
    board.pop()
    return int(max(-MATE_SCORE, min(MATE_SCORE, score)))


def _format_move(board: chess.Board, move_obj: chess.Move, output_format: str) -> str:
    fmt = output_format.lower().strip()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0
