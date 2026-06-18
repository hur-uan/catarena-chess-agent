import chess

from agents.chess_agent import select_move
from tools.board_parser import parse_observation
from tools.move_formatter import format_move
from tools.move_validator import validate_move


def test_parse_observation_from_move_history():
    board = parse_observation({"moves": ["e2e4", "e7e5", "g1f3"]})
    assert board.turn == chess.BLACK
    assert board.fullmove_number == 2


def test_legal_moves_hint_is_still_validated():
    board = chess.Board()
    move = select_move({"fen": board.fen(), "legal_moves": ["not-a-move", "e2e4"]})
    assert move == "e2e4"


def test_promotion_formatting_uci_and_san():
    board = chess.Board("8/P6k/8/8/8/8/7K/8 w - - 0 1")
    move = chess.Move.from_uci("a7a8q")
    assert validate_move(board, move).is_legal
    assert format_move(board, move, "uci") == "a7a8q"
    assert "a8=Q" in format_move(board, move, "san")


def test_castling_move_can_be_formatted():
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    move = chess.Move.from_uci("e1g1")
    assert validate_move(board, move).is_legal
    assert format_move(board, move, "san") == "O-O"

