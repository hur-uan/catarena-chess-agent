"""Safe next-round CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

This version keeps the proven in-repository search backend, but wraps it with:
- strict python-chess legality validation,
- mate-in-one short-circuiting,
- bounded deterministic fallback move scoring,
- exception guards around parser/search integration.

It intentionally does not call external clients or network APIs during move
selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import chess

from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
from tools.board_parser import extract_legal_moves, parse_observation
from tools.strategy_profile import resolve_strategy_profile

DEFAULT_ENGINE_CONFIG = EngineConfig()


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


@dataclass(slots=True)
class _FallbackChoice:
    move: chess.Move
    score: int


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
    record = select_move_details(
        observation=observation,
        output_format=output_format,
        time_limit_ms=time_limit_ms,
    )
    return record.selected_move


def select_move_details(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> SearchRecord:
    """Return the selected move and lightweight search diagnostics."""
    board = _safe_parse_board(observation)
    legal_moves = list(board.legal_moves)
    legal_uci = [move.uci() for move in legal_moves]

    if not legal_moves or board.is_game_over(claim_draw=False):
        return _make_record(board, "", legal_uci, fallback_used=True, backend="terminal")

    # If the arena supplies a restricted legal-move hint list, respect the
    # intersection.  python-chess legality remains authoritative.
    hinted_legal = _hinted_legal_moves(observation, legal_uci)

    # Tactical zero-risk improvement: never miss mate in one.
    mate_move = _find_mate_in_one(board, hinted_legal)
    if mate_move is not None:
        return _make_record(
            board,
            mate_move.uci(),
            legal_uci,
            cp=48999,
            mate_distance=1,
            fallback_used=False,
            backend="mate_in_one_guard",
        )

    # Preserve the proven in-repository engine path, but never trust it blindly.
    try:
        strategy_profile, strategy_source = resolve_strategy_profile(observation=observation)
        config = EngineConfig(strategy_profile=strategy_profile)
        record = select_move_record(
            observation=observation,
            output_format=output_format,
            time_limit_ms=time_limit_ms,
            config=config,
        )
        selected = str(record.selected_move).strip()
        selected_move = _uci_to_legal_move(selected, legal_moves)
        if selected_move is not None and _move_allowed_by_hints(selected_move, hinted_legal):
            record.selected_move = selected_move.uci()
            record.legal_moves = legal_uci
            record.fallback_used = False
            record.backend = getattr(record, "backend", None) or "internal_engine_guarded"
            record.engine_config = {
                "profile_name": strategy_profile.profile_name,
                "strategy_source": strategy_source,
                "safety_wrapper": "legal_validation_mate_guard",
            }
            return record
    except Exception:
        # Match safety beats diagnostics: if parser/profile/search internals ever
        # fail, return a deterministic legal move instead of crashing.
        pass

    fallback = _choose_fallback_move(board, hinted_legal)
    return _make_record(
        board,
        fallback.uci() if fallback is not None else "",
        legal_uci,
        fallback_used=True,
        backend="deterministic_safe_fallback",
    )


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _safe_parse_board(observation: Any) -> chess.Board:
    try:
        board = parse_observation(observation)
        if isinstance(board, chess.Board):
            return board
    except Exception:
        pass

    if isinstance(observation, dict):
        fen = observation.get("fen") or observation.get("board")
        if isinstance(fen, str):
            try:
                return chess.Board(fen)
            except ValueError:
                pass
    elif isinstance(observation, str):
        try:
            return chess.Board(observation)
        except ValueError:
            pass

    return chess.Board()


def _hinted_legal_moves(observation: Any, legal_uci: list[str]) -> set[str]:
    legal_set = set(legal_uci)
    try:
        hinted = {str(item).strip() for item in extract_legal_moves(observation)}
    except Exception:
        hinted = set()
    hinted.discard("")
    intersection = hinted.intersection(legal_set)
    return intersection if intersection else legal_set


def _move_allowed_by_hints(move: chess.Move, hinted_legal: set[str]) -> bool:
    return move.uci() in hinted_legal


def _uci_to_legal_move(move_text: str, legal_moves: Iterable[chess.Move]) -> chess.Move | None:
    if not move_text:
        return None
    try:
        move = chess.Move.from_uci(move_text)
    except ValueError:
        return None
    for legal in legal_moves:
        if move == legal:
            return legal
    return None


def _find_mate_in_one(board: chess.Board, hinted_legal: set[str]) -> chess.Move | None:
    for move in _ordered_legal_moves(board):
        if move.uci() not in hinted_legal:
            continue
        board.push(move)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return move
    return None


def _choose_fallback_move(board: chess.Board, hinted_legal: set[str]) -> chess.Move | None:
    best: _FallbackChoice | None = None
    for move in _ordered_legal_moves(board):
        if move.uci() not in hinted_legal:
            continue
        score = _fallback_move_score(board, move)
        if best is None or score > best.score or (score == best.score and move.uci() < best.move.uci()):
            best = _FallbackChoice(move=move, score=score)
    return best.move if best is not None else None


def _ordered_legal_moves(board: chess.Board) -> list[chess.Move]:
    return sorted(board.legal_moves, key=lambda move: move.uci())


def _fallback_move_score(board: chess.Board, move: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_at(move.from_square)
    captured_piece = board.piece_at(move.to_square)

    if board.is_capture(move):
        if captured_piece is None and board.is_en_passant(move):
            captured_value = PIECE_VALUES[chess.PAWN]
        else:
            captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0
        attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0
        score += 1000 + (10 * captured_value) - attacker_value

    if move.promotion:
        score += 8000 + PIECE_VALUES.get(move.promotion, 0)

    if board.gives_check(move):
        score += 450

    if board.is_castling(move):
        score += 350

    if move.to_square in CENTER_SQUARES:
        score += 90
    elif move.to_square in EXTENDED_CENTER:
        score += 35

    if moving_piece is not None:
        if moving_piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
            score += _minor_development_bonus(board, move, moving_piece)
        elif moving_piece.piece_type == chess.PAWN:
            score += _pawn_advance_bonus(board, move, moving_piece)
        elif moving_piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 45
        elif moving_piece.piece_type == chess.ROOK and board.fullmove_number <= 8:
            score -= 20

    # Avoid fallback moves that immediately allow the moved piece to be won by a
    # lower-value enemy piece when no compensation was gained.  This is shallow
    # and bounded but prevents many emergency blunders.
    board.push(move)
    if moving_piece is not None and board.is_attacked_by(board.turn, move.to_square):
        moved_value = PIECE_VALUES.get(moving_piece.piece_type, 0)
        if captured_piece is None and move.promotion is None:
            score -= moved_value // 2
    if board.is_checkmate():
        score += 50000
    board.pop()

    return score


def _minor_development_bonus(board: chess.Board, move: chess.Move, piece: chess.Piece) -> int:
    if piece.color == chess.WHITE:
        back_rank = chess.square_rank(move.from_square) == 0
        forward_rank = chess.square_rank(move.to_square)
    else:
        back_rank = chess.square_rank(move.from_square) == 7
        forward_rank = 7 - chess.square_rank(move.to_square)
    bonus = 0
    if back_rank:
        bonus += 120
    bonus += max(0, forward_rank) * 8
    return bonus


def _pawn_advance_bonus(board: chess.Board, move: chess.Move, piece: chess.Piece) -> int:
    rank = chess.square_rank(move.to_square)
    progress = rank if piece.color == chess.WHITE else 7 - rank
    bonus = progress * 6
    if move.to_square in CENTER_SQUARES:
        bonus += 35
    if board.fullmove_number <= 10 and move.from_square in {chess.D2, chess.E2, chess.D7, chess.E7}:
        bonus += 30
    return bonus


def _make_record(
    board: chess.Board,
    selected_move: str,
    legal_moves: list[str],
    cp: int = 0,
    mate_distance: int | None = None,
    fallback_used: bool = False,
    backend: str = "safe_wrapper",
) -> SearchRecord:
    return SearchRecord(
        fen=board.fen(),
        selected_move=selected_move,
        cp=cp,
        mate_distance=mate_distance,
        wdl=cp_to_wdl(cp, mate_distance),
        depth=0,
        elapsed_ms=0.0,
        nodes=0,
        qnodes=0,
        legal_moves=legal_moves,
        fallback_used=fallback_used,
        backend=backend,
    )
