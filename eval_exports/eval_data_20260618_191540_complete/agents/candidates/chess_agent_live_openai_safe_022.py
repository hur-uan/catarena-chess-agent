"""Safe CATArena chess agent with local tactical guardrails.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str
"""

from __future__ import annotations

import time
from typing import Any

try:
    import chess
except Exception:  # pragma: no cover - arena is expected to provide python-chess
    chess = None  # type: ignore[assignment]

try:
    from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
except Exception:  # pragma: no cover - defensive standalone fallback
    EngineConfig = None  # type: ignore[assignment]
    SearchRecord = None  # type: ignore[assignment]
    cp_to_wdl = None  # type: ignore[assignment]
    select_move_record = None  # type: ignore[assignment]

try:
    from tools.board_parser import parse_observation
except Exception:  # pragma: no cover - defensive fallback
    parse_observation = None  # type: ignore[assignment]

DEFAULT_ENGINE_CONFIG = EngineConfig() if EngineConfig is not None else None

PIECE_VALUES = {
    chess.PAWN: 100 if chess is not None else 1,
    chess.KNIGHT: 320 if chess is not None else 3,
    chess.BISHOP: 330 if chess is not None else 3,
    chess.ROOK: 500 if chess is not None else 5,
    chess.QUEEN: 900 if chess is not None else 9,
    chess.KING: 20000 if chess is not None else 100,
}
CENTER_SQUARES = {"d4", "e4", "d5", "e5"}
EXTENDED_CENTER = {"c3", "d3", "e3", "f3", "c4", "f4", "c5", "f5", "c6", "d6", "e6", "f6"}


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
    return str(select_move_details(observation, output_format, time_limit_ms).selected_move)


def select_move_details(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> Any:
    """Return selected move plus lightweight diagnostics when SearchRecord exists."""
    start = time.perf_counter()
    board = _safe_parse_board(observation)
    if board is None:
        return _engine_or_minimal_record(observation, output_format, time_limit_ms, start)

    legal_moves = list(board.legal_moves)
    legal_uci = [move.uci() for move in legal_moves]
    if not legal_moves or board.is_game_over(claim_draw=False):
        return _make_record(board, "", 0, 0, start, legal_uci, False, "terminal")

    mate_move = _find_mate_in_one(board, legal_moves)
    if mate_move is not None:
        return _make_record(
            board,
            _format_move(board, mate_move, output_format),
            100000,
            1,
            start,
            legal_uci,
            False,
            "mate_in_one_guard",
        )

    engine_record = _call_local_engine(observation, output_format, time_limit_ms)
    engine_move = _record_to_legal_move(board, engine_record)
    if engine_move is not None and not _allows_opponent_mate_in_one(board, engine_move):
        selected_text = _format_move(board, engine_move, output_format)
        try:
            engine_record.selected_move = selected_text
            engine_record.legal_moves = legal_uci
            engine_record.fallback_used = bool(getattr(engine_record, "fallback_used", False))
            engine_record.backend = "local_engine_with_tactical_guard"
            return engine_record
        except Exception:
            return _make_record(board, selected_text, 0, 0, start, legal_uci, False, "local_engine_with_tactical_guard")

    safe_move = _choose_safe_heuristic_move(board, legal_moves, time_limit_ms)
    if safe_move is None:
        safe_move = legal_moves[0]
    return _make_record(
        board,
        _format_move(board, safe_move, output_format),
        0,
        0,
        start,
        legal_uci,
        True,
        "safe_heuristic_fallback",
    )


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _safe_parse_board(observation: Any) -> Any:
    if chess is None:
        return None
    if parse_observation is not None:
        try:
            board = parse_observation(observation)
            if board is not None:
                return board
        except Exception:
            pass
    try:
        if isinstance(observation, dict):
            fen = observation.get("fen") or observation.get("board") or observation.get("state")
            if isinstance(fen, str):
                return chess.Board(fen)
        if isinstance(observation, str):
            text = observation.strip()
            if text:
                return chess.Board(text)
    except Exception:
        return None
    return None


def _engine_or_minimal_record(observation: Any, output_format: str, time_limit_ms: int, start: float) -> Any:
    if select_move_record is not None:
        try:
            if DEFAULT_ENGINE_CONFIG is not None:
                return select_move_record(observation, output_format, time_limit_ms, DEFAULT_ENGINE_CONFIG)
            return select_move_record(observation, output_format, time_limit_ms)
        except Exception:
            pass
    return _SimpleRecord("", elapsed_ms=(time.perf_counter() - start) * 1000.0)


def _call_local_engine(observation: Any, output_format: str, time_limit_ms: int) -> Any:
    if select_move_record is None:
        return None
    try:
        if DEFAULT_ENGINE_CONFIG is not None:
            return select_move_record(
                observation=observation,
                output_format=output_format,
                time_limit_ms=time_limit_ms,
                config=DEFAULT_ENGINE_CONFIG,
            )
        return select_move_record(observation=observation, output_format=output_format, time_limit_ms=time_limit_ms)
    except Exception:
        return None


def _record_to_legal_move(board: Any, record: Any) -> Any:
    if record is None:
        return None
    text = str(getattr(record, "selected_move", "")).strip()
    if not text:
        return None
    try:
        move_obj = chess.Move.from_uci(text)
        if move_obj in board.legal_moves:
            return move_obj
    except Exception:
        pass
    try:
        move_obj = board.parse_san(text)
        if move_obj in board.legal_moves:
            return move_obj
    except Exception:
        return None
    return None


def _find_mate_in_one(board: Any, legal_moves: list[Any]) -> Any:
    for candidate in legal_moves:
        board.push(candidate)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return candidate
    return None


def _allows_opponent_mate_in_one(board: Any, candidate: Any) -> bool:
    board.push(candidate)
    if board.is_checkmate() or board.is_stalemate() or board.is_game_over(claim_draw=False):
        board.pop()
        return False
    opponent_moves = list(board.legal_moves)
    for reply in opponent_moves:
        board.push(reply)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            board.pop()
            return True
    board.pop()
    return False


def _choose_safe_heuristic_move(board: Any, legal_moves: list[Any], time_limit_ms: int) -> Any:
    deadline = time.perf_counter() + max(0.005, min(0.03, time_limit_ms / 1000.0 * 0.35))
    best_move = None
    best_score = -10**9
    fallback_best = None
    fallback_score = -10**9
    for candidate in legal_moves:
        if time.perf_counter() > deadline and best_move is not None:
            break
        score = _static_move_score(board, candidate)
        if score > fallback_score:
            fallback_score = score
            fallback_best = candidate
        if _allows_opponent_mate_in_one(board, candidate):
            continue
        if score > best_score:
            best_score = score
            best_move = candidate
    return best_move if best_move is not None else fallback_best


def _static_move_score(board: Any, move_obj: Any) -> int:
    score = 0
    moving_piece = board.piece_at(move_obj.from_square)
    captured_piece = board.piece_at(move_obj.to_square)
    if board.is_en_passant(move_obj):
        captured_piece_type = chess.PAWN
    else:
        captured_piece_type = captured_piece.piece_type if captured_piece is not None else None
    attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece is not None else 0
    victim_value = PIECE_VALUES.get(captured_piece_type, 0) if captured_piece_type is not None else 0
    if victim_value:
        score += 10000 + victim_value * 10 - attacker_value
    if move_obj.promotion:
        score += 8000 + PIECE_VALUES.get(move_obj.promotion, 0)
    if board.gives_check(move_obj):
        score += 1200
    if board.is_castling(move_obj):
        score += 700
    to_name = chess.square_name(move_obj.to_square)
    if to_name in CENTER_SQUARES:
        score += 140
    elif to_name in EXTENDED_CENTER:
        score += 55
    if moving_piece is not None and moving_piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        home_rank = 0 if moving_piece.color == chess.WHITE else 7
        if chess.square_rank(move_obj.from_square) == home_rank:
            score += 180
    if moving_piece is not None and moving_piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
        score -= 90
    return score


def _format_move(board: Any, move_obj: Any, output_format: str) -> str:
    fmt = output_format.lower().strip()
    if fmt == "san":
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def _make_record(
    board: Any,
    selected_move: str,
    cp: int,
    depth: int,
    start: float,
    legal_moves: list[str],
    fallback_used: bool,
    backend: str,
) -> Any:
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    wdl = cp_to_wdl(cp, None) if cp_to_wdl is not None else {"win": 0, "draw": 1, "loss": 0}
    if SearchRecord is not None:
        try:
            return SearchRecord(
                fen=board.fen(),
                selected_move=selected_move,
                cp=cp,
                mate_distance=None,
                wdl=wdl,
                depth=depth,
                elapsed_ms=elapsed_ms,
                nodes=0,
                qnodes=0,
                legal_moves=legal_moves,
                fallback_used=fallback_used,
                backend=backend,
            )
        except TypeError:
            pass
    return _SimpleRecord(
        selected_move,
        fen=board.fen(),
        cp=cp,
        depth=depth,
        elapsed_ms=elapsed_ms,
        legal_moves=legal_moves,
        fallback_used=fallback_used,
        backend=backend,
    )


class _SimpleRecord:
    def __init__(self, selected_move: str, **kwargs: Any) -> None:
        self.selected_move = selected_move
        for key, value in kwargs.items():
            setattr(self, key, value)
