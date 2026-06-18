from tools.strategy_profile import StrategyProfile
from tuning.match_runner import MatchConfig, run_paired_match


def test_paired_match_runs_with_default_profiles():
    summary = run_paired_match(
        StrategyProfile(),
        StrategyProfile(),
        MatchConfig(pair_count=2, time_limit_ms=20, max_plies=20),
    )
    assert summary.games == 4
    assert len(summary.game_scores_a) == 4
    assert 0.0 <= summary.mean_score_a <= 1.0


def test_paired_match_forces_internal_engine_and_tracks_move_counts():
    profile_a = StrategyProfile()
    profile_b = StrategyProfile()
    profile_b.external_engine.enabled = True
    summary = run_paired_match(
        profile_a,
        profile_b,
        MatchConfig(pair_count=1, time_limit_ms=20, max_plies=10, force_internal_engine=True),
    )
    assert summary.games == 2
    assert summary.player_a_moves >= 0
    assert summary.player_b_moves >= 0
    assert all(game.response_times_ms for game in summary.results)


def test_match_config_timeout_threshold_uses_ratio_or_absolute_slack():
    config = MatchConfig(time_limit_ms=20, timeout_slack_ms=1, timeout_slack_ratio=0.5)
    assert config.timeout_threshold_ms() == 30.0
