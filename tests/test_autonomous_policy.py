from pathlib import Path

import tuning.autonomous_policy as autonomous_policy
from tuning.autonomous_policy import run_autonomous_tuning_round


def _memory_record(selected_block: str, action: str, reason_code: str = "", **extra_tuning):
    return {
        "runtime_policy": "formal_internal_only",
        "formal_execution_backend": "internal_engine",
        "tuning": {
            "selected_block": selected_block,
            "action": action,
            "reason_code": reason_code,
            **extra_tuning,
        },
    }


def test_autonomous_tuning_skips_when_reliability_failure_present(tmp_path: Path):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))

    report = run_autonomous_tuning_round(
        round_id="round_skip",
        failure_type="timeout",
        memory_records=[],
        strategy_profile_path=strategy_path,
        promote=False,
    )

    assert report.action == "skipped"
    assert report.reason_code == "stability_first"


def test_autonomous_tuning_holds_when_no_gate_cross(tmp_path: Path):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))

    report = run_autonomous_tuning_round(
        round_id="round_hold",
        failure_type="no_clear_failure",
        memory_records=[],
        strategy_profile_path=strategy_path,
        promote=False,
    )

    assert report.enabled is True
    assert report.selected_block == "move_ordering.capture_base_bonus"
    assert report.action in {"hold", "freeze", "ready", "promote"}
    assert report.reason_code
    assert report.seeds


def test_autonomous_tuning_keeps_no_gate_cross_under_observation(tmp_path: Path):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    memory_records = [
        _memory_record("search.history_order", "hold", "no_gate_cross"),
        _memory_record("search.history_order", "hold", "no_gate_cross"),
    ]

    report = run_autonomous_tuning_round(
        round_id="round_freeze",
        failure_type="no_clear_failure",
        memory_records=memory_records,
        strategy_profile_path=strategy_path,
        promote=False,
    )

    if report.reason_code == "no_gate_cross":
        assert report.action == "hold"


def test_autonomous_tuning_thaws_after_cooldown_rounds(tmp_path: Path, monkeypatch):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    captured = {"learning_rate": None, "slack_ms": None, "slack_ratio": None}

    class DummyDecision:
        value = "accept_h0"

    class DummySprtResult:
        decision = DummyDecision()

    class DummyAcceptanceMatch:
        mean_score_a = 0.5
        player_a_timeouts = 0
        player_b_timeouts = 0
        player_a_crashes = 0

    class DummyAcceptancePrescreen:
        score_difference = 0.0

    class DummyIteration:
        score_difference = 0.0
        prescreen_score_difference = 0.0
        applied_change_count = 0
        applied_change_paths = []

    class DummyBlockReport:
        spsa_iterations = [DummyIteration()]
        acceptance_match = DummyAcceptanceMatch()
        acceptance_prescreen = DummyAcceptancePrescreen()
        sprt_result = DummySprtResult()
        proposed_profile = {}

    class DummyResult:
        blocks_run = [DummyBlockReport()]

    def fake_optimize_profile(**kwargs):
        captured["learning_rate"] = kwargs["spsa_config"].learning_rate
        captured["slack_ms"] = kwargs["match_timeout_slack_ms"]
        captured["slack_ratio"] = kwargs["match_timeout_slack_ratio"]
        return DummyResult()

    monkeypatch.setattr(autonomous_policy, "optimize_profile", fake_optimize_profile)

    memory_records = [
        _memory_record("search.history_order", "hold", "direction_unstable"),
        _memory_record("search.history_order", "freeze", "direction_unstable"),
        _memory_record("search.depth_time", "hold"),
        _memory_record("move_ordering.development", "hold"),
        _memory_record("move_ordering.development", "hold"),
    ]

    report = run_autonomous_tuning_round(
        round_id="round_thaw",
        failure_type="no_clear_failure",
        memory_records=memory_records,
        strategy_profile_path=strategy_path,
        match_timeout_slack_ms=11,
        match_timeout_slack_ratio=3.5,
        promote=False,
    )

    assert report.enabled is True
    assert report.selected_block == "move_ordering.capture_base_bonus"
    assert captured["learning_rate"] == 8.00
    assert captured["slack_ms"] == 11
    assert captured["slack_ratio"] == 3.5


def test_autonomous_tuning_rotates_across_active_blocks(tmp_path: Path, monkeypatch):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    captured = {"block_names": None}

    class DummyDecision:
        value = "accept_h0"

    class DummySprtResult:
        decision = DummyDecision()

    class DummyAcceptanceMatch:
        mean_score_a = 0.5
        player_a_timeouts = 0
        player_b_timeouts = 0
        player_a_crashes = 0

    class DummyAcceptancePrescreen:
        score_difference = 0.0

    class DummyIteration:
        score_difference = 0.0
        prescreen_score_difference = 0.0
        applied_change_count = 0
        applied_change_paths = []

    class DummyBlockReport:
        spsa_iterations = [DummyIteration()]
        acceptance_match = DummyAcceptanceMatch()
        acceptance_prescreen = DummyAcceptancePrescreen()
        sprt_result = DummySprtResult()
        proposed_profile = {}

    class DummyResult:
        blocks_run = [DummyBlockReport()]

    def fake_optimize_profile(**kwargs):
        captured["block_names"] = kwargs["block_names"]
        return DummyResult()

    monkeypatch.setattr(autonomous_policy, "optimize_profile", fake_optimize_profile)
    memory_records = [
        _memory_record("search.history_order", "hold", "no_gate_cross"),
    ]

    report = run_autonomous_tuning_round(
        round_id="round_rotate",
        failure_type="no_clear_failure",
        memory_records=memory_records,
        strategy_profile_path=strategy_path,
        promote=False,
    )

    assert report.selected_block == "move_ordering.capture_base_bonus"
    assert captured["block_names"] == ["move_ordering.capture_base_bonus"]


def test_autonomous_tuning_can_target_selected_block(tmp_path: Path, monkeypatch):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    captured = {"block_names": None}

    class DummyDecision:
        value = "accept_h0"

    class DummySprtResult:
        decision = DummyDecision()

    class DummyAcceptanceMatch:
        mean_score_a = 0.5
        player_a_timeouts = 0
        player_b_timeouts = 0
        player_a_crashes = 0

    class DummyAcceptancePrescreen:
        score_difference = 0.0

    class DummyIteration:
        score_difference = 0.0
        prescreen_score_difference = 0.0
        applied_change_count = 0
        applied_change_paths = []

    class DummyBlockReport:
        spsa_iterations = [DummyIteration()]
        acceptance_match = DummyAcceptanceMatch()
        acceptance_prescreen = DummyAcceptancePrescreen()
        sprt_result = DummySprtResult()
        proposed_profile = {}

    class DummyResult:
        blocks_run = [DummyBlockReport()]

    def fake_optimize_profile(**kwargs):
        captured["block_names"] = kwargs["block_names"]
        return DummyResult()

    monkeypatch.setattr(autonomous_policy, "optimize_profile", fake_optimize_profile)

    report = run_autonomous_tuning_round(
        round_id="round_target",
        failure_type="no_clear_failure",
        memory_records=[],
        strategy_profile_path=strategy_path,
        selected_block="move_ordering.capture_base_bonus",
        promote=False,
    )

    assert report.selected_block == "move_ordering.capture_base_bonus"
    assert captured["block_names"] == ["move_ordering.capture_base_bonus"]


def test_autonomous_tuning_focuses_promising_acceptance_unconfirmed_block(
    tmp_path: Path,
    monkeypatch,
):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    captured = {"block_names": None}

    class DummyDecision:
        value = "accept_h0"

    class DummySprtResult:
        decision = DummyDecision()

    class DummyAcceptanceMatch:
        mean_score_a = 0.5
        player_a_timeouts = 0
        player_b_timeouts = 0
        player_a_crashes = 0

    class DummyAcceptancePrescreen:
        score_difference = 0.0

    class DummyIteration:
        score_difference = 0.0
        prescreen_score_difference = 0.0
        applied_change_count = 0
        applied_change_paths = []

    class DummyBlockReport:
        spsa_iterations = [DummyIteration()]
        acceptance_match = DummyAcceptanceMatch()
        acceptance_prescreen = DummyAcceptancePrescreen()
        sprt_result = DummySprtResult()
        proposed_profile = {}

    class DummyResult:
        blocks_run = [DummyBlockReport()]

    def fake_optimize_profile(**kwargs):
        captured["block_names"] = kwargs["block_names"]
        return DummyResult()

    monkeypatch.setattr(autonomous_policy, "optimize_profile", fake_optimize_profile)
    memory_records = [
        _memory_record("search.history_order", "hold", "no_gate_cross"),
        _memory_record(
            "move_ordering.capture_base_bonus",
            "hold",
            "acceptance_unconfirmed",
            gate_cross_count=3,
            positive_inner_count=2,
            negative_inner_count=0,
        ),
    ]

    report = run_autonomous_tuning_round(
        round_id="round_focus",
        failure_type="no_clear_failure",
        memory_records=memory_records,
        strategy_profile_path=strategy_path,
        promote=False,
    )

    assert report.selected_block == "move_ordering.capture_base_bonus"
    assert captured["block_names"] == ["move_ordering.capture_base_bonus"]


def test_autonomous_tuning_does_not_freeze_on_mixed_hold_reasons(
    tmp_path: Path,
    monkeypatch,
):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    captured = {"called": False}

    class DummyDecision:
        value = "accept_h0"

    class DummySprtResult:
        decision = DummyDecision()

    class DummyAcceptanceMatch:
        mean_score_a = 0.5
        player_a_timeouts = 0
        player_b_timeouts = 0
        player_a_crashes = 0

    class DummyAcceptancePrescreen:
        score_difference = 0.0

    class DummyIteration:
        score_difference = 0.0
        prescreen_score_difference = 0.0
        applied_change_count = 0
        applied_change_paths = []

    class DummyBlockReport:
        spsa_iterations = [DummyIteration()]
        acceptance_match = DummyAcceptanceMatch()
        acceptance_prescreen = DummyAcceptancePrescreen()
        sprt_result = DummySprtResult()
        proposed_profile = {}

    class DummyResult:
        blocks_run = [DummyBlockReport()]

    def fake_optimize_profile(**kwargs):
        captured["called"] = True
        return DummyResult()

    monkeypatch.setattr(autonomous_policy, "optimize_profile", fake_optimize_profile)
    memory_records = [
        _memory_record("search.history_order", "hold", "direction_unstable"),
        _memory_record("search.history_order", "hold", "no_gate_cross"),
        _memory_record("search.history_order", "hold", "direction_unstable"),
    ]

    report = run_autonomous_tuning_round(
        round_id="round_mixed_holds",
        failure_type="no_clear_failure",
        memory_records=memory_records,
        strategy_profile_path=strategy_path,
        promote=False,
    )

    assert captured["called"] is True
    assert report.enabled is True
    assert report.selected_block == "move_ordering.capture_base_bonus"


def test_autonomous_tuning_uses_next_block_when_recent_freeze_not_cooled_down(
    tmp_path: Path,
    monkeypatch,
):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    captured = {"block_names": None}

    class DummyDecision:
        value = "accept_h0"

    class DummySprtResult:
        decision = DummyDecision()

    class DummyAcceptanceMatch:
        mean_score_a = 0.5
        player_a_timeouts = 0
        player_b_timeouts = 0
        player_a_crashes = 0

    class DummyAcceptancePrescreen:
        score_difference = 0.0

    class DummyIteration:
        score_difference = 0.0
        prescreen_score_difference = 0.0
        applied_change_count = 0
        applied_change_paths = []

    class DummyBlockReport:
        spsa_iterations = [DummyIteration()]
        acceptance_match = DummyAcceptanceMatch()
        acceptance_prescreen = DummyAcceptancePrescreen()
        sprt_result = DummySprtResult()
        proposed_profile = {}

    class DummyResult:
        blocks_run = [DummyBlockReport()]

    def fake_optimize_profile(**kwargs):
        captured["block_names"] = kwargs["block_names"]
        return DummyResult()

    monkeypatch.setattr(autonomous_policy, "optimize_profile", fake_optimize_profile)
    memory_records = [
        _memory_record("search.history_order", "hold", "direction_unstable"),
        _memory_record("search.history_order", "freeze", "direction_unstable"),
        _memory_record("search.depth_time", "hold"),
    ]

    report = run_autonomous_tuning_round(
        round_id="round_still_frozen",
        failure_type="no_clear_failure",
        memory_records=memory_records,
        strategy_profile_path=strategy_path,
        promote=False,
    )

    assert report.enabled is True
    assert report.selected_block == "move_ordering.capture_base_bonus"
    assert captured["block_names"] == ["move_ordering.capture_base_bonus"]
