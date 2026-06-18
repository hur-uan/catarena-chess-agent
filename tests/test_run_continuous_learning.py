import importlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path


class FakePlatformRun:
    def __init__(self, round_dir: Path):
        self.battle_log_path = str(round_dir / "battle.log")
        self.ranking_path = str(round_dir / "ranking.csv")
        self.error_report_path = str(round_dir / "error_report.json")
        self.official_report_path = str(round_dir / "feedback_report.json")
        self.context_path = str(round_dir / "feedback_context.json")
        self.contract_path = str(round_dir / "feedback_contract.json")
        self.manifest_path = str(round_dir / "feedback_manifest.json")
        self.passed = True
        self.games = 2
        self.moves_played = 10
        self.errors = []

    def model_dump(self):
        return {
            "battle_log_path": self.battle_log_path,
            "ranking_path": self.ranking_path,
            "error_report_path": self.error_report_path,
            "official_report_path": self.official_report_path,
            "context_path": self.context_path,
            "contract_path": self.contract_path,
            "manifest_path": self.manifest_path,
            "passed": self.passed,
            "games": self.games,
            "moves_played": self.moves_played,
            "errors": self.errors,
        }


class FakeOptimizationReport:
    def __init__(self, round_id: str):
        self.round_id = round_id
        self.validator_passed = True
        self.generated_agent = type(
            "GeneratedAgent",
            (),
            {
                "path": f"agents/candidates/{round_id}.json",
                "promoted": False,
                "backend": "profile",
            },
        )()
        self.tuning_report = type(
            "TuningReport",
            (),
            {"promoted_strategy_profile": False},
        )()
        self.artifact_paths = {"round_record_path": f"reports/{round_id}/round_record.json"}

    def model_dump(self):
        return {
            "round_id": self.round_id,
            "validator_passed": self.validator_passed,
            "artifact_paths": self.artifact_paths,
        }


def _write_feedback_files(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "battle.log").write_text("result win\n", encoding="utf-8")
    (output_dir / "ranking.csv").write_text(
        "agent,rank,games,wins,losses,draws,win_rate\nchess_agent,1,1,1,0,0,1.0\n",
        encoding="utf-8",
    )


def test_run_continuous_learning_uses_self_play_defaults(monkeypatch, tmp_path):
    module = importlib.import_module("scripts.run_continuous_learning")
    captured = {"self_play_calls": [], "platform_calls": [], "optimization_calls": []}

    def fake_self_play_run(
        output_dir: Path,
        pair_count: int,
        time_limit_ms: int,
        max_plies: int,
        timeout_slack_ms: int,
        timeout_slack_ratio: float,
    ):
        _write_feedback_files(output_dir)
        captured["self_play_calls"].append(
            {
                "output_dir": str(output_dir),
                "pair_count": pair_count,
                "time_limit_ms": time_limit_ms,
                "max_plies": max_plies,
                "timeout_slack_ms": timeout_slack_ms,
                "timeout_slack_ratio": timeout_slack_ratio,
            }
        )
        return FakePlatformRun(output_dir)

    def fake_platform_run(output_dir: Path, max_plies: int):
        captured["platform_calls"].append({"output_dir": str(output_dir), "max_plies": max_plies})
        return FakePlatformRun(output_dir)

    def fake_run_optimization_round(**kwargs):
        captured["optimization_calls"].append(kwargs)
        return FakeOptimizationReport(kwargs["round_id"])

    monkeypatch.setattr(module, "run_self_play_learning_round", fake_self_play_run)
    monkeypatch.setattr(module, "run_official_catarena_chess_round", fake_platform_run)
    monkeypatch.setattr(module, "run_optimization_round", fake_run_optimization_round)
    monkeypatch.setattr(
        "sys.argv",
        [
            "scripts/run_continuous_learning.py",
            "--reports-dir",
            str(tmp_path / "reports"),
            "--round-count",
            "2",
            "--backend",
            "rule",
            "--optimizer-match-timeout-slack-ms",
            "7",
            "--optimizer-match-timeout-slack-ratio",
            "2.5",
        ],
    )

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        module.main()
    payload = json.loads(buffer.getvalue())

    assert payload["backend"] == "profile"
    assert payload["requested_backend"] == "rule"
    assert payload["feedback_source"] == "self-play"
    assert payload["memory_path"]
    assert payload["round_count"] == 2
    assert payload["promote_agent"] is False
    assert payload["promote_profile"] is False
    assert len(captured["self_play_calls"]) == 2
    assert captured["platform_calls"] == []
    assert len(captured["optimization_calls"]) == 2
    assert all(call["memory_path"] for call in captured["optimization_calls"])
    assert all(call["strict_catarena"] is False for call in captured["optimization_calls"])
    assert all(call["promote_agent"] is False for call in captured["optimization_calls"])
    assert all(call["promote_profile"] is False for call in captured["optimization_calls"])
    assert all(
        call["optimizer_match_timeout_slack_ms"] == 7
        for call in captured["optimization_calls"]
    )
    assert all(
        call["optimizer_match_timeout_slack_ratio"] == 2.5
        for call in captured["optimization_calls"]
    )


def test_run_continuous_learning_can_use_catarena_feedback(monkeypatch, tmp_path):
    module = importlib.import_module("scripts.run_continuous_learning")
    captured = {"self_play_calls": [], "platform_calls": [], "optimization_calls": []}

    def fake_self_play_run(**kwargs):
        captured["self_play_calls"].append(kwargs)
        raise AssertionError("self-play should not run for CATArena feedback")

    def fake_platform_run(output_dir: Path, max_plies: int):
        _write_feedback_files(output_dir)
        captured["platform_calls"].append({"output_dir": str(output_dir), "max_plies": max_plies})
        return FakePlatformRun(output_dir)

    def fake_run_optimization_round(**kwargs):
        captured["optimization_calls"].append(kwargs)
        return FakeOptimizationReport(kwargs["round_id"])

    monkeypatch.setattr(module, "run_self_play_learning_round", fake_self_play_run)
    monkeypatch.setattr(module, "run_official_catarena_chess_round", fake_platform_run)
    monkeypatch.setattr(module, "run_optimization_round", fake_run_optimization_round)
    monkeypatch.setattr(
        "sys.argv",
        [
            "scripts/run_continuous_learning.py",
            "--reports-dir",
            str(tmp_path / "reports"),
            "--round-count",
            "1",
            "--feedback-source",
            "catarena",
        ],
    )

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        module.main()
    payload = json.loads(buffer.getvalue())

    assert payload["feedback_source"] == "catarena"
    assert captured["self_play_calls"] == []
    assert len(captured["platform_calls"]) == 1
    assert captured["optimization_calls"][0]["strict_catarena"] is True


def test_run_continuous_learning_accepts_custom_memory_path(monkeypatch, tmp_path):
    module = importlib.import_module("scripts.run_continuous_learning")
    captured = {"optimization_calls": []}
    memory_path = tmp_path / "isolated_memory.jsonl"

    def fake_self_play_run(
        output_dir: Path,
        pair_count: int,
        time_limit_ms: int,
        max_plies: int,
        timeout_slack_ms: int,
        timeout_slack_ratio: float,
    ):
        _write_feedback_files(output_dir)
        return FakePlatformRun(output_dir)

    def fake_run_optimization_round(**kwargs):
        captured["optimization_calls"].append(kwargs)
        return FakeOptimizationReport(kwargs["round_id"])

    monkeypatch.setattr(module, "run_self_play_learning_round", fake_self_play_run)
    monkeypatch.setattr(module, "run_optimization_round", fake_run_optimization_round)
    monkeypatch.setattr(
        "sys.argv",
        [
            "scripts/run_continuous_learning.py",
            "--reports-dir",
            str(tmp_path / "reports"),
            "--round-count",
            "1",
            "--memory",
            str(memory_path),
        ],
    )

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        module.main()
    payload = json.loads(buffer.getvalue())

    assert payload["memory_path"] == str(memory_path)
    assert captured["optimization_calls"][0]["memory_path"] == memory_path


def test_run_continuous_learning_continues_after_failed_round(monkeypatch, tmp_path):
    module = importlib.import_module("scripts.run_continuous_learning")
    captured = {"optimization_calls": []}

    def fake_self_play_run(
        output_dir: Path,
        pair_count: int,
        time_limit_ms: int,
        max_plies: int,
        timeout_slack_ms: int,
        timeout_slack_ratio: float,
    ):
        _write_feedback_files(output_dir)
        return FakePlatformRun(output_dir)

    def fake_run_optimization_round(**kwargs):
        captured["optimization_calls"].append(kwargs["round_id"])
        if kwargs["round_id"].endswith("_001"):
            raise TimeoutError("simulated profile timeout")
        return FakeOptimizationReport(kwargs["round_id"])

    monkeypatch.setattr(module, "run_self_play_learning_round", fake_self_play_run)
    monkeypatch.setattr(module, "run_optimization_round", fake_run_optimization_round)
    monkeypatch.setattr(
        "sys.argv",
        [
            "scripts/run_continuous_learning.py",
            "--reports-dir",
            str(tmp_path / "reports"),
            "--round-count",
            "2",
            "--round-prefix",
            "resume_after_failure",
            "--backend",
            "openai",
        ],
    )

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        module.main()
    payload = json.loads(buffer.getvalue())

    assert payload["backend"] == "profile"
    assert payload["requested_backend"] == "openai"
    assert payload["round_count"] == 2
    assert captured["optimization_calls"] == [
        "resume_after_failure_001",
        "resume_after_failure_002",
    ]
    assert payload["rounds"][0]["optimization_failed"] is True
    assert "TimeoutError: simulated profile timeout" == payload["rounds"][0]["optimization_error"]
    assert payload["rounds"][1]["optimization_report"]["round_id"] == "resume_after_failure_002"
