import chess

from agents.engine import (
    EngineConfig,
    evaluate_board,
    root_move_prior_score,
    search_best_move,
)
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


def test_tactical_vulnerability_penalizes_attacked_queen():
    board = chess.Board("4k3/8/8/2p5/3Q4/8/8/4K3 w - - 0 1")
    late_board = chess.Board("4k3/8/8/2p5/3Q4/8/8/4K3 w - - 0 35")
    base_profile, _ = resolve_strategy_profile(
        observation={"strategy_profile": {"eval": {"use_tactical_vulnerability": False}}}
    )
    tactical_profile, _ = resolve_strategy_profile(
        observation={
            "strategy_profile": {
                "eval": {
                    "use_tactical_vulnerability": True,
                    "tactical_vulnerability_weight": 1.0,
                }
            }
        }
    )
    weighted_profile, _ = resolve_strategy_profile(
        observation={
            "strategy_profile": {
                "eval": {
                    "use_tactical_vulnerability": True,
                    "tactical_vulnerability_weight": 2.0,
                }
            }
        }
    )
    limited_profile, _ = resolve_strategy_profile(
        observation={
            "strategy_profile": {
                "eval": {
                    "use_tactical_vulnerability": True,
                    "tactical_vulnerability_max_fullmove": 20,
                }
            }
        }
    )

    base = evaluate_board(board, chess.WHITE, base_profile)
    tactical = evaluate_board(board, chess.WHITE, tactical_profile)
    weighted = evaluate_board(board, chess.WHITE, weighted_profile)
    late_base = evaluate_board(late_board, chess.WHITE, base_profile)
    late_limited = evaluate_board(late_board, chess.WHITE, limited_profile)

    assert tactical < base
    assert weighted < tactical
    assert late_limited == late_base


def test_side_to_move_quiescence_prefers_winning_capture():
    board = chess.Board("4k3/8/8/7q/8/8/8/4K2Q w - - 0 1")
    profile, _ = resolve_strategy_profile(
        observation={
            "strategy_profile": {
                "search": {
                    "default_depth": 1,
                    "max_depth": 1,
                    "quiescence_depth": 0,
                    "use_side_to_move_quiescence": True,
                }
            }
        }
    )

    result = search_best_move(
        board,
        time_limit_ms=100,
        config=EngineConfig(strategy_profile=profile),
    )

    assert result.move == chess.Move.from_uci("h1h5")


def test_root_opening_priors_reward_development_over_rook_lift():
    board = chess.Board()
    profile, _ = resolve_strategy_profile(
        observation={"strategy_profile": {"search": {"use_root_opening_priors": True}}}
    )

    knight_score = root_move_prior_score(
        board,
        chess.Move.from_uci("g1f3"),
        profile,
    )
    rook_score = root_move_prior_score(
        board,
        chess.Move.from_uci("a1a2"),
        profile,
    )
    edge_pawn_score = root_move_prior_score(
        board,
        chess.Move.from_uci("a2a3"),
        profile,
    )

    assert knight_score > 0
    assert rook_score < 0
    assert edge_pawn_score < 0
