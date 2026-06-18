from tools.log_parser import parse_logs
from tools.ranking_analyzer import analyze_ranking
from tools.self_play_platform import run_self_play_learning_round


def test_self_play_learning_round_writes_optimizer_feedback(tmp_path):
    run = run_self_play_learning_round(
        output_dir=tmp_path,
        pair_count=1,
        time_limit_ms=10,
        max_plies=4,
    )

    assert run.passed is True
    assert run.feedback_source == "self_play"
    assert run.games == 2

    log_report = parse_logs(run.battle_log_path)
    ranking_summary = analyze_ranking(run.ranking_path)

    assert log_report.total_games == 2
    assert log_report.total_actions > 0
    assert log_report.illegal_moves == 0
    assert log_report.timeouts == 0
    assert log_report.crashes == 0
    assert log_report.runtime_errors == []
    assert log_report.average_response_ms is not None
    assert ranking_summary.agent_name == "chess_agent"
    assert ranking_summary.games == 2
    assert ranking_summary.win_rate is not None
