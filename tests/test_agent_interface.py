import chess

from agents.chess_agent import ChessAgent, act, agent, select_move
from tools.move_validator import validate_move


def test_select_move_from_start_fen_is_legal():
    board = chess.Board()
    move = select_move({"fen": board.fen()})
    assert validate_move(board, move).is_legal


def test_common_entrypoint_aliases_return_moves():
    observation = {"fen": chess.Board().fen()}
    assert agent(observation)
    assert act(observation)
    assert ChessAgent().act(observation)


def test_terminal_position_returns_empty_string():
    board = chess.Board("7k/5KQ1/8/8/8/8/8/8 b - - 0 1")
    assert board.is_checkmate()
    assert select_move({"fen": board.fen()}) == ""
