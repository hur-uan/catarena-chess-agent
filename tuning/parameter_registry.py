"""Tuning metadata and helpers for strategy-profile optimization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field

from tools.strategy_profile import StrategyProfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TUNING_REGISTRY_PATH = ROOT / "config/tuning_registry.json"


class ParameterSpec(BaseModel):
    path: str
    type: str = "float"
    min_value: float = Field(alias="min")
    max_value: float = Field(alias="max")
    step: float = 1.0
    frozen: bool = False

    model_config = {"populate_by_name": True}

    def normalize(self, value: Any) -> float:
        if self.max_value <= self.min_value:
            return 0.0
        numeric = float(value)
        return max(0.0, min(1.0, (numeric - self.min_value) / (self.max_value - self.min_value)))

    def denormalize(self, unit_value: float) -> Any:
        if self.max_value <= self.min_value:
            raw = self.min_value
        else:
            raw = self.min_value + max(0.0, min(1.0, unit_value)) * (
                self.max_value - self.min_value
            )
        return self.quantize(raw)

    def quantize(self, raw_value: float) -> Any:
        bounded = min(self.max_value, max(self.min_value, raw_value))
        if self.type == "bool":
            return bool(round(bounded))
        step = self.step or 1.0
        snapped = self.min_value + round((bounded - self.min_value) / step) * step
        snapped = min(self.max_value, max(self.min_value, snapped))
        if self.type == "int":
            return int(round(snapped))
        return round(float(snapped), _decimal_places(step))


class ConstraintSpec(BaseModel):
    kind: str
    left: str
    right: str
    adjust: str = "left"
    margin: float = 0.0

    def is_satisfied(self, payload: Dict[str, Any]) -> bool:
        left_value = float(_get_path(payload, self.left))
        right_value = float(_get_path(payload, self.right))
        if self.kind == "lte":
            return left_value <= right_value - self.margin + 1e-9
        if self.kind == "gte":
            return left_value >= right_value + self.margin - 1e-9
        raise ValueError(f"Unsupported constraint kind: {self.kind}")


class TuningBlock(BaseModel):
    name: str
    description: str = ""
    tuner: str = "spsa"
    mode_scope: str = "all"
    enabled: bool = False
    signal_mode: str = "line_quality"
    prescreen_set: str = ""
    prescreen_time_limit_ms: int = 0
    research_goal: str = ""
    parameters: List[ParameterSpec] = Field(default_factory=list)

    def tunable_parameters(self) -> List[ParameterSpec]:
        return [parameter for parameter in self.parameters if not parameter.frozen]


class TuningRegistry(BaseModel):
    version: int = 1
    blocks: List[TuningBlock] = Field(default_factory=list)
    constraints: List[ConstraintSpec] = Field(default_factory=list)

    def block(self, name: str) -> TuningBlock:
        for block in self.blocks:
            if block.name == name:
                return block
        raise KeyError(f"Unknown tuning block: {name}")

    def resolve_blocks(
        self,
        names: Optional[Iterable[str]] = None,
        enabled_only: bool = True,
    ) -> List[TuningBlock]:
        if names is None:
            return [block for block in self.blocks if (block.enabled or not enabled_only)]
        requested = {name.strip() for name in names if name and name.strip()}
        return [block for block in self.blocks if block.name in requested]

    def parameter_specs(self) -> Dict[str, ParameterSpec]:
        specs: Dict[str, ParameterSpec] = {}
        for block in self.blocks:
            for parameter in block.parameters:
                specs[parameter.path] = parameter
        return specs

    def block_to_unit_vector(self, profile: StrategyProfile, block: TuningBlock) -> List[float]:
        data = profile.model_dump()
        return [
            parameter.normalize(_get_path(data, parameter.path))
            for parameter in block.tunable_parameters()
        ]

    def profile_from_unit_vector(
        self,
        profile: StrategyProfile,
        block: TuningBlock,
        unit_vector: List[float],
    ) -> StrategyProfile:
        parameters = block.tunable_parameters()
        if len(parameters) != len(unit_vector):
            raise ValueError(
                f"Vector length {len(unit_vector)} does not match block {block.name} "
                f"parameter count {len(parameters)}"
            )
        payload = profile.model_dump()
        for parameter, unit_value in zip(parameters, unit_vector):
            _set_path(payload, parameter.path, parameter.denormalize(unit_value))
        constrained = self.apply_constraints(
            payload,
            active_paths={parameter.path for parameter in parameters},
        )
        return StrategyProfile.model_validate(constrained)

    def apply_constraints(
        self,
        payload: Dict[str, Any],
        active_paths: Optional[set[str]] = None,
    ) -> Dict[str, Any]:
        result = json.loads(json.dumps(payload))
        all_specs = self.parameter_specs()
        specs = (
            all_specs
            if active_paths is None
            else {path: spec for path, spec in all_specs.items() if path in active_paths}
        )
        constraints = [
            constraint
            for constraint in self.constraints
            if active_paths is None
            or constraint.left in active_paths
            or constraint.right in active_paths
        ]
        for _ in range(max(1, len(self.constraints) + 1)):
            changed = False
            for constraint in constraints:
                if constraint.is_satisfied(result):
                    continue
                left_value = float(_get_path(result, constraint.left))
                right_value = float(_get_path(result, constraint.right))
                if constraint.kind == "lte":
                    if constraint.adjust == "left":
                        _set_path(result, constraint.left, right_value - constraint.margin)
                        _project_path(result, constraint.left, all_specs)
                    else:
                        _set_path(result, constraint.right, left_value + constraint.margin)
                        _project_path(result, constraint.right, all_specs)
                elif constraint.kind == "gte":
                    if constraint.adjust == "left":
                        _set_path(result, constraint.left, right_value + constraint.margin)
                        _project_path(result, constraint.left, all_specs)
                    else:
                        _set_path(result, constraint.right, left_value - constraint.margin)
                        _project_path(result, constraint.right, all_specs)
                else:
                    raise ValueError(f"Unsupported constraint kind: {constraint.kind}")
                changed = True
            if not changed:
                break
        for path in specs:
            _project_path(result, path, specs)
        return result


def load_tuning_registry(path: Optional[Path] = None) -> TuningRegistry:
    registry_path = Path(path or DEFAULT_TUNING_REGISTRY_PATH)
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    return TuningRegistry.model_validate(payload)


def _project_path(payload: Dict[str, Any], path: str, specs: Dict[str, ParameterSpec]) -> None:
    spec = specs.get(path)
    if spec is None:
        return
    value = _get_path(payload, path)
    _set_path(payload, path, spec.quantize(float(value)))


def _get_path(payload: Dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        current = current[part]
    return current


def _set_path(payload: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = payload
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def _decimal_places(step: float) -> int:
    text = f"{step:.10f}".rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return len(text.split(".")[1])
