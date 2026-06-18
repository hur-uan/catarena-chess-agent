import chess

from agents.chess_agent import select_move
from tools.move_validator import validate_move


def test_zero_time_limit_still_returns_legal_move():
    board = chess.Board()
    move = select_move({"fen": board.fen()}, time_limit_ms=0)
    assert validate_move(board, move).is_legal

