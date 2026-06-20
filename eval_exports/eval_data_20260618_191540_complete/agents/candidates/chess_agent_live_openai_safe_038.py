"""Safe CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This version deliberately avoids external/network engine delegation.  It uses a
small tactical prepass plus the repository's internal bounded engine, and it
validates every final move against python-chess legal_moves before returning.
"""

from __future__ import annotations

from typing import Any

import chess

from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
from tools.board_parser import parse_observation
from tools.strategy_profile import resolve_strategy_profile

DEFAULT_ENGINE_CONFIG = EngineConfig()


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
    """Choose a legal chess move for the supplied observation.

    The final result is always checked against python-chess legal moves.  If the
    internal engine ever returns an invalid or unsupported formatted move, this
    function falls back to a deterministic legal move.
    """
    board = _safe_parse_board(observation)
    if board is None:
        return ""

    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    tactical = _select_tactical_prepass(board)
    if tactical is not None:
        return _format_legal_move(board, tactical, output_format)

    try:
        record = select_move_details(
            observation=observation,
            output_format="uci",
            time_limit_ms=time_limit_ms,
        )
        candidate = str(record.selected_move).strip()
    except Exception:
        candidate = ""

    move_obj = _uci_to_legal_move(board, candidate)
    if move_obj is None:
        move_obj = _deterministic_fallback_move(board)
    if move_obj is None:
        return ""
    return _format_legal_move(board, move_obj, output_format)


def select_move_details(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> SearchRecord:
    """Return the selected move and underlying search diagnostics.

    This function intentionally uses only the internal repository engine.  It
    does not call black_numba or any other external service.
    """
    board = _safe_parse_board(observation)
    if board is None:
        return SearchRecord(
            fen="",
            selected_move="",
            cp=0,
            mate_distance=None,
            wdl=cp_to_wdl(0, None),
            depth=0,
            elapsed_ms=0.0,
            nodes=0,
            qnodes=0,
            legal_moves=[],
            fallback_used=True,
            backend="parse_failure",
        )

    legal_moves = [move.uci() for move in board.legal_moves]
    if not legal_moves or board.is_game_over(claim_draw=False):
        return SearchRecord(
            fen=board.fen(),
            selected_move="",
            cp=0,
            mate_distance=None,
            wdl=cp_to_wdl(0, None),
            depth=0,
            elapsed_ms=0.0,
            nodes=0,
            qnodes=0,
            legal_moves=legal_moves,
            fallback_used=False,
            backend="terminal",
        )

    tactical = _select_tactical_prepass(board)
    if tactical is not None:
        return SearchRecord(
            fen=board.fen(),
            selected_move=tactical.uci(),
            cp=99999,
            mate_distance=1,
            wdl=cp_to_wdl(99999, 1),
            depth=1,
            elapsed_ms=0.0,
            nodes=len(legal_moves),
            qnodes=0,
            legal_moves=legal_moves,
            principal_variation=[tactical.uci()],
            fallback_used=False,
            backend="tactical_prepass",
        )

    strategy_profile, strategy_source = resolve_strategy_profile(observation=observation)
    config = EngineConfig(strategy_profile=strategy_profile)
    record = select_move_record(
        observation=observation,
        output_format="uci",
        time_limit_ms=time_limit_ms,
        config=config,
    )
    record.engine_config = {
        "profile_name": strategy_profile.profile_name,
        "strategy_source": strategy_source,
        "external_engine": "disabled_for_match_safety",
    }

    move_obj = _uci_to_legal_move(board, str(record.selected_move).strip())
    if move_obj is None:
        fallback = _deterministic_fallback_move(board)
        record.selected_move = fallback.uci() if fallback is not None else ""
        record.fallback_used = True
        record.backend = "internal_engine_validated_fallback"
    else:
        record.selected_move = move_obj.uci()
        if not getattr(record, "backend", ""):
            record.backend = "internal_engine_validated"
    return record


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _safe_parse_board(observation: Any) -> chess.Board | None:
    try:
        board = parse_observation(observation)
    except Exception:
        return None
    if not isinstance(board, chess.Board):
        return None
    return board


def _select_tactical_prepass(board: chess.Board) -> chess.Move | None:
    """Return an obvious forcing move without doing expensive search.

    This is intentionally tiny and deterministic: only single legal moves and
    mate-in-one are handled.  Anything more complex is left to the internal
    bounded engine.
    """
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    for candidate in _ordered_moves_for_tactics(board, legal_moves):
        board.push(candidate)
        gives_mate = board.is_checkmate()
        board.pop()
        if gives_mate:
            return candidate
    return None


def _ordered_moves_for_tactics(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> list[chess.Move]:
    return sorted(legal_moves, key=lambda move: _tactical_order_score(board, move), reverse=True)


def _tactical_order_score(board: chess.Board, move_to_score: chess.Move) -> int:
    score = 0
    if board.gives_check(move_to_score):
        score += 10_000
    if board.is_capture(move_to_score):
        victim = board.piece_at(move_to_score.to_square)
        if victim is None and board.is_en_passant(move_to_score):
            victim_value = 100
        else:
            victim_value = _piece_value(victim.piece_type) if victim is not None else 0
        attacker = board.piece_at(move_to_score.from_square)
        attacker_value = _piece_value(attacker.piece_type) if attacker is not None else 0
        score += 1_000 + (10 * victim_value) - attacker_value
    if move_to_score.promotion is not None:
        score += 800 + _piece_value(move_to_score.promotion)
    return score


def _piece_value(piece_type: int) -> int:
    if piece_type == chess.PAWN:
        return 100
    if piece_type == chess.KNIGHT:
        return 320
    if piece_type == chess.BISHOP:
        return 330
    if piece_type == chess.ROOK:
        return 500
    if piece_type == chess.QUEEN:
        return 900
    return 0


def _uci_to_legal_move(board: chess.Board, candidate: str) -> chess.Move | None:
    if not candidate:
        return None
    try:
        move_obj = chess.Move.from_uci(candidate)
    except ValueError:
        return None
    if move_obj in board.legal_moves:
        return move_obj
    return None


def _deterministic_fallback_move(board: chess.Board) -> chess.Move | None:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None

    # Prefer immediate mate if validation reached fallback after an engine issue.
    tactical = _select_tactical_prepass(board)
    if tactical is not None:
        return tactical

    # Stable, cheap move ordering: checks/captures/promotions first, then UCI.
    return max(
        legal_moves,
        key=lambda candidate: (
            _tactical_order_score(board, candidate),
            candidate.uci(),
        ),
    )


def _format_legal_move(
    board: chess.Board,
    move_obj: chess.Move,
    output_format: str,
) -> str:
    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    # CATArena expects UCI; treat default/unknown as UCI for safety.
    return move_obj.uci()
