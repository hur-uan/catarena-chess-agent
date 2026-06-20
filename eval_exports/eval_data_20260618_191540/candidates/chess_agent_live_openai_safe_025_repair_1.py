"""Safe CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This agent avoids match-time network and external-engine calls. It uses the
local project search engine when available, validates every selected move with
python-chess, and falls back to a deterministic tactical heuristic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import chess

try:
    from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
except ImportError:  # pragma: no cover - only used in stripped-down harnesses.
    EngineConfig = None  # type: ignore[assignment]
    select_move_record = None  # type: ignore[assignment]

    def cp_to_wdl(
        cp: int,
        mate_distance: int | None = None,
    ) -> dict[str, float]:
        if mate_distance is not None:
            if mate_distance > 0:
                return {"win": 1.0, "draw": 0.0, "loss": 0.0}
            return {"win": 0.0, "draw": 0.0, "loss": 1.0}
        if cp > 100:
            return {"win": 0.55, "draw": 0.35, "loss": 0.10}
        if cp < -100:
            return {"win": 0.10, "draw": 0.35, "loss": 0.55}
        return {"win": 0.25, "draw": 0.50, "loss": 0.25}

    @dataclass
    class SearchRecord:  # type: ignore[no-redef]
        fen: str
        selected_move: str
        cp: int = 0
        mate_distance: int | None = None
        wdl: object | None = None
        depth: int = 0
        elapsed_ms: float = 0.0
        nodes: int = 0
        qnodes: int = 0
        legal_moves: list[str] | None = None
        principal_variation: list[str] | None = None
        fallback_used: bool = True
        backend: str = "heuristic"
        engine_config: dict[str, object] | None = None


PIECE_VALUES: dict[int, int] = {
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
    return select_move_details(observation, output_format, time_limit_ms).selected_move


def select_move_details(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> SearchRecord:
    """Return the selected move and lightweight diagnostics."""
    start = time.perf_counter()
    board = _parse_observation(observation)
    legal_moves = sorted(board.legal_moves, key=lambda move_obj: move_obj.uci())
    legal_uci = [move_obj.uci() for move_obj in legal_moves]

    if not legal_moves or board.is_game_over(claim_draw=False):
        return _record(board, "", legal_uci, start, "none", True)

    hinted = _extract_legal_hint_uci(observation, legal_uci)
    candidate_pool = [
        move_obj for move_obj in legal_moves if not hinted or move_obj.uci() in hinted
    ]
    if not candidate_pool:
        candidate_pool = legal_moves

    if len(candidate_pool) == 1:
        return _record_for_move(
            board,
            candidate_pool[0],
            output_format,
            legal_uci,
            start,
            "forced",
            False,
        )

    mate_move = _find_mate_in_one(board, candidate_pool)
    if mate_move is not None:
        return _record_for_move(
            board,
            mate_move,
            output_format,
            legal_uci,
            start,
            "mate_in_one",
            False,
            mate_distance=1,
        )

    engine_move = _select_local_engine_move(
        observation,
        board,
        legal_uci,
        hinted,
        time_limit_ms,
    )
    if engine_move is not None:
        return _record_for_move(
            board,
            engine_move,
            output_format,
            legal_uci,
            start,
            "local_engine",
            False,
        )

    fallback_move = _select_heuristic_move(board, candidate_pool)
    return _record_for_move(
        board,
        fallback_move,
        output_format,
        legal_uci,
        start,
        "heuristic",
        True,
    )


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen: str | None = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
    elif isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _extract_legal_hint_uci(observation: Any, legal_uci: list[str]) -> set[str]:
    legal_set = set(legal_uci)
    hinted: set[str] = set()
    if not isinstance(observation, dict):
        return hinted

    for key in ("legal_moves", "legalMoves", "moves"):
        raw = observation.get(key)
        if not isinstance(raw, (list, tuple, set)):
            continue
        for item in raw:
            text = str(item).strip()
            if text in legal_set:
                hinted.add(text)
    return hinted


def _select_local_engine_move(
    observation: Any,
    board: chess.Board,
    legal_uci: list[str],
    hinted: set[str],
    time_limit_ms: int,
) -> chess.Move | None:
    if EngineConfig is None or select_move_record is None:
        return None

    try:
        config = EngineConfig()
        record = select_move_record(
            observation=observation,
            output_format="uci",
            time_limit_ms=max(1, int(time_limit_ms)),
            config=config,
        )
    except Exception:
        return None

    selected = str(getattr(record, "selected_move", "")).strip()
    if not selected or selected not in legal_uci:
        return None
    if hinted and selected not in hinted:
        return None

    try:
        move_obj = chess.Move.from_uci(selected)
    except ValueError:
        return None
    if move_obj in board.legal_moves:
        return move_obj
    return None


def _find_mate_in_one(
    board: chess.Board,
    moves: list[chess.Move],
) -> chess.Move | None:
    for candidate in sorted(moves, key=lambda move_obj: move_obj.uci()):
        board.push(candidate)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return candidate
    return None


def _select_heuristic_move(board: chess.Board, moves: list[chess.Move]) -> chess.Move:
    best_move = sorted(moves, key=lambda move_obj: move_obj.uci())[0]
    best_score: tuple[int, str] | None = None
    for candidate in moves:
        score = _score_move(board, candidate)
        key = (score, _reverse_uci_key(candidate))
        if best_score is None or key > best_score:
            best_score = key
            best_move = candidate
    return best_move


def _score_move(board: chess.Board, move_obj: chess.Move) -> int:
    moving_piece = board.piece_at(move_obj.from_square)
    if moving_piece is None:
        return -1_000_000

    score = 0
    moving_value = PIECE_VALUES.get(moving_piece.piece_type, 0)

    if board.is_capture(move_obj):
        victim = board.piece_at(move_obj.to_square)
        victim_value = PIECE_VALUES.get(victim.piece_type, 100) if victim else 100
        if board.is_en_passant(move_obj):
            victim_value = PIECE_VALUES[chess.PAWN]
        score += 10_000 + victim_value * 10 - moving_value

    if move_obj.promotion:
        score += 8_000 + PIECE_VALUES.get(move_obj.promotion, 0)

    if board.gives_check(move_obj):
        score += 350

    if board.is_castling(move_obj):
        score += 250

    if move_obj.to_square in CENTER_SQUARES:
        score += 80
    elif move_obj.to_square in EXTENDED_CENTER:
        score += 35

    if moving_piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        home_rank = 0 if moving_piece.color == chess.WHITE else 7
        if chess.square_rank(move_obj.from_square) == home_rank:
            score += 120
        if move_obj.to_square in CENTER_SQUARES:
            score += 60

    if moving_piece.piece_type == chess.PAWN:
        rank = chess.square_rank(move_obj.to_square)
        advancement = rank if moving_piece.color == chess.WHITE else 7 - rank
        score += advancement * 8
        if move_obj.to_square in CENTER_SQUARES:
            score += 50

    if moving_piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
        score -= 90
    rook_in_opening = moving_piece.piece_type == chess.ROOK and board.fullmove_number <= 10
    if rook_in_opening and not board.is_castling(move_obj):
        score -= 35

    board.push(move_obj)
    if board.is_checkmate():
        board.pop()
        return 1_000_000
    if board.is_stalemate() or board.is_insufficient_material():
        score -= 500
    score -= _hanging_piece_penalty(
        board,
        move_obj.to_square,
        moving_piece.color,
        moving_value,
    )
    board.pop()

    return score


def _hanging_piece_penalty(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
    value: int,
) -> int:
    opponent = not color
    if not board.attackers(opponent, square):
        return 0
    friendly_defenders = board.attackers(color, square)
    if not friendly_defenders:
        return value // 2
    return value // 6


def _format_move(
    board: chess.Board,
    move_obj: chess.Move,
    output_format: str,
) -> str:
    fmt = output_format.lower().strip()
    if fmt in {"san", "pgn", "algebraic"}:
        try:
            return board.san(move_obj)
        except AssertionError:
            return move_obj.uci()
    return move_obj.uci()


def _record_for_move(
    board: chess.Board,
    move_obj: chess.Move,
    output_format: str,
    legal_uci: list[str],
    start: float,
    backend: str,
    fallback_used: bool,
    mate_distance: int | None = None,
) -> SearchRecord:
    selected = _format_move(board, move_obj, output_format)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    cp = 49_999 if mate_distance is not None else 0
    return SearchRecord(
        fen=board.fen(),
        selected_move=selected,
        cp=cp,
        mate_distance=mate_distance,
        wdl=cp_to_wdl(cp, mate_distance),
        depth=0 if fallback_used else 1,
        elapsed_ms=elapsed_ms,
        nodes=len(legal_uci),
        qnodes=0,
        legal_moves=legal_uci,
        principal_variation=[move_obj.uci()],
        fallback_used=fallback_used,
        backend=backend,
        engine_config={
            "external_engine": "disabled",
            "safety": "python_chess_validated",
        },
    )


def _record(
    board: chess.Board,
    selected_move: str,
    legal_uci: list[str],
    start: float,
    backend: str,
    fallback_used: bool,
) -> SearchRecord:
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return SearchRecord(
        fen=board.fen(),
        selected_move=selected_move,
        cp=0,
        mate_distance=None,
        wdl=cp_to_wdl(0, None),
        depth=0,
        elapsed_ms=elapsed_ms,
        nodes=0,
        qnodes=0,
        legal_moves=legal_uci,
        principal_variation=[],
        fallback_used=fallback_used,
        backend=backend,
        engine_config={
            "external_engine": "disabled",
            "safety": "python_chess_validated",
        },
    )


def _reverse_uci_key(move_obj: chess.Move) -> str:
    """Invert UCI chars so lexicographically smaller moves win score ties."""
    return "".join(chr(255 - ord(char)) for char in move_obj.uci())
