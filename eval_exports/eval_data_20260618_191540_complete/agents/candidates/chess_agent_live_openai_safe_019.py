"""Safe next-round CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This version deliberately avoids external analysis services.  It keeps the
repository's internal bounded engine as the primary move selector, then adds
small deterministic tactical guards and a final python-chess legality fallback.
"""

from __future__ import annotations

from typing import Any

import chess

from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
from tools.board_parser import parse_observation
from tools.strategy_profile import resolve_strategy_profile

DEFAULT_ENGINE_CONFIG = EngineConfig()
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
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
    """Return the selected move and search diagnostics.

    The arena contract expects UCI.  For unusual output formats, defer to the
    internal engine and still enforce a UCI legal fallback if necessary.
    """
    board = _parse_board_safe(observation)
    legal_uci = [move.uci() for move in board.legal_moves]
    if board.is_game_over(claim_draw=False) or not legal_uci:
        return _make_record(board, "", legal_uci, backend="terminal")

    uci_output = output_format.lower().strip() in {"", "default", "uci"}

    if uci_output:
        mate_move = _find_mate_in_one(board)
        if mate_move is not None:
            return _make_record(
                board,
                mate_move.uci(),
                legal_uci,
                cp=48999,
                mate_distance=1,
                depth=1,
                backend="mate_in_one",
            )

    engine_record = _call_internal_engine(observation, output_format, time_limit_ms)
    engine_move = _legal_record_move(engine_record, legal_uci)

    if uci_output and engine_move is not None:
        guarded = _mate_guard_choice(board, chess.Move.from_uci(engine_move))
        if guarded is not None and guarded.uci() != engine_move:
            return _make_record(
                board,
                guarded.uci(),
                legal_uci,
                cp=_static_eval_after_move(board, guarded),
                depth=1,
                backend="mate_guard",
                principal_variation=[engine_move, guarded.uci()],
            )

    if engine_move is not None:
        engine_record.selected_move = engine_move
        engine_record.legal_moves = legal_uci
        return engine_record

    fallback = _deterministic_fallback(board)
    return _make_record(
        board,
        fallback.uci() if fallback is not None else "",
        legal_uci,
        cp=_static_eval_after_move(board, fallback) if fallback is not None else 0,
        depth=0,
        backend="local_fallback",
        fallback_used=True,
    )


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _call_internal_engine(
    observation: Any,
    output_format: str,
    time_limit_ms: int,
) -> SearchRecord:
    try:
        strategy_profile, strategy_source = resolve_strategy_profile(observation=observation)
        config = EngineConfig(strategy_profile=strategy_profile)
    except Exception:
        strategy_profile = None
        strategy_source = "default_after_profile_error"
        config = DEFAULT_ENGINE_CONFIG

    try:
        record = select_move_record(
            observation=observation,
            output_format=output_format,
            time_limit_ms=time_limit_ms,
            config=config,
        )
    except Exception:
        board = _parse_board_safe(observation)
        legal_uci = [move.uci() for move in board.legal_moves]
        fallback = _deterministic_fallback(board)
        return _make_record(
            board,
            fallback.uci() if fallback is not None else "",
            legal_uci,
            backend="engine_exception_fallback",
            fallback_used=True,
        )

    profile_name = getattr(strategy_profile, "profile_name", "default") if strategy_profile is not None else "default"
    record.engine_config = {
        "profile_name": profile_name,
        "strategy_source": strategy_source,
        "external_backend": "disabled_for_match_safety",
    }
    return record


def _parse_board_safe(observation: Any) -> chess.Board:
    try:
        return parse_observation(observation)
    except Exception:
        fen = None
        if isinstance(observation, dict):
            value = observation.get("fen") or observation.get("board")
            if isinstance(value, str):
                fen = value
        elif isinstance(observation, str):
            fen = observation
        if fen:
            try:
                return chess.Board(fen)
            except Exception:
                pass
    return chess.Board()


def _legal_record_move(record: SearchRecord, legal_uci: list[str]) -> str | None:
    move_text = str(getattr(record, "selected_move", "")).strip()
    if move_text in legal_uci:
        return move_text
    return None


def _find_mate_in_one(board: chess.Board) -> chess.Move | None:
    for move in sorted(board.legal_moves, key=lambda candidate: candidate.uci()):
        board.push(move)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return move
    return None


def _allows_opponent_mate_in_one(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    for reply in board.legal_moves:
        board.push(reply)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            board.pop()
            return True
    board.pop()
    return False


def _mate_guard_choice(board: chess.Board, selected: chess.Move) -> chess.Move | None:
    if not _allows_opponent_mate_in_one(board, selected):
        return selected

    safe_moves: list[chess.Move] = []
    for candidate in board.legal_moves:
        if not _allows_opponent_mate_in_one(board, candidate):
            safe_moves.append(candidate)
    if not safe_moves:
        return selected
    return max(
        safe_moves,
        key=lambda candidate: (_static_eval_after_move(board, candidate), _move_tiebreak(candidate)),
    )


def _deterministic_fallback(board: chess.Board) -> chess.Move | None:
    legal = list(board.legal_moves)
    if not legal:
        return None

    mate = _find_mate_in_one(board)
    if mate is not None:
        return mate

    safe_moves = [move for move in legal if not _allows_opponent_mate_in_one(board, move)]
    candidates = safe_moves if safe_moves else legal
    return max(
        candidates,
        key=lambda candidate: (_static_eval_after_move(board, candidate), _move_tiebreak(candidate)),
    )


def _static_eval_after_move(board: chess.Board, move: chess.Move | None) -> int:
    if move is None:
        return 0
    mover = board.turn
    board.push(move)
    if board.is_checkmate():
        board.pop()
        return 48999
    score = _material_score(board, mover)
    if board.is_check():
        score += 25
    score += min(board.legal_moves.count(), 40)
    board.pop()
    return score


def _material_score(board: chess.Board, perspective: chess.Color) -> int:
    score = 0
    for piece in board.piece_map().values():
        value = PIECE_VALUES.get(piece.piece_type, 0)
        if piece.color == perspective:
            score += value
        else:
            score -= value
    return score


def _move_tiebreak(move: chess.Move) -> str:
    return move.uci()


def _make_record(
    board: chess.Board,
    selected_move: str,
    legal_moves: list[str],
    cp: int = 0,
    mate_distance: int | None = None,
    depth: int = 0,
    backend: str = "local",
    fallback_used: bool = False,
    principal_variation: list[str] | None = None,
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
        principal_variation=principal_variation or ([selected_move] if selected_move else []),
        fallback_used=fallback_used,
        backend=backend,
        engine_config={"external_backend": "disabled_for_match_safety"},
    )
