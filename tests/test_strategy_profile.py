import chess

from agents.engine import EngineConfig, evaluate_board, search_best_move
from tools.strategy_profile import resolve_strategy_profile


def test_strategy_profile_observation_override_changes_search_depth():
    profile, source = resolve_strategy_profile(
        observation={"strategy_profile": {"search": {"max_depth": 2}}}
    )
    assert source == "observation_override"
    assert profile.search.max_depth == 2


def test_strategy_profile_override_flows_into_search():
    board = chess.Board("6k1/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    config = EngineConfig(strategy_profile=resolve_strategy_profile(
        observation={"strategy_profile": {"search": {"max_depth": 2}}}
    )[0])
    result = search_best_move(board, time_limit_ms=100, config=config)
    assert result.move is not None


def test_evaluate_board_uses_strategy_profile_piece_values():
    board = chess.Board("7k/8/8/8/8/8/7Q/7K w - - 0 1")
    base = evaluate_board(board, chess.WHITE)
    profile, _ = resolve_strategy_profile(
        observation={"strategy_profile": {"piece_values": {"queen": 1200}}}
    )
    boosted = evaluate_board(board, chess.WHITE, profile)
    assert boosted > base
