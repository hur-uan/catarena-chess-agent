"""CLI entrypoint for block-wise strategy-profile tuning."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from tools.serialization import to_plain_data
from tools.strategy_profile import StrategyProfile, load_strategy_profile
from tuning.match_runner import MatchConfig, MatchSummary, run_paired_match
from tuning.parameter_registry import (
    DEFAULT_TUNING_REGISTRY_PATH,
    TuningBlock,
    TuningRegistry,
    load_tuning_registry,
)
from tuning.prescreen import PrescreenConfig, PrescreenSummary, run_fen_prescreen
from tuning.sprt import SprtConfig, SprtResult, evaluate_sprt
from tuning.spsa import SpsaConfig, SpsaIteration, apply_spsa_result, spsa_update_step


class BlockOptimizationReport(BaseModel):
    block_name: str
    tuner: str
    iterations: int = 0
    updated: bool = False
    skipped_reason: str = ""
    inner_match_pairs: int = 0
    acceptance_match_pairs: int = 0
    proposed_profile: Dict[str, object] = Field(default_factory=dict)
    candidate_profile: Dict[str, object] = Field(default_factory=dict)
    spsa_iterations: List[SpsaIteration] = Field(default_factory=list)
    acceptance_match: Optional[MatchSummary] = None
    acceptance_prescreen: Optional[PrescreenSummary] = None
    sprt_result: Optional[SprtResult] = None


class OptimizationReport(BaseModel):
    strategy_profile_path: str
    registry_path: str
    preset: str = "local"
    promoted: bool = False
    blocks_run: List[BlockOptimizationReport] = Field(default_factory=list)
    final_profile: Dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True)
class RunPreset:
    iterations: int
    inner_pair_count: int
    acceptance_pair_count: int
    time_limit_ms: int
    max_plies: int


PRESETS: Dict[str, RunPreset] = {
    "quick": RunPreset(
        iterations=2,
        inner_pair_count=4,
        acceptance_pair_count=8,
        time_limit_ms=25,
        max_plies=24,
    ),
    "local": RunPreset(
        iterations=3,
        inner_pair_count=8,
        acceptance_pair_count=16,
        time_limit_ms=40,
        max_plies=48,
    ),
    "signal": RunPreset(
        iterations=4,
        inner_pair_count=12,
        acceptance_pair_count=24,
        time_limit_ms=50,
        max_plies=64,
    ),
}


def optimize_profile(
    strategy_profile_path: Path,
    registry_path: Path = DEFAULT_TUNING_REGISTRY_PATH,
    block_names: Optional[List[str]] = None,
    preset: str = "local",
    iterations: Optional[int] = None,
    inner_pair_count: Optional[int] = None,
    acceptance_pair_count: Optional[int] = None,
    time_limit_ms: Optional[int] = None,
    max_plies: Optional[int] = None,
    match_timeout_slack_ms: int = 5,
    match_timeout_slack_ratio: float = 0.20,
    random_seed: int = 7,
    spsa_config: Optional[SpsaConfig] = None,
    promote: bool = False,
) -> OptimizationReport:
    registry = load_tuning_registry(registry_path)
    active_profile = load_strategy_profile(strategy_profile_path)
    blocks = registry.resolve_blocks(block_names, enabled_only=block_names is None)
    rng = random.Random(random_seed)
    resolved_preset = PRESETS[preset]
    resolved_iterations = iterations or resolved_preset.iterations
    resolved_inner_pairs = inner_pair_count or resolved_preset.inner_pair_count
    resolved_acceptance_pairs = acceptance_pair_count or resolved_preset.acceptance_pair_count
    resolved_time_limit_ms = time_limit_ms or resolved_preset.time_limit_ms
    resolved_max_plies = max_plies or resolved_preset.max_plies
    resolved_spsa_config = spsa_config or SpsaConfig()
    report = OptimizationReport(
        strategy_profile_path=str(strategy_profile_path),
        registry_path=str(registry_path),
        preset=preset,
    )

    for block in blocks:
        block_report = _optimize_block(
            active_profile=active_profile,
            block=block,
            registry=registry,
            iterations=resolved_iterations,
            inner_pair_count=resolved_inner_pairs,
            acceptance_pair_count=resolved_acceptance_pairs,
            time_limit_ms=resolved_time_limit_ms,
            max_plies=resolved_max_plies,
            match_timeout_slack_ms=max(0, match_timeout_slack_ms),
            match_timeout_slack_ratio=max(0.0, match_timeout_slack_ratio),
            rng=rng,
            spsa_config=resolved_spsa_config,
        )
        report.blocks_run.append(block_report)
        if block_report.updated and block_report.candidate_profile:
            active_profile = StrategyProfile.model_validate(block_report.candidate_profile)

    report.final_profile = active_profile.model_dump()
    if promote:
        strategy_profile_path.write_text(
            json.dumps(report.final_profile, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        report.promoted = True
    return report


def _optimize_block(
    active_profile: StrategyProfile,
    block: TuningBlock,
    registry: TuningRegistry,
    iterations: int,
    inner_pair_count: int,
    acceptance_pair_count: int,
    time_limit_ms: int,
    max_plies: int,
    match_timeout_slack_ms: int,
    match_timeout_slack_ratio: float,
    rng: random.Random,
    spsa_config: SpsaConfig,
) -> BlockOptimizationReport:
    block_report = BlockOptimizationReport(
        block_name=block.name,
        tuner=block.tuner,
        iterations=iterations,
        inner_match_pairs=inner_pair_count,
        acceptance_match_pairs=acceptance_pair_count,
    )
    if block.tuner != "spsa":
        block_report.skipped_reason = f"tuner '{block.tuner}' is not implemented in the first pass"
        return block_report
    if block.mode_scope != "internal_only":
        block_report.skipped_reason = "first-pass tuner only supports internal_only blocks"
        return block_report
    theta = registry.block_to_unit_vector(active_profile, block)
    if not theta:
        block_report.skipped_reason = "block has no tunable parameters after freezing"
        return block_report

    working_profile = active_profile
    prescreen_time_limit_ms = block.prescreen_time_limit_ms or time_limit_ms
    for iteration in range(1, iterations + 1):
        step = spsa_update_step(theta, iteration, spsa_config, rng)
        plus_profile = registry.profile_from_unit_vector(working_profile, block, step.plus_vector)
        minus_profile = registry.profile_from_unit_vector(working_profile, block, step.minus_vector)
        prescreen = run_fen_prescreen(
            plus_profile,
            minus_profile,
            baseline_profile=active_profile,
            config=PrescreenConfig(
                candidate_time_limit_ms=prescreen_time_limit_ms,
                oracle_time_limit_ms=max(60, prescreen_time_limit_ms * 3),
                signal_mode=block.signal_mode,
                prescreen_set=block.prescreen_set,
            ),
        )
        inner_match = run_paired_match(
            plus_profile,
            minus_profile,
            MatchConfig(
                pair_count=inner_pair_count,
                time_limit_ms=time_limit_ms,
                max_plies=max_plies,
                timeout_slack_ms=match_timeout_slack_ms,
                timeout_slack_ratio=match_timeout_slack_ratio,
            ),
        )
        difference = _combined_signal(inner_match, prescreen)
        previous_profile = working_profile
        theta = apply_spsa_result(
            theta,
            step,
            difference,
            min_effective_score_difference=spsa_config.min_effective_score_difference,
        )
        working_profile = registry.profile_from_unit_vector(working_profile, block, theta)
        applied_change_paths = _changed_parameter_paths(
            previous_profile,
            working_profile,
            block,
        )
        block_report.spsa_iterations.append(
            SpsaIteration(
                step=step,
                score_difference=difference,
                match_score_difference=(2.0 * inner_match.mean_score_a) - 1.0,
                prescreen_score_difference=prescreen.score_difference,
                updated_vector=theta,
                applied_change_count=len(applied_change_paths),
                applied_change_paths=applied_change_paths,
            )
        )

    acceptance_match = run_paired_match(
        working_profile,
        active_profile,
        MatchConfig(
            pair_count=acceptance_pair_count,
            time_limit_ms=time_limit_ms,
            max_plies=max_plies,
            timeout_slack_ms=match_timeout_slack_ms,
            timeout_slack_ratio=match_timeout_slack_ratio,
        ),
    )
    acceptance_prescreen = run_fen_prescreen(
        working_profile,
        active_profile,
        baseline_profile=active_profile,
        config=PrescreenConfig(
            candidate_time_limit_ms=prescreen_time_limit_ms,
            oracle_time_limit_ms=max(60, prescreen_time_limit_ms * 3),
            signal_mode=block.signal_mode,
            prescreen_set=block.prescreen_set,
        ),
    )
    sprt_result = evaluate_sprt(acceptance_match.game_scores_a, SprtConfig())
    block_report.acceptance_match = acceptance_match
    block_report.acceptance_prescreen = acceptance_prescreen
    block_report.sprt_result = sprt_result
    block_report.proposed_profile = working_profile.model_dump()

    if _passes_hard_gate(acceptance_match) and sprt_result.decision.value == "accept_h1":
        block_report.updated = True
        block_report.candidate_profile = working_profile.model_dump()
    else:
        block_report.candidate_profile = active_profile.model_dump()
    return block_report


def _passes_hard_gate(match: MatchSummary) -> bool:
    if match.player_a_crashes > 0:
        return False
    timeout_margin = max(1, match.player_b_timeouts)
    if match.player_a_timeouts > match.player_b_timeouts + timeout_margin:
        return False
    return match.timeout_rate_a() <= match.timeout_rate_b() + 0.02


def _combined_signal(match: MatchSummary, prescreen: PrescreenSummary) -> float:
    match_signal = (2.0 * match.mean_score_a) - 1.0
    if abs(match_signal) >= 0.05:
        return 0.75 * match_signal + 0.25 * prescreen.score_difference
    return 0.4 * match_signal + 0.6 * prescreen.score_difference


def _changed_parameter_paths(
    baseline_profile: StrategyProfile,
    candidate_profile: StrategyProfile,
    block: TuningBlock,
) -> List[str]:
    baseline = baseline_profile.model_dump()
    candidate = candidate_profile.model_dump()
    changed: List[str] = []
    for parameter in block.tunable_parameters():
        if _get_path(candidate, parameter.path) != _get_path(baseline, parameter.path):
            changed.append(parameter.path)
    return changed


def _get_path(payload: Dict[str, object], path: str) -> object:
    current: object = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            raise KeyError(path)
        current = current[part]
    return current


def _collect_block_names(
    registry: TuningRegistry,
    raw_blocks: Optional[List[str]],
) -> Optional[List[str]]:
    if not raw_blocks:
        return None
    if len(raw_blocks) == 1 and raw_blocks[0].strip().lower() == "all":
        return [block.name for block in registry.resolve_blocks()]
    collected: List[str] = []
    valid_names = {block.name for block in registry.blocks}
    for raw in raw_blocks:
        for candidate in raw.split(","):
            name = candidate.strip()
            if not name:
                continue
            if name == "recommended":
                collected.extend([block.name for block in registry.resolve_blocks()])
                continue
            if name not in valid_names:
                raise ValueError(f"Unknown tuning block: {name}")
            collected.append(name)
    return list(dict.fromkeys(collected))


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune the chess strategy profile.")
    parser.add_argument(
        "--strategy-profile",
        type=Path,
        default=Path("config/strategy_profile.json"),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_TUNING_REGISTRY_PATH,
    )
    parser.add_argument("--block", action="append", dest="blocks")
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        default="local",
        help="Default experiment scale. Individual numeric flags override the preset.",
    )
    parser.add_argument("--list-blocks", action="store_true")
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--inner-pairs", type=int)
    parser.add_argument("--acceptance-pairs", type=int)
    parser.add_argument("--time-limit-ms", type=int)
    parser.add_argument("--max-plies", type=int)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()
    registry = load_tuning_registry(args.registry)
    if args.list_blocks:
        print(
            json.dumps(
                [
                    {
                        "name": block.name,
                        "tuner": block.tuner,
                        "mode_scope": block.mode_scope,
                        "enabled": block.enabled,
                    }
                    for block in registry.blocks
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    block_names = _collect_block_names(registry, args.blocks)

    report = optimize_profile(
        strategy_profile_path=args.strategy_profile,
        registry_path=args.registry,
        block_names=block_names,
        preset=args.preset,
        iterations=args.iterations,
        inner_pair_count=args.inner_pairs,
        acceptance_pair_count=args.acceptance_pairs,
        time_limit_ms=args.time_limit_ms,
        max_plies=args.max_plies,
        random_seed=args.seed,
        promote=args.promote,
    )
    print(json.dumps(to_plain_data(report), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
