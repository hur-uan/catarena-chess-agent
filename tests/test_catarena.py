from tools.catarena import check_catarena
from tools.catarena_platform import (
    collect_catarena_platform_context,
    run_official_catarena_chess_round,
)


def test_catarena_status_reports_missing_checkout(tmp_path):
    status = check_catarena(tmp_path / "missing")
    assert not status.exists
    assert not status.has_chessgame
    assert "missing" in status.message.lower()


def test_catarena_platform_context_uses_official_chess_files():
    status = check_catarena()
    if not status.has_chessgame:
        return

    context = collect_catarena_platform_context()
    paths = {item.path for item in context.source_files}
    assert "chessgame/chess/server.py" in paths
    assert "chessgame/chess_Arena/arena.py" in paths
    assert "chessgame/chess/AI_example/ai_http_server.py" in paths
    assert not context.missing_required_files


def test_official_catarena_chess_round_writes_platform_reports(tmp_path):
    status = check_catarena()
    if not status.has_chessgame:
        return

    result = run_official_catarena_chess_round(output_dir=tmp_path, max_plies=4)
    assert result.games == 2
    assert result.moves_played > 0
    assert result.passed
    assert (tmp_path / "catarena_manifest.json").exists()
    assert (tmp_path / "official_catarena_report.json").exists()
