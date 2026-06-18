from agents.chess_agent import select_move_details
from tools import black_numba_client
from tools.black_numba_client import BlackNumbaUnavailable, is_black_numba_available
from tools.black_numba_config import resolve_black_numba_config


def test_black_numba_runtime_can_be_discovered():
    assert is_black_numba_available()


def test_select_move_details_uses_internal_engine_by_default():
    details = select_move_details(
        {"fen": "rn1qkbnr/pppb1ppp/8/3pp3/8/5NP1/PPPPPPBP/RNBQK2R w KQkq - 0 4"}
    )
    assert details.selected_move
    assert details.depth >= 0
    assert details.backend == "internal"


def test_black_numba_low_time_profile_can_disable_external_runtime():
    import chess

    resolved = resolve_black_numba_config(
        board=chess.Board(),
        requested_time_limit_ms=20,
    )
    assert not resolved.enabled


def test_black_numba_observation_override_changes_depth_profile():
    import chess

    resolved = resolve_black_numba_config(
        board=chess.Board(),
        requested_time_limit_ms=200,
        observation={"black_numba_config": {"enabled": True, "opening_depth_limit": 3}},
    )
    assert resolved.enabled
    assert resolved.depth_limit == 3


def test_black_numba_strategy_profile_override_changes_depth_profile():
    import chess

    resolved = resolve_black_numba_config(
        board=chess.Board(),
        requested_time_limit_ms=200,
        observation={
            "strategy_profile": {
                "external_engine": {"enabled": True, "opening_depth_limit": 3}
            }
        },
    )
    assert resolved.enabled
    assert resolved.depth_limit == 3


def test_black_numba_client_times_out_unresponsive_worker(monkeypatch):
    class FakeStdin:
        def __init__(self):
            self.writes = []

        def write(self, text):
            self.writes.append(text)

        def flush(self):
            pass

    class FakeStdout:
        def readline(self):
            raise AssertionError("readline should not run when select times out")

    class FakeProcess:
        def __init__(self):
            self.stdin = FakeStdin()
            self.stdout = FakeStdout()
            self.killed = False

        def kill(self):
            self.killed = True

        def wait(self, timeout):
            return 0

    fake_process = FakeProcess()
    monkeypatch.setattr(black_numba_client, "_ensure_process", lambda: fake_process)
    monkeypatch.setattr(black_numba_client.select, "select", lambda *args: ([], [], []))

    try:
        black_numba_client.analyze_position(
            "8/8/8/8/8/8/8/K6k w - - 0 1",
            response_timeout_seconds=0.1,
        )
    except BlackNumbaUnavailable as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("expected black_numba timeout")

    assert fake_process.killed
