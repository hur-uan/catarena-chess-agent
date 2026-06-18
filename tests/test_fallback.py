import chess

from agents.chess_agent import select_move
from tools.board_parser import parse_observation
from tools.move_validator import validate_move


def test_fallback_uses_board_legal_moves_when_hint_is_invalid():
    board = chess.Board()
    move = select_move({"fen": board.fen(), "legal_moves": ["e7e5"]})
    assert validate_move(board, move).is_legal
    assert move != "e7e5"


def test_unknown_observation_falls_back_to_start_position():
    board = parse_observation({"unexpected": "shape"})
    assert board.board_fen() == chess.Board().board_fen()

