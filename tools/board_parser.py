"""Parse CATArena-like chess observations into python-chess boards."""

from __future__ import annotations

import json
from typing import Any, Iterable, List, Optional

import chess
from pydantic import BaseModel, Field

FEN_KEYS = (
    "fen",
    "board_fen",
    "state",
    "board_state",
    "position",
)
MOVE_HISTORY_KEYS = (
    "moves",
    "move_history",
    "history",
    "played_moves",
    "move_list",
)
LEGAL_MOVE_KEYS = (
    "legal_moves",
    "valid_moves",
    "available_moves",
    "possible_moves",
    "actions",
)
TURN_KEYS = (
    "turn",
    "to_move",
    "side_to_move",
    "current_player",
    "player",
    "color",
)


class ParsedObservation(BaseModel):
    board_fen: str
    legal_moves_hint: List[str] = Field(default_factory=list)
    source: str = "unknown"
    raw_type: str = "unknown"

    def board(self) -> chess.Board:
        return chess.Board(self.board_fen)


def parse_observation(obs: Any) -> chess.Board:
    """Return a chess.Board from common CATArena/dict/string observation shapes."""
    return parse_observation_details(obs).board()


def parse_observation_details(obs: Any) -> ParsedObservation:
    raw_type = type(obs).__name__
    if isinstance(obs, chess.Board):
        return ParsedObservation(
            board_fen=obs.fen(),
            legal_moves_hint=[move.uci() for move in obs.legal_moves],
            source="board",
            raw_type=raw_type,
        )

    if isinstance(obs, str):
        board = _board_from_string(obs)
        return ParsedObservation(board_fen=board.fen(), source="string", raw_type=raw_type)

    if isinstance(obs, dict):
        board, source = _board_from_dict(obs)
        return ParsedObservation(
            board_fen=board.fen(),
            legal_moves_hint=extract_legal_moves(obs),
            source=source,
            raw_type=raw_type,
        )

    if isinstance(obs, (list, tuple)):
        board = _board_from_moves(obs)
        return ParsedObservation(board_fen=board.fen(), source="move-list", raw_type=raw_type)

    return ParsedObservation(board_fen=chess.Board().fen(), source="fallback", raw_type=raw_type)


def extract_legal_moves(obs: Any) -> List[str]:
    if not isinstance(obs, dict):
        return []
    for key in LEGAL_MOVE_KEYS:
        value = _deep_get(obs, key)
        moves = _coerce_move_strings(value)
        if moves:
            return moves
    return []


def _board_from_dict(obs: dict) -> tuple[chess.Board, str]:
    for key in FEN_KEYS:
        value = _deep_get(obs, key)
        if isinstance(value, str):
            board = _try_board_from_fen(value)
            if board is not None:
                return board, "fen:%s" % key

    board_value = _deep_get(obs, "board")
    if isinstance(board_value, str):
        board = _try_board_from_fen(board_value)
        if board is not None:
            return board, "board"
    if isinstance(board_value, dict):
        board, source = _board_from_dict(board_value)
        return board, "board.%s" % source

    pgn_value = _deep_get(obs, "pgn")
    if isinstance(pgn_value, str) and pgn_value.strip():
        return _board_from_string(pgn_value), "pgn"

    for key in MOVE_HISTORY_KEYS:
        value = _deep_get(obs, key)
        moves = _coerce_move_strings(value)
        if moves:
            return _board_from_moves(moves), "moves:%s" % key

    board = chess.Board()
    turn = _extract_turn(obs)
    if turn is not None:
        board.turn = turn
        return board, "turn-only"
    return board, "default-start"


def _board_from_string(value: str) -> chess.Board:
    value = value.strip()
    if not value:
        return chess.Board()

    board = _try_board_from_fen(value)
    if board is not None:
        return board

    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        decoded = None
    if decoded is not None:
        return parse_observation(decoded)

    tokens = [token.strip() for token in value.replace("\n", " ").split(" ") if token.strip()]
    moves = [
        token
        for token in tokens
        if not token.endswith(".") and token not in {"1-0", "0-1", "*"}
    ]
    return _board_from_moves(moves)


def _board_from_moves(moves: Iterable[Any]) -> chess.Board:
    board = chess.Board()
    for raw_move in moves:
        move_text = str(raw_move).strip()
        if not move_text:
            continue
        move_text = move_text.split(".", 1)[-1] if "." in move_text else move_text
        try:
            if _looks_like_uci(move_text):
                move = chess.Move.from_uci(move_text)
                if move in board.legal_moves:
                    board.push(move)
                    continue
            move = board.parse_san(move_text)
            board.push(move)
        except (ValueError, AssertionError):
            break
    return board


def _try_board_from_fen(value: str) -> Optional[chess.Board]:
    try:
        return chess.Board(value)
    except ValueError:
        return None


def _looks_like_uci(value: str) -> bool:
    if len(value) not in {4, 5}:
        return False
    files = set("abcdefgh")
    ranks = set("12345678")
    return value[0] in files and value[2] in files and value[1] in ranks and value[3] in ranks


def _coerce_move_strings(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if "," in text:
            return [item.strip() for item in text.split(",") if item.strip()]
        return [item.strip() for item in text.split() if item.strip()]
    if isinstance(value, dict):
        return _coerce_move_strings(value.get("moves") or value.get("legal_moves"))
    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _deep_get(data: dict, key: str) -> Any:
    if key in data:
        return data[key]
    for value in data.values():
        if isinstance(value, dict):
            found = _deep_get(value, key)
            if found is not None:
                return found
    return None


def _extract_turn(obs: dict) -> Optional[bool]:
    for key in TURN_KEYS:
        value = _deep_get(obs, key)
        if value is None:
            continue
        text = str(value).strip().lower()
        if text in {"white", "w", "0", "true"}:
            return chess.WHITE
        if text in {"black", "b", "1", "false"}:
            return chess.BLACK
    return None


