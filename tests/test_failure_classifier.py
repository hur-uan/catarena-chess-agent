from tools.failure_classifier import classify_failure
from tools.log_parser import GameLogReport
from tools.ranking_analyzer import RankingSummary


def test_low_rate_timeouts_do_not_dominate_round():
    report = classify_failure(
        GameLogReport(total_actions=300, timeouts=1),
        RankingSummary(rank=1, win_rate=0.5),
    )

    assert report.main_failure_type == "no_clear_failure"
    assert "low-rate timeouts" in report.evidence[0]


def test_timeout_rate_above_threshold_is_stability_failure():
    report = classify_failure(
        GameLogReport(total_actions=300, timeouts=3),
        RankingSummary(rank=1, win_rate=0.5),
    )

    assert report.main_failure_type == "timeout"
    assert report.priority == "high"
