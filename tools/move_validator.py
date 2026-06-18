"""Move validation helpers built on python-chess."""

from __future__ import annotations

from typing import Any, Optional

import chess
from pydantic import BaseModel


class ValidationResult(BaseModel):
    is_legal: bool
    normalized_move: Optional[str] = None
    reason: str = ""


def coerce_move(board: chess.Board, move_value: Any) -> Optional[chess.Move]:
    if isinstance(move_value, chess.Move):
        return move_value
    if move_value is None:
        return None

    text = str(move_value).strip()
    if not text:
        return None

    try:
        move = chess.Move.from_uci(text)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass

    try:
        return board.parse_san(text)
    except ValueError:
        return None


def validate_move(board: chess.Board, move_value: Any) -> ValidationResult:
    move = coerce_move(board, move_value)
    if move is None:
        return ValidationResult(is_legal=False, reason="move could not be parsed")
    if move not in board.legal_moves:
        return ValidationResult(
            is_legal=False,
            normalized_move=move.uci(),
            reason="move is not legal in current position",
        )
    return ValidationResult(is_legal=True, normalized_move=move.uci(), reason="legal")


def first_legal_move(board: chess.Board) -> Optional[chess.Move]:
    return next(iter(board.legal_moves), None)

