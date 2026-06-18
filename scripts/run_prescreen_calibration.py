from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.serialization import to_plain_data
from tools.strategy_profile import (
    DEFAULT_STRATEGY_PROFILE_PATH,
    StrategyProfile,
    load_strategy_profile,
)
from tuning.parameter_registry import (
    DEFAULT_TUNING_REGISTRY_PATH,
    ParameterSpec,
    TuningBlock,
    load_tuning_registry,
)
from tuning.prescreen import PrescreenConfig, PrescreenSummary, run_fen_prescreen


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate whether prescreen sets can distinguish profile perturbations."
    )
    parser.add_argument("--strategy-profile", type=Path, default=DEFAULT_STRATEGY_PROFILE_PATH)
    parser.add_argument("--registry", type=Path, default=DEFAULT_TUNING_REGISTRY_PATH)
    parser.add_argument("--blocks", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-time-limit-ms", type=int, default=40)
    parser.add_argument("--oracle-time-limit-ms", type=int, default=120)
    parser.add_argument("--step-multiplier", type=float, default=2.0)
    parser.add_argument("--include-frozen", action="store_true")
    parser.add_argument("--use-external-oracle", action="store_true")
    args = parser.parse_args()

    profile = load_strategy_profile(args.strategy_profile)
    registry = load_tuning_registry(args.registry)
    blocks = registry.resolve_blocks(args.blocks, enabled_only=False)

    report = {
        "strategy_profile_path": str(args.strategy_profile),
        "registry_path": str(args.registry),
        "candidate_time_limit_ms": args.candidate_time_limit_ms,
        "oracle_time_limit_ms": args.oracle_time_limit_ms,
        "step_multiplier": args.step_multiplier,
        "include_frozen": args.include_frozen,
        "use_external_oracle": args.use_external_oracle,
        "blocks": [
            _calibrate_block(
                profile=profile,
                block=block,
                include_frozen=args.include_frozen,
                candidate_time_limit_ms=args.candidate_time_limit_ms,
                oracle_time_limit_ms=args.oracle_time_limit_ms,
                step_multiplier=args.step_multiplier,
                use_external_oracle=args.use_external_oracle,
            )
            for block in blocks
        ],
    }
    report["summary"] = _summarize_blocks(report["blocks"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(to_plain_data(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            to_plain_data(report["summary"]),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _calibrate_block(
    *,
    profile: StrategyProfile,
    block: TuningBlock,
    include_frozen: bool,
    candidate_time_limit_ms: int,
    oracle_time_limit_ms: int,
    step_multiplier: float,
    use_external_oracle: bool,
) -> Dict[str, Any]:
    parameters = block.parameters if include_frozen else block.tunable_parameters()
    parameter_reports = [
        _calibrate_parameter(
            profile=profile,
            block=block,
            parameter=parameter,
            candidate_time_limit_ms=candidate_time_limit_ms,
            oracle_time_limit_ms=oracle_time_limit_ms,
            step_multiplier=step_multiplier,
            use_external_oracle=use_external_oracle,
        )
        for parameter in parameters
    ]
    return {
        "block_name": block.name,
        "signal_mode": block.signal_mode,
        "prescreen_set": block.prescreen_set,
        "parameter_count": len(parameter_reports),
        "parameters": parameter_reports,
        "summary": _summarize_parameters(parameter_reports),
    }


def _calibrate_parameter(
    *,
    profile: StrategyProfile,
    block: TuningBlock,
    parameter: ParameterSpec,
    candidate_time_limit_ms: int,
    oracle_time_limit_ms: int,
    step_multiplier: float,
    use_external_oracle: bool,
) -> Dict[str, Any]:
    current_value = _get_path(profile.model_dump(), parameter.path)
    variants = []
    for direction, raw_value in _parameter_variant_values(
        parameter,
        current_value,
        step_multiplier,
    ):
        candidate = _profile_with_parameter(profile, parameter, raw_value)
        summary = run_fen_prescreen(
            candidate,
            profile,
            baseline_profile=profile,
            config=PrescreenConfig(
                candidate_time_limit_ms=candidate_time_limit_ms,
                oracle_time_limit_ms=oracle_time_limit_ms,
                signal_mode=block.signal_mode,
                prescreen_set=block.prescreen_set,
                use_external_oracle=use_external_oracle,
            ),
        )
        variants.append(
            {
                "direction": direction,
                "current_value": current_value,
                "candidate_value": raw_value,
                "summary": _summarize_prescreen_results(summary),
            }
        )
    return {
        "path": parameter.path,
        "frozen": parameter.frozen,
        "type": parameter.type,
        "step": parameter.step,
        "current_value": current_value,
        "variants": variants,
        "summary": _summarize_variants(variants),
    }


def _parameter_variant_values(
    parameter: ParameterSpec,
    current_value: Any,
    step_multiplier: float,
) -> List[tuple[str, Any]]:
    delta = max(parameter.step, 1e-9) * max(1.0, step_multiplier)
    raw_values = [
        ("minus", parameter.quantize(float(current_value) - delta)),
        ("plus", parameter.quantize(float(current_value) + delta)),
    ]
    seen = {current_value}
    variants = []
    for direction, value in raw_values:
        if value in seen:
            continue
        seen.add(value)
        variants.append((direction, value))
    return variants


def _profile_with_parameter(
    profile: StrategyProfile,
    parameter: ParameterSpec,
    value: Any,
) -> StrategyProfile:
    payload = profile.model_dump()
    _set_path(payload, parameter.path, value)
    return StrategyProfile.model_validate(payload)


def _summarize_prescreen_results(summary: PrescreenSummary) -> Dict[str, Any]:
    per_position_diffs = [
        float(result.score_a) - float(result.score_b)
        for result in summary.results
    ]
    move_diff_count = sum(1 for result in summary.results if result.move_a != result.move_b)
    root_score_diff_count = sum(
        1 for result in summary.results if result.root_score_a_cp != result.root_score_b_cp
    )
    line_score_diff_count = sum(
        1 for result in summary.results if result.line_score_a_cp != result.line_score_b_cp
    )
    nonzero_position_score_count = sum(
        1 for difference in per_position_diffs if abs(difference) > 1e-9
    )
    differing_positions = []
    for result, score_difference in zip(summary.results, per_position_diffs):
        if (
            abs(score_difference) <= 1e-9
            and result.move_a == result.move_b
            and result.root_score_a_cp == result.root_score_b_cp
            and result.line_score_a_cp == result.line_score_b_cp
        ):
            continue
        differing_positions.append(
            {
                "name": result.name,
                "fen": result.fen,
                "move_a": result.move_a,
                "move_b": result.move_b,
                "score_difference": score_difference,
                "score_a": result.score_a,
                "score_b": result.score_b,
                "root_score_a_cp": result.root_score_a_cp,
                "root_score_b_cp": result.root_score_b_cp,
                "line_score_a_cp": result.line_score_a_cp,
                "line_score_b_cp": result.line_score_b_cp,
                "oracle_move": result.oracle_move,
                "oracle_line_cp": result.oracle_line_cp,
            }
        )
    return {
        "positions": summary.positions,
        "mean_score_a": summary.mean_score_a,
        "mean_score_b": summary.mean_score_b,
        "score_difference": summary.score_difference,
        "move_diff_count": move_diff_count,
        "root_score_diff_count": root_score_diff_count,
        "line_score_diff_count": line_score_diff_count,
        "nonzero_position_score_count": nonzero_position_score_count,
        "max_abs_position_score_difference": (
            max((abs(difference) for difference in per_position_diffs), default=0.0)
        ),
        "differing_positions": differing_positions,
    }


def _summarize_variants(variants: List[Dict[str, Any]]) -> Dict[str, Any]:
    summaries = [variant["summary"] for variant in variants]
    score_differences = [float(summary["score_difference"]) for summary in summaries]
    return {
        "variant_count": len(variants),
        "nonzero_variant_count": sum(1 for value in score_differences if abs(value) > 1e-9),
        "move_diff_variant_count": sum(
            1 for summary in summaries if int(summary["move_diff_count"]) > 0
        ),
        "max_abs_score_difference": max(
            (abs(value) for value in score_differences),
            default=0.0,
        ),
        "max_move_diff_count": max(
            (int(summary["move_diff_count"]) for summary in summaries),
            default=0,
        ),
    }


def _summarize_parameters(parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "parameter_count": len(parameters),
        "sensitive_parameter_count": sum(
            1 for parameter in parameters if parameter["summary"]["nonzero_variant_count"] > 0
        ),
        "move_sensitive_parameter_count": sum(
            1 for parameter in parameters if parameter["summary"]["move_diff_variant_count"] > 0
        ),
        "max_abs_score_difference": max(
            (
                float(parameter["summary"]["max_abs_score_difference"])
                for parameter in parameters
            ),
            default=0.0,
        ),
        "max_move_diff_count": max(
            (int(parameter["summary"]["max_move_diff_count"]) for parameter in parameters),
            default=0,
        ),
    }


def _summarize_blocks(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "block_count": len(blocks),
        "sensitive_block_count": sum(
            1 for block in blocks if block["summary"]["sensitive_parameter_count"] > 0
        ),
        "move_sensitive_block_count": sum(
            1 for block in blocks if block["summary"]["move_sensitive_parameter_count"] > 0
        ),
        "max_abs_score_difference": max(
            (float(block["summary"]["max_abs_score_difference"]) for block in blocks),
            default=0.0,
        ),
        "max_move_diff_count": max(
            (int(block["summary"]["max_move_diff_count"]) for block in blocks),
            default=0,
        ),
    }


def _get_path(payload: Dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        current = current[part]
    return current


def _set_path(payload: Dict[str, Any], path: str, value: Any) -> None:
    current = payload
    parts = path.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


if __name__ == "__main__":
    main()
