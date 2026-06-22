import json

from scripts.run_profile_ab_match import (
    apply_profile_overrides,
    load_openings_file,
    score_to_elo,
    summarize_match,
)
from tools.strategy_profile import StrategyProfile
from tuning.match_runner import MatchConfig, run_paired_match


def test_score_to_elo_is_centered_at_even_score():
    assert score_to_elo(0.5) == 0.0
    assert score_to_elo(0.75) > 0.0
    assert score_to_elo(0.25) < 0.0


def test_summarize_match_reports_reliability_fields():
    summary = run_paired_match(
        StrategyProfile(),
        StrategyProfile(),
        MatchConfig(pair_count=1, time_limit_ms=20, max_plies=8),
    )

    payload = summarize_match(summary)

    assert payload["games"] == 2
    assert "score_ci95_low" in payload
    assert "elo_estimate_a" in payload
    assert payload["player_a_timeouts"] >= 0
    assert payload["by_opening"]


def test_load_openings_file_accepts_feedback_fen_suite(tmp_path):
    path = tmp_path / "feedback_fen_suite.json"
    path.write_text(
        json.dumps(
            {
                "positions": [
                    {
                        "name": "test_position",
                        "fen": "8/8/8/8/8/8/8/K6k w - - 0 1",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    openings = load_openings_file(path)

    assert len(openings) == 1
    assert openings[0].name == "test_position"


def test_apply_profile_overrides_updates_nested_values():
    profile = apply_profile_overrides(
        StrategyProfile(),
        [
            "search.use_side_to_move_quiescence=true",
            "search.use_root_opening_priors=true",
            "eval.use_tactical_vulnerability=true",
            "eval.tactical_vulnerability_weight=2.0",
            "eval.tactical_vulnerability_max_fullmove=20",
            "search.max_depth=2",
        ],
    )

    assert profile.search.use_side_to_move_quiescence is True
    assert profile.search.use_root_opening_priors is True
    assert profile.eval.use_tactical_vulnerability is True
    assert profile.eval.tactical_vulnerability_weight == 2.0
    assert profile.eval.tactical_vulnerability_max_fullmove == 20
    assert profile.search.max_depth == 2
