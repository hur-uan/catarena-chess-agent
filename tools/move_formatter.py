"""Format internal chess.Move objects for CATArena outputs."""

from __future__ import annotations

from typing import Any

import chess

from tools.move_validator import coerce_move


def format_move(board: chess.Board, move_value: Any, output_format: str = "uci") -> str:
    move = coerce_move(board, move_value)
    if move is None:
        raise ValueError("Cannot format an unparsable move.")

    normalized_format = output_format.lower().strip()
    if normalized_format in {"uci", "default", ""}:
        return move.uci()
    if normalized_format == "san":
        return board.san(move)
    if normalized_format == "lan":
        return board.lan(move)
    raise ValueError("Unsupported move output format: %s" % output_format)

