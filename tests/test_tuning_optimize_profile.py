import random
from pathlib import Path

from tools.strategy_profile import load_strategy_profile
from tuning.optimize_profile import (
    _changed_parameter_paths,
    _collect_block_names,
    load_tuning_registry,
    optimize_profile,
)
from tuning.spsa import SpsaConfig, apply_spsa_result, spsa_update_step


def test_optimize_profile_runs_single_block_without_promoting(tmp_path: Path):
    strategy_path = tmp_path / "strategy_profile.json"
    strategy_path.write_text(Path("config/strategy_profile.json").read_text(encoding="utf-8"))
    report = optimize_profile(
        strategy_profile_path=strategy_path,
        block_names=["pawn_structure"],
        preset="quick",
        iterations=1,
        inner_pair_count=1,
        acceptance_pair_count=1,
        time_limit_ms=15,
        max_plies=12,
        promote=False,
    )
    assert report.strategy_profile_path == str(strategy_path)
    assert report.blocks_run
    assert report.promoted is False
    assert report.preset == "quick"


def test_collect_block_names_supports_recommended_alias():
    registry = load_tuning_registry()
    names = _collect_block_names(registry, ["recommended"])
    assert names is not None
    assert names == ["search.history_order"]


def test_changed_parameter_paths_detects_no_quantized_change():
    registry = load_tuning_registry()
    profile = load_strategy_profile(Path("config/strategy_profile.json"))
    block = registry.block("move_ordering.tactical")
    theta = registry.block_to_unit_vector(profile, block)
    step = spsa_update_step(theta, 1, SpsaConfig(), random.Random(1))
    updated = apply_spsa_result(theta, step, score_difference=0.0013792141705866734)
    candidate = registry.profile_from_unit_vector(profile, block, updated)

    assert _changed_parameter_paths(profile, candidate, block) == []


def test_changed_parameter_paths_detects_quantized_update():
    registry = load_tuning_registry()
    profile = load_strategy_profile(Path("config/strategy_profile.json"))
    block = registry.block("search.history_order")
    theta = registry.block_to_unit_vector(profile, block)
    step = spsa_update_step(theta, 1, SpsaConfig(), random.Random(1))
    updated = apply_spsa_result(theta, step, score_difference=0.02)
    candidate = registry.profile_from_unit_vector(profile, block, updated)

    changed = _changed_parameter_paths(profile, candidate, block)
    assert changed
    assert "search.tt_move_bonus" in changed
