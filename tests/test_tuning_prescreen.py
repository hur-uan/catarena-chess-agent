import chess

from agents.engine import SearchResult, SearchStats
from tools.strategy_profile import StrategyProfile
from tuning import prescreen
from tuning.prescreen import (
    PrescreenConfig,
    PrescreenPosition,
    default_prescreen_positions,
    resolve_prescreen_positions,
    run_fen_prescreen,
)


def test_prescreen_has_multiple_positions():
    positions = default_prescreen_positions()
    assert len(positions) >= 4


def test_prescreen_runs_and_returns_bounded_scores():
    summary = run_fen_prescreen(StrategyProfile(), StrategyProfile())
    assert summary.positions >= 1
    assert 0.0 <= summary.mean_score_a <= 1.0
    assert 0.0 <= summary.mean_score_b <= 1.0
    assert -1.0 <= summary.score_difference <= 1.0


def test_static_eval_prescreen_produces_non_zero_signal(monkeypatch):
    position = PrescreenPosition(
        name="pawn_shape_bias",
        fen="4k3/2ppp3/8/8/8/2P5/2P1P3/4K3 w - - 0 1",
    )
    profile_a = StrategyProfile()
    profile_b = StrategyProfile()
    profile_a.eval.pawn_structure_weight = 0.2
    profile_b.eval.pawn_structure_weight = 3.0

    monkeypatch.setattr(prescreen, "_oracle_root_reference", lambda *args, **kwargs: ("", 0))
    summary = run_fen_prescreen(
        profile_a,
        profile_b,
        config=PrescreenConfig(
            signal_mode="static_eval",
            use_external_oracle=False,
            positions=[position],
        ),
    )

    assert summary.positions == 1
    assert summary.score_difference != 0.0
    assert summary.mean_score_a > summary.mean_score_b


def test_prescreen_can_resolve_block_specific_position_sets():
    positions = resolve_prescreen_positions("line_quality", "search.depth_time")
    assert len(positions) >= 4
    assert any(position.name == "forcing_check_chain" for position in positions)


def test_search_behavior_prescreen_uses_search_stats_signal(monkeypatch):
    position = PrescreenPosition(
        name="ordering_stats_case",
        fen="4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",
    )
    strong = StrategyProfile()
    weak = StrategyProfile()
    strong.search.tt_move_bonus = 150000
    strong.search.history_bonus_scale = 8
    strong.search.history_bonus_power = 3
    weak.search.tt_move_bonus = 5000
    weak.search.history_bonus_scale = 1
    weak.search.history_bonus_power = 1

    monkeypatch.setattr(prescreen, "_oracle_root_reference", lambda *args, **kwargs: ("", 50))
    monkeypatch.setattr(prescreen, "_line_score_after_move", lambda *args, **kwargs: 50)

    def fake_search_best_move(board, time_limit_ms, config):
        move = next(iter(board.legal_moves))
        if config.strategy_profile.search.tt_move_bonus > 100000:
            return SearchResult(
                move=move,
                score_cp=50,
                mate_distance=None,
                depth=2,
                stats=SearchStats(nodes=40, cutoffs=8, tt_hits=5, max_depth_completed=2),
            )
        return SearchResult(
            move=move,
            score_cp=50,
            mate_distance=None,
            depth=0,
            stats=SearchStats(nodes=40, cutoffs=0, tt_hits=0, max_depth_completed=0),
        )

    monkeypatch.setattr(prescreen, "search_best_move", fake_search_best_move)
    summary = run_fen_prescreen(
        strong,
        weak,
        config=PrescreenConfig(
            signal_mode="search_behavior",
            use_external_oracle=False,
            positions=[position],
        ),
    )

    assert summary.positions == 1
    assert summary.score_difference > 0.0
    assert summary.results[0].depth_a > summary.results[0].depth_b
    assert summary.results[0].cutoffs_a > summary.results[0].cutoffs_b


def test_external_oracle_scores_are_cached_per_prescreen_run(monkeypatch):
    position = PrescreenPosition(
        name="stable_oracle_case",
        fen="4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",
    )
    calls = []

    monkeypatch.setattr(prescreen, "is_black_numba_available", lambda: True)

    def fake_analyze_position(fen, **kwargs):
        calls.append(fen)
        return {"move": "e2e3", "score_cp": 100 + len(calls)}

    def fake_search_best_move(board, time_limit_ms, config):
        return SearchResult(
            move=chess.Move.from_uci("e2e3"),
            score_cp=50,
            mate_distance=None,
            depth=1,
            stats=SearchStats(nodes=10, cutoffs=0, tt_hits=0, max_depth_completed=1),
        )

    monkeypatch.setattr(prescreen, "analyze_position", fake_analyze_position)
    monkeypatch.setattr(prescreen, "search_best_move", fake_search_best_move)

    summary = run_fen_prescreen(
        StrategyProfile(),
        StrategyProfile(),
        config=PrescreenConfig(
            use_external_oracle=True,
            positions=[position],
        ),
    )

    assert summary.score_difference == 0.0
    assert len(calls) == 2
