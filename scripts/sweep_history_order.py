from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from itertools import product
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.serialization import to_plain_data
from tools.strategy_profile import load_strategy_profile
from tuning.optimize_profile import PRESETS, optimize_profile
from tuning.parameter_registry import DEFAULT_TUNING_REGISTRY_PATH, load_tuning_registry
from tuning.spsa import SpsaConfig

DEFAULT_BLOCK = "search.history_order"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sweep search.history_order SPSA settings and summarize which combinations "
            "most often cross the discrete parameter gate."
        )
    )
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
    parser.add_argument(
        "--block",
        default=DEFAULT_BLOCK,
        help=f"Tuning block to study. Defaults to {DEFAULT_BLOCK}.",
    )
    parser.add_argument(
        "--parameter-paths",
        default="",
        help=(
            "Optional comma-separated subset of parameter paths to keep tunable within the "
            "selected block. Other parameters in the block are temporarily frozen."
        ),
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        default="quick",
        help="Base match budget. Numeric flags override the preset values.",
    )
    parser.add_argument(
        "--seeds",
        default="1,2,3,4,5",
        help="Comma-separated random seeds to evaluate for each combination.",
    )
    parser.add_argument(
        "--learning-rates",
        default="0.30,0.45,0.60",
        help="Comma-separated SPSA learning rates to sweep.",
    )
    parser.add_argument(
        "--perturbations",
        default="0.08,0.10,0.12",
        help="Comma-separated SPSA perturbation values to sweep.",
    )
    parser.add_argument(
        "--iterations-list",
        default="1,2,3",
        help="Comma-separated SPSA iteration counts to sweep.",
    )
    parser.add_argument("--inner-pairs", type=int)
    parser.add_argument("--acceptance-pairs", type=int)
    parser.add_argument("--time-limit-ms", type=int)
    parser.add_argument("--max-plies", type=int)
    parser.add_argument("--alpha", type=float, default=0.602)
    parser.add_argument("--gamma", type=float, default=0.101)
    parser.add_argument("--stability-constant", type=float, default=5.0)
    parser.add_argument(
        "--top",
        type=int,
        default=8,
        help="Number of highest-ranked combinations to echo in top_experiments.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    seeds = _parse_int_list(args.seeds)
    learning_rates = _parse_float_list(args.learning_rates)
    perturbations = _parse_float_list(args.perturbations)
    iteration_counts = _parse_int_list(args.iterations_list)
    selected_parameter_paths = _parse_optional_csv(args.parameter_paths)

    registry_path = _prepare_registry_path(
        source_registry_path=args.registry,
        block_name=args.block,
        selected_parameter_paths=selected_parameter_paths,
    )
    registry = load_tuning_registry(registry_path)
    block = registry.block(args.block)
    baseline_profile = load_strategy_profile(args.strategy_profile)
    baseline_payload = baseline_profile.model_dump()
    baseline_parameters = {
        parameter.path: _get_path(baseline_payload, parameter.path)
        for parameter in block.tunable_parameters()
    }

    experiments: List[Dict[str, Any]] = []
    for learning_rate, perturbation, iterations in product(
        learning_rates,
        perturbations,
        iteration_counts,
    ):
        experiments.append(
            _run_experiment(
                strategy_profile_path=args.strategy_profile,
                registry_path=registry_path,
                block_name=args.block,
                selected_parameter_paths=selected_parameter_paths,
                preset=args.preset,
                seeds=seeds,
                learning_rate=learning_rate,
                perturbation=perturbation,
                iterations=iterations,
                inner_pair_count=args.inner_pairs,
                acceptance_pair_count=args.acceptance_pairs,
                time_limit_ms=args.time_limit_ms,
                max_plies=args.max_plies,
                alpha=args.alpha,
                gamma=args.gamma,
                stability_constant=args.stability_constant,
            )
        )

    ranked_experiments = sorted(experiments, key=_ranking_key, reverse=True)
    payload = {
        "block": args.block,
        "selected_parameter_paths": selected_parameter_paths,
        "baseline_parameters": baseline_parameters,
        "strategy_profile_path": str(args.strategy_profile),
        "registry_path": str(registry_path),
        "sweep": {
            "preset": args.preset,
            "seeds": seeds,
            "learning_rates": learning_rates,
            "perturbations": perturbations,
            "iterations_list": iteration_counts,
            "inner_pair_count": args.inner_pairs,
            "acceptance_pair_count": args.acceptance_pairs,
            "time_limit_ms": args.time_limit_ms,
            "max_plies": args.max_plies,
            "alpha": args.alpha,
            "gamma": args.gamma,
            "stability_constant": args.stability_constant,
        },
        "experiment_count": len(ranked_experiments),
        "top_experiments": ranked_experiments[: max(0, args.top)],
        "experiments": ranked_experiments,
    }
    text = json.dumps(to_plain_data(payload), ensure_ascii=False, indent=2, sort_keys=True)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)


def _run_experiment(
    *,
    strategy_profile_path: Path,
    registry_path: Path,
    block_name: str,
    selected_parameter_paths: List[str],
    preset: str,
    seeds: List[int],
    learning_rate: float,
    perturbation: float,
    iterations: int,
    inner_pair_count: int | None,
    acceptance_pair_count: int | None,
    time_limit_ms: int | None,
    max_plies: int | None,
    alpha: float,
    gamma: float,
    stability_constant: float,
) -> Dict[str, Any]:
    seed_results: List[Dict[str, Any]] = []
    changed_path_counts: Counter[str] = Counter()

    for seed in seeds:
        report = optimize_profile(
            strategy_profile_path=strategy_profile_path,
            registry_path=registry_path,
            block_names=[block_name],
            preset=preset,
            iterations=iterations,
            inner_pair_count=inner_pair_count,
            acceptance_pair_count=acceptance_pair_count,
            time_limit_ms=time_limit_ms,
            max_plies=max_plies,
            random_seed=seed,
            spsa_config=SpsaConfig(
                alpha=alpha,
                gamma=gamma,
                learning_rate=learning_rate,
                perturbation=perturbation,
                stability_constant=stability_constant,
            ),
            promote=False,
        )
        block_report = report.blocks_run[0]
        last_iteration = block_report.spsa_iterations[-1] if block_report.spsa_iterations else None
        acceptance_match = block_report.acceptance_match
        acceptance_prescreen = block_report.acceptance_prescreen
        changed_paths = (
            list(last_iteration.applied_change_paths) if last_iteration is not None else []
        )
        changed_path_counts.update(changed_paths)
        acceptance_mean_score_a = (
            float(acceptance_match.mean_score_a) if acceptance_match is not None else 0.5
        )
        acceptance_prescreen_difference = (
            float(acceptance_prescreen.score_difference)
            if acceptance_prescreen is not None
            else 0.0
        )
        score_difference = float(last_iteration.score_difference) if last_iteration else 0.0
        match_score_difference = (
            float(last_iteration.match_score_difference) if last_iteration else 0.0
        )
        prescreen_score_difference = (
            float(last_iteration.prescreen_score_difference) if last_iteration else 0.0
        )
        applied_change_count = int(last_iteration.applied_change_count) if last_iteration else 0
        safe = _seed_is_safe(acceptance_match)
        promotable = (
            score_difference > 0.0
            and applied_change_count > 0
            and acceptance_prescreen_difference >= 0.0
            and acceptance_mean_score_a >= 0.5
            and safe
        )
        seed_results.append(
            {
                "seed": seed,
                "score_difference": round(score_difference, 6),
                "match_score_difference": round(match_score_difference, 6),
                "prescreen_score_difference": round(prescreen_score_difference, 6),
                "applied_change_count": applied_change_count,
                "applied_change_paths": changed_paths,
                "acceptance_prescreen_difference": round(
                    acceptance_prescreen_difference,
                    6,
                ),
                "acceptance_mean_score_a": round(acceptance_mean_score_a, 6),
                "player_a_timeouts": (
                    int(acceptance_match.player_a_timeouts) if acceptance_match is not None else 0
                ),
                "player_b_timeouts": (
                    int(acceptance_match.player_b_timeouts) if acceptance_match is not None else 0
                ),
                "player_a_crashes": (
                    int(acceptance_match.player_a_crashes) if acceptance_match is not None else 0
                ),
                "sprt_decision": (
                    block_report.sprt_result.decision.value
                    if block_report.sprt_result is not None
                    else ""
                ),
                "safe": safe,
                "promotable": promotable,
                "skipped_reason": block_report.skipped_reason,
            }
        )

    experiment = _summarize_experiment(
        block_name=block_name,
        preset=preset,
        seeds=seeds,
        learning_rate=learning_rate,
        perturbation=perturbation,
        iterations=iterations,
        inner_pair_count=inner_pair_count,
        acceptance_pair_count=acceptance_pair_count,
        time_limit_ms=time_limit_ms,
        max_plies=max_plies,
        seed_results=seed_results,
        changed_path_counts=changed_path_counts,
    )
    experiment["repro_command"] = _repro_command(
        block_name=block_name,
        preset=preset,
        seeds=seeds,
        learning_rate=learning_rate,
        perturbation=perturbation,
        iterations=iterations,
        inner_pair_count=inner_pair_count,
        acceptance_pair_count=acceptance_pair_count,
        time_limit_ms=time_limit_ms,
        max_plies=max_plies,
        selected_parameter_paths=selected_parameter_paths,
    )
    return experiment


def _summarize_experiment(
    *,
    block_name: str,
    preset: str,
    seeds: List[int],
    learning_rate: float,
    perturbation: float,
    iterations: int,
    inner_pair_count: int | None,
    acceptance_pair_count: int | None,
    time_limit_ms: int | None,
    max_plies: int | None,
    seed_results: List[Dict[str, Any]],
    changed_path_counts: Counter[str],
) -> Dict[str, Any]:
    gate_cross_count = sum(1 for item in seed_results if item["applied_change_count"] > 0)
    positive_inner_count = sum(1 for item in seed_results if item["score_difference"] > 0.0)
    negative_inner_count = sum(1 for item in seed_results if item["score_difference"] < 0.0)
    positive_acceptance_prescreen_count = sum(
        1 for item in seed_results if item["acceptance_prescreen_difference"] > 0.0
    )
    negative_acceptance_prescreen_count = sum(
        1 for item in seed_results if item["acceptance_prescreen_difference"] < 0.0
    )
    safe_seed_count = sum(1 for item in seed_results if item["safe"])
    promotable_seed_count = sum(1 for item in seed_results if item["promotable"])
    changed_parameter_counts = [
        int(item["applied_change_count"]) for item in seed_results if item["applied_change_count"] > 0
    ]
    candidate_ready_proxy = (
        gate_cross_count > 0
        and negative_inner_count == 0
        and positive_inner_count > 0
        and promotable_seed_count >= 2
        and safe_seed_count == len(seed_results)
    )
    return {
        "block_name": block_name,
        "preset": preset,
        "combination": {
            "learning_rate": learning_rate,
            "perturbation": perturbation,
            "iterations": iterations,
            "seed_count": len(seeds),
            "inner_pair_count": inner_pair_count,
            "acceptance_pair_count": acceptance_pair_count,
            "time_limit_ms": time_limit_ms,
            "max_plies": max_plies,
        },
        "summary": {
            "candidate_ready_proxy": candidate_ready_proxy,
            "gate_cross_count": gate_cross_count,
            "gate_cross_rate": round(gate_cross_count / max(1, len(seed_results)), 4),
            "positive_inner_count": positive_inner_count,
            "negative_inner_count": negative_inner_count,
            "positive_acceptance_prescreen_count": positive_acceptance_prescreen_count,
            "negative_acceptance_prescreen_count": negative_acceptance_prescreen_count,
            "safe_seed_count": safe_seed_count,
            "promotable_seed_count": promotable_seed_count,
            "all_positive_inner": positive_inner_count == len(seed_results),
            "no_negative_inner": negative_inner_count == 0,
            "mean_score_difference": round(_mean_of(seed_results, "score_difference"), 6),
            "mean_match_score_difference": round(
                _mean_of(seed_results, "match_score_difference"),
                6,
            ),
            "mean_prescreen_score_difference": round(
                _mean_of(seed_results, "prescreen_score_difference"),
                6,
            ),
            "mean_acceptance_prescreen_difference": round(
                _mean_of(seed_results, "acceptance_prescreen_difference"),
                6,
            ),
            "mean_acceptance_mean_score_a": round(
                _mean_of(seed_results, "acceptance_mean_score_a"),
                6,
            ),
            "mean_applied_change_count": round(
                mean(changed_parameter_counts) if changed_parameter_counts else 0.0,
                4,
            ),
            "changed_path_counts": dict(sorted(changed_path_counts.items())),
        },
        "seeds": seed_results,
    }


def _ranking_key(experiment: Dict[str, Any]) -> tuple:
    summary = experiment["summary"]
    combination = experiment["combination"]
    return (
        int(summary["candidate_ready_proxy"]),
        int(summary["promotable_seed_count"]),
        float(summary["gate_cross_rate"]),
        int(summary["no_negative_inner"]),
        float(summary["mean_score_difference"]),
        float(summary["mean_acceptance_prescreen_difference"]),
        float(summary["mean_applied_change_count"]),
        -int(combination["iterations"]),
    )


def _seed_is_safe(match: Any) -> bool:
    if match is None:
        return True
    if int(match.player_a_crashes) > 0:
        return False
    return int(match.player_a_timeouts) <= int(match.player_b_timeouts) + max(
        1,
        int(match.player_b_timeouts),
    )


def _mean_of(records: Iterable[Dict[str, Any]], field: str) -> float:
    values = [float(record[field]) for record in records]
    return mean(values) if values else 0.0


def _parse_int_list(raw_value: str) -> List[int]:
    values = [item.strip() for item in raw_value.split(",")]
    result = [int(item) for item in values if item]
    if not result:
        raise ValueError("Expected at least one integer value.")
    return result


def _parse_float_list(raw_value: str) -> List[float]:
    values = [item.strip() for item in raw_value.split(",")]
    result = [float(item) for item in values if item]
    if not result:
        raise ValueError("Expected at least one float value.")
    return result


def _parse_optional_csv(raw_value: str) -> List[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _prepare_registry_path(
    *,
    source_registry_path: Path,
    block_name: str,
    selected_parameter_paths: List[str],
) -> Path:
    if not selected_parameter_paths:
        return Path(source_registry_path)
    payload = json.loads(Path(source_registry_path).read_text(encoding="utf-8"))
    blocks = payload.get("blocks", [])
    block = next(
        (item for item in blocks if isinstance(item, dict) and item.get("name") == block_name),
        None,
    )
    if block is None:
        raise ValueError(f"Unknown tuning block: {block_name}")
    parameters = block.get("parameters", [])
    available_paths = {
        parameter.get("path", "")
        for parameter in parameters
        if isinstance(parameter, dict)
    }
    unknown_paths = [path for path in selected_parameter_paths if path not in available_paths]
    if unknown_paths:
        joined = ", ".join(sorted(unknown_paths))
        raise ValueError(f"Unknown parameter path(s) for {block_name}: {joined}")
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        path = str(parameter.get("path", ""))
        parameter["frozen"] = path not in selected_parameter_paths
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir="/private/tmp",
        prefix=f"{block_name.replace('.', '_')}_",
        suffix="_registry.json",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        return Path(handle.name)


def _get_path(payload: Dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        current = current[part]
    return current


def _repro_command(
    *,
    block_name: str,
    preset: str,
    seeds: List[int],
    learning_rate: float,
    perturbation: float,
    iterations: int,
    inner_pair_count: int | None,
    acceptance_pair_count: int | None,
    time_limit_ms: int | None,
    max_plies: int | None,
    selected_parameter_paths: List[str],
) -> str:
    parts = [
        "python3 scripts/sweep_history_order.py",
        f"--block {block_name}",
        f"--preset {preset}",
        f"--seeds {','.join(str(seed) for seed in seeds)}",
        f"--learning-rates {learning_rate}",
        f"--perturbations {perturbation}",
        f"--iterations-list {iterations}",
        "--top 1",
    ]
    if selected_parameter_paths:
        parts.append(f"--parameter-paths {','.join(selected_parameter_paths)}")
    if inner_pair_count is not None:
        parts.append(f"--inner-pairs {inner_pair_count}")
    if acceptance_pair_count is not None:
        parts.append(f"--acceptance-pairs {acceptance_pair_count}")
    if time_limit_ms is not None:
        parts.append(f"--time-limit-ms {time_limit_ms}")
    if max_plies is not None:
        parts.append(f"--max-plies {max_plies}")
    return " ".join(parts)


if __name__ == "__main__":
    main()
