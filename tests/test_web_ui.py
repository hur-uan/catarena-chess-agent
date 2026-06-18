import chess

import web_ui.app as web_app
from tools.move_validator import validate_move
from web_ui.app import GAMES, app


def test_web_ui_state_and_human_move():
    GAMES.clear()
    client = app.test_client()
    new_response = client.post("/api/new", json={"human_color": "white"})
    assert new_response.status_code == 200
    state = new_response.get_json()
    assert state["turn"] == "white"

    move = state["legal_by_from"]["e2"][0]
    move_response = client.post("/api/move", json={"move": move})
    assert move_response.status_code == 200
    moved_state = move_response.get_json()
    assert len(moved_state["history"]) == 2
    assert moved_state["turn"] == "white"


def test_web_ui_agent_step_returns_legal_move():
    GAMES.clear()
    client = app.test_client()
    state = client.post("/api/new", json={"human_color": "white"}).get_json()
    board = chess.Board(state["fen"])

    response = client.post("/api/agent-move", json={})
    assert response.status_code == 200
    moved = response.get_json()
    assert validate_move(board, moved["history"][-1]["uci"]).is_legal
    session = next(iter(GAMES.values()))
    assert session.search_records
    assert session.search_records[-1]["selected_move"] == moved["history"][-1]["uci"]


def test_web_ui_auto_learn_rule_backend_after_max_plies(monkeypatch):
    GAMES.clear()
    client = app.test_client()
    client.post(
        "/api/new",
        json={"mode": "agent_vs_agent", "max_plies": 20},
    )
    session = next(iter(GAMES.values()))
    session.history = [{"uci": "e2e4"} for _ in range(session.max_plies)]

    captured: dict[str, object] = {}

    def fake_run_background_learning(
        game,
        backend: str,
        max_repair_attempts: int,
        promote_agent: bool,
        promote_profile: bool,
    ) -> None:
        captured.update(
            {
                "backend": backend,
                "max_repair_attempts": max_repair_attempts,
                "promote_agent": promote_agent,
                "promote_profile": promote_profile,
            }
        )
        game.learned = True
        game.learning_error = ""
        game.learning_result = {
            "validator_passed": True,
            "promoted_agent": False,
            "promoted_profile": False,
            "candidate_path": "agents/candidates/fake.json",
            "repair_attempts": 0,
            "artifact_paths": {"round_record_path": "reports/web_auto/fake/round_record.json"},
        }
        web_app._set_learning(game, "validated", "Candidate validated but not promoted")

    class ImmediateThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self) -> None:
            self.target(*self.args)

    monkeypatch.setattr(web_app, "_run_background_learning", fake_run_background_learning)
    monkeypatch.setattr(web_app.threading, "Thread", ImmediateThread)

    learn_response = client.post("/api/learn", json={"backend": "rule", "max_repair_attempts": 0})
    assert learn_response.status_code == 200
    payload = learn_response.get_json()
    assert payload["status"] == "started"

    status = client.get("/api/learn-status").get_json()["learning"]
    assert status["status"] == "validated"
    assert status["result"]["validator_passed"]
    assert status["result"]["promoted_agent"] is False
    assert status["result"]["promoted_profile"] is False
    assert status["result"]["artifact_paths"]["round_record_path"].endswith("round_record.json")
    assert captured["backend"] == "rule"
    assert captured["max_repair_attempts"] == 0
    assert captured["promote_agent"] is False
    assert captured["promote_profile"] is False
