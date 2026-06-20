"""Safe tactical CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This version keeps the proven internal search backend but removes the optional
external-client path and adds a very small deterministic tactical safety layer:
- play mate in one immediately when available;
- validate all selected moves against python-chess legal_moves;
- avoid a selected move that permits an immediate mate reply when a safe
  alternative exists.
"""

from __future__ import annotations

from typing import Any

import chess

from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
from tools.board_parser import parse_observation

DEFAULT_ENGINE_CONFIG = EngineConfig()
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}
CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
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


def select_move(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> str:
    """Choose a legal chess move for the supplied observation."""
    return select_move_details(
        observation=observation,
        output_format=output_format,
        time_limit_ms=time_limit_ms,
    ).selected_move


def select_move_details(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> SearchRecord:
    """Return the selected move and lightweight search diagnostics."""
    board = _parse_board_safe(observation)
    legal_moves = list(board.legal_moves)
    legal_uci = [move.uci() for move in legal_moves]

    if not legal_moves or board.is_game_over(claim_draw=False):
        return _make_record(board, "", legal_uci, depth=0, fallback_used=False)

    mate_move = _find_mate_in_one(board)
    if mate_move is not None:
        return _make_record(
            board,
            _format_move(board, mate_move, output_format),
            legal_uci,
            cp=48999,
            mate_distance=1,
            depth=1,
            fallback_used=False,
            backend="tactical_mate_in_one",
        )

    try:
        record = select_move_record(
            observation=observation,
            output_format=output_format,
            time_limit_ms=time_limit_ms,
            config=DEFAULT_ENGINE_CONFIG,
        )
    except (ValueError, TypeError, AttributeError, RuntimeError):
        fallback = _best_fallback_move(board, require_no_mate_reply=True)
        return _make_record(
            board,
            _format_move(board, fallback, output_format),
            legal_uci,
            depth=0,
            fallback_used=True,
            backend="exception_fallback",
        )

    return _guard_record(board, record, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_board_safe(observation: Any) -> chess.Board:
    try:
        board = parse_observation(observation)
        if isinstance(board, chess.Board):
            return board
    except (ValueError, TypeError, AttributeError):
        pass

    fen = ""
    if isinstance(observation, dict):
        fen = str(observation.get("fen", "")).strip()
    elif isinstance(observation, str):
        text = observation.strip()
        if "/" in text and " " in text:
            fen = text

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _make_record(
    board: chess.Board,
    selected_move: str,
    legal_moves: list[str],
    cp: int = 0,
    mate_distance: int | None = None,
    depth: int = 0,
    fallback_used: bool = False,
    backend: str = "safe_wrapper",
) -> SearchRecord:
    return SearchRecord(
        fen=board.fen(),
        selected_move=selected_move,
        cp=cp,
        mate_distance=mate_distance,
        wdl=cp_to_wdl(cp, mate_distance),
        depth=depth,
        elapsed_ms=0.0,
        nodes=0,
        qnodes=0,
        legal_moves=legal_moves,
        fallback_used=fallback_used,
        backend=backend,
        engine_config={"safety_layer": True, "external_client": False},
    )


def _guard_record(board: chess.Board, record: SearchRecord, output_format: str) -> SearchRecord:
    legal_moves = list(board.legal_moves)
    legal_uci = {move.uci() for move in legal_moves}
    selected = str(getattr(record, "selected_move", "")).strip()

    selected_move = _move_from_output(board, selected, output_format)
    if selected_move is None or selected_move.uci() not in legal_uci:
        fallback = _best_fallback_move(board, require_no_mate_reply=True)
        record.selected_move = _format_move(board, fallback, output_format)
        record.fallback_used = True
        record.backend = "legal_fallback"
        return record

    # The arena primarily requests UCI moves.  For non-UCI outputs, avoid
    # changing a valid engine response because SAN/LAN parsing conventions can
    # vary between integrations.
    if _wants_uci(output_format) and _allows_immediate_mate(board, selected_move):
        safer = _best_fallback_move(board, require_no_mate_reply=True)
        if not _allows_immediate_mate(board, safer):
            record.selected_move = safer.uci()
            record.fallback_used = True
            record.backend = "mate_threat_guard"

    return record


def _move_from_output(board: chess.Board, selected: str, output_format: str) -> chess.Move | None:
    if not selected:
        return None
    try:
        move = chess.Move.from_uci(selected)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass

    if not _wants_uci(output_format):
        try:
            move = board.parse_san(selected)
            if move in board.legal_moves:
                return move
        except ValueError:
            return None
    return None


def _wants_uci(output_format: str) -> bool:
    normalized = output_format.lower().strip()
    return normalized in {"", "uci", "default"}


def _format_move(board: chess.Board, move_to_format: chess.Move, output_format: str) -> str:
    normalized = output_format.lower().strip()
    if normalized in {"san", "algebraic"}:
        try:
            return board.san(move_to_format)
        except (ValueError, AssertionError):
            return move_to_format.uci()
    return move_to_format.uci()


def _find_mate_in_one(board: chess.Board) -> chess.Move | None:
    best_move: chess.Move | None = None
    best_score = -10**9
    for candidate in board.legal_moves:
        board.push(candidate)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            score = _score_move(board, candidate)
            if score > best_score:
                best_score = score
                best_move = candidate
    return best_move


def _allows_immediate_mate(board: chess.Board, candidate: chess.Move) -> bool:
    if candidate not in board.legal_moves:
        return True
    board.push(candidate)
    try:
        if board.is_game_over(claim_draw=False):
            return False
        for reply in board.legal_moves:
            board.push(reply)
            is_mate = board.is_checkmate()
            board.pop()
            if is_mate:
                return True
        return False
    finally:
        board.pop()


def _best_fallback_move(board: chess.Board, require_no_mate_reply: bool) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return chess.Move.null()

    best_move = legal_moves[0]
    best_score = -10**9
    found_safe = False

    for candidate in legal_moves:
        unsafe = _allows_immediate_mate(board, candidate)
        if require_no_mate_reply and unsafe:
            score = -10**8 + _score_move(board, candidate)
        else:
            score = _score_move(board, candidate)
            if require_no_mate_reply:
                found_safe = True
        if score > best_score:
            best_score = score
            best_move = candidate

    if require_no_mate_reply and not found_safe:
        for candidate in legal_moves:
            score = _score_move(board, candidate)
            if score > best_score:
                best_score = score
                best_move = candidate
    return best_move


def _score_move(board: chess.Board, candidate: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_at(candidate.from_square)

    if candidate.promotion:
        score += 7000 + PIECE_VALUES.get(candidate.promotion, 0)

    if board.is_capture(candidate):
        if board.is_en_passant(candidate):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim = board.piece_at(candidate.to_square)
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0
        score += 5000 + (10 * victim_value) - attacker_value

    board.push(candidate)
    try:
        if board.is_checkmate():
            score += 100000
        elif board.is_check():
            score += 350
    finally:
        board.pop()

    if board.is_castling(candidate):
        score += 250
    if candidate.to_square in CENTER_SQUARES:
        score += 80
    elif candidate.to_square in EXTENDED_CENTER:
        score += 30

    if moving_piece is not None:
        if moving_piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
            home_rank = 0 if moving_piece.color == chess.WHITE else 7
            if chess.square_rank(candidate.from_square) == home_rank:
                score += 90
        if moving_piece.piece_type == chess.PAWN:
            rank = chess.square_rank(candidate.to_square)
            score += rank * 4 if moving_piece.color == chess.WHITE else (7 - rank) * 4

    # Deterministic tie-breaker that is stable across processes.
    score += candidate.to_square - candidate.from_square
    return score
