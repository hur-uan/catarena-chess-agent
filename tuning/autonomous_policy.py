"""Autonomous round-to-round tuning policy for CATArena integration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from tools.pipeline_metadata import FORMAL_EXECUTION_BACKEND, RUNTIME_POLICY
from tools.strategy_profile import DEFAULT_STRATEGY_PROFILE_PATH
from tuning.optimize_profile import optimize_profile
from tuning.parameter_registry import DEFAULT_TUNING_REGISTRY_PATH
from tuning.spsa import SpsaConfig


class AutonomousBlockPolicy(BaseModel):
    block_name: str
    mode: str = "hold"
    note: str = ""
    seeds: List[int] = Field(default_factory=lambda: [1, 2, 3])
    preset: str = "quick"
    iterations: int = 1
    inner_pair_count: int = 2
    acceptance_pair_count: int = 4
    time_limit_ms: int = 25
    max_plies: int = 20
    thaw_after_rounds: int = 3
    spsa_learning_rate: float = 0.15
    spsa_perturbation: float = 0.10
    spsa_stability_constant: float = 5.0
    min_effective_score_difference: float = 0.0
    focus_after_promising_rounds: int = 3


class AutonomousTuningSeedResult(BaseModel):
    seed: int
    score_difference: float = 0.0
    prescreen_score_difference: float = 0.0
    applied_change_count: int = 0
    applied_change_paths: List[str] = Field(default_factory=list)
    acceptance_prescreen_difference: float = 0.0
    acceptance_mean_score_a: float = 0.5
    sprt_decision: str = ""
    player_a_timeouts: int = 0
    player_b_timeouts: int = 0
    player_a_crashes: int = 0
    proposed_profile: Dict[str, Any] = Field(default_factory=dict)


class AutonomousTuningReport(BaseModel):
    enabled: bool = False
    action: str = "skipped"
    reason_code: str = ""
    reason: str = ""
    selected_block: str = ""
    selected_block_mode: str = ""
    selected_block_note: str = ""
    gate_cross_count: int = 0
    positive_inner_count: int = 0
    negative_inner_count: int = 0
    positive_acceptance_prescreen_count: int = 0
    negative_acceptance_prescreen_count: int = 0
    safe_seed_count: int = 0
    consecutive_similar_holds: int = 0
    chosen_seed: int = 0
    chosen_changed_paths: List[str] = Field(default_factory=list)
    promoted_strategy_profile: bool = False
    promoted_profile_path: str = ""
    archived_profile_path: str = ""
    seeds: List[AutonomousTuningSeedResult] = Field(default_factory=list)


AUTONOMOUS_BLOCK_POLICIES: List[AutonomousBlockPolicy] = [
    AutonomousBlockPolicy(
        block_name="search.history_order",
        mode="hold",
        note=(
            "TT move ordering is held after a p16 shadow retest failed to reproduce "
            "the sparse p8 positive changed seed; the only p16 gate-cross was negative."
        ),
        spsa_learning_rate=0.45,
    ),
    AutonomousBlockPolicy(
        block_name="search.mate_threshold",
        mode="hold",
        note=(
            "Broad mate-threshold search block is held after a mixed p8 signal failed "
            "to reproduce in a same-configuration repeat."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="search.mate_detection_margin",
        mode="hold",
        note=(
            "Mate detection margin is held after baseline, amplified, repeated, "
            "and step-50 p8 runs failed to produce a reproducible gate-cross."
        ),
        spsa_learning_rate=0.35,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.03,
    ),
    AutonomousBlockPolicy(
        block_name="eval.mobility_weight",
        mode="hold",
        note=(
            "Mobility weight is held at the promoted 0.85 value after the 0.85 -> 0.7 "
            "p16 revisit produced acceptance-unconfirmed and repeated rank-regression "
            "signals."
        ),
        spsa_learning_rate=0.30,
        spsa_perturbation=0.20,
        min_effective_score_difference=0.02,
    ),
    AutonomousBlockPolicy(
        block_name="eval.king_safety_weight",
        mode="hold",
        note=(
            "King-safety evaluation weight is held after the updated-policy p8 retest "
            "froze on repeated negative inner signal."
        ),
        spsa_learning_rate=0.30,
        spsa_perturbation=0.20,
        min_effective_score_difference=0.02,
    ),
    AutonomousBlockPolicy(
        block_name="eval.piece_activity_weight",
        mode="hold",
        note=(
            "Piece-activity evaluation weight is held after the isolated 0.85 -> 0.8 "
            "candidate produced a p16 rank regression."
        ),
        spsa_learning_rate=0.60,
        spsa_perturbation=0.20,
        min_effective_score_difference=0.02,
    ),
    AutonomousBlockPolicy(
        block_name="eval.pawn_structure_weight",
        mode="hold",
        note=(
            "Pawn-structure evaluation weight is held after p8 produced only "
            "shadow/acceptance-unconfirmed signal with a very small score difference."
        ),
        spsa_learning_rate=0.60,
        spsa_perturbation=0.20,
        min_effective_score_difference=0.02,
    ),
    AutonomousBlockPolicy(
        block_name="eval.weights",
        mode="hold",
        note=(
            "Broad eval weights are held after the first promotion succeeded but the "
            "second promotion-confirm degraded from candidate-ready to shadow-ready."
        ),
        spsa_learning_rate=0.30,
        spsa_perturbation=0.20,
        min_effective_score_difference=0.02,
    ),
    AutonomousBlockPolicy(
        block_name="eval.weights_no_mobility",
        mode="hold",
        note=(
            "Eval weights excluding mobility are held after p8 and p16 stayed shadow-ready "
            "with a stable negative seed; split into single-parameter tests."
        ),
        spsa_learning_rate=0.30,
        spsa_perturbation=0.20,
        min_effective_score_difference=0.02,
    ),
    AutonomousBlockPolicy(
        block_name="eval.material_weight",
        mode="hold",
        note=(
            "Material evaluation weight is held after a learning-rate-amplified p8 "
            "revisit still produced no gate-cross or changed path."
        ),
        spsa_learning_rate=0.60,
        spsa_perturbation=0.20,
        min_effective_score_difference=0.02,
    ),
    AutonomousBlockPolicy(
        block_name="piece_values.pawn",
        mode="hold",
        note=(
            "Pawn value is held after p8 produced a real 100 to 110 candidate with "
            "repeated negative inner/static-prescreen signal and rank regression."
        ),
        spsa_learning_rate=20.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="piece_values.knight",
        mode="hold",
        note=(
            "Knight value is held after p8 produced real changed paths but repeated "
            "negative inner and static-prescreen signal."
        ),
        spsa_learning_rate=20.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="piece_values.bishop",
        mode="hold",
        note=(
            "Bishop value is held after p8 repeated positive inner/static signals but "
            "p16 repeated rank=2 and one regression-after-patch classification."
        ),
        spsa_learning_rate=20.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="piece_values.rook",
        mode="hold",
        note=(
            "Rook value is held after p8 produced no stable gate-cross and one "
            "rank regression, with zero static and acceptance prescreen support."
        ),
        spsa_learning_rate=20.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="piece_values.queen",
        mode="hold",
        note=(
            "Queen value is held after p8 produced no gate-cross, no changed paths, "
            "zero static/acceptance prescreen signal, and one rank regression."
        ),
        spsa_learning_rate=20.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="piece_values",
        mode="hold",
        note=(
            "Broad piece values are held after p8 produced no gate-cross, no changed "
            "paths, and all-zero static/acceptance signals."
        ),
        spsa_learning_rate=20.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="phase",
        mode="hold",
        note=(
            "Broad phase thresholds are held after p8 produced no gate-cross, no "
            "changed paths, and all-zero static/acceptance prescreen signal."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="phase.opening_fullmove_limit",
        mode="hold",
        note=(
            "Opening phase cutoff is held after p8 produced no gate-cross, no changed "
            "paths, and zero static/acceptance prescreen signal."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="phase.endgame_non_king_piece_threshold",
        mode="hold",
        note=(
            "Endgame phase cutoff is held after p8 produced no gate-cross, no changed "
            "paths, and zero static/acceptance prescreen signal."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="eval.constants",
        mode="hold",
        note=(
            "Broad eval constants are held after p8 produced no gate-cross, no "
            "changed paths, all-zero static/acceptance signals, rank regression, "
            "and one optimizer acceptance timeout record."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="eval.draw_score",
        mode="hold",
        note=(
            "Draw terminal score is held after p8 produced no gate-cross, no changed "
            "paths, and zero static/acceptance prescreen signal."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="eval.missing_king_penalty",
        mode="hold",
        note=(
            "Missing-king penalty is held after p8 produced no gate-cross, no changed "
            "paths, and zero static/acceptance prescreen signal."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="eval.mate_score",
        mode="hold",
        note=(
            "Mate score is held after p8 produced no gate-cross, no changed paths, "
            "and zero static/acceptance prescreen signal."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="search.root_mate_stop_distance",
        mode="hold",
        note=(
            "Root mate stop distance is held after conservative p8 retest produced "
            "no gate-cross, no changed paths, and only small mixed score noise."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="search.history_bonus_scale",
        mode="hold",
        note=(
            "History bonus scale is held after conservative p8 retest produced "
            "no gate-cross, no changed paths, and only tiny score noise."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="search.history_bonus_power",
        mode="hold",
        note=(
            "History bonus power is held after conservative p8 retest produced "
            "no gate-cross, no changed paths, and small negative score noise."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="search.depth_time",
        mode="hold",
        note=(
            "Depth/time controls are held after baseline, perturbation-amplified, "
            "and learning-rate-amplified p8 runs all failed to produce a gate-cross."
        ),
        spsa_learning_rate=0.50,
        spsa_perturbation=0.30,
    ),
    AutonomousBlockPolicy(
        block_name="search.quiescence_depth",
        mode="hold",
        note=(
            "Quiescence depth remains held by final shutdown protocol; no further "
            "internal self-play blocks are active."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="search.min_time_margin_ms",
        mode="hold",
        note=(
            "Minimum time margin is held after p8 produced repeated real changes "
            "with stable negative line-quality signal and one rank regression."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="search.default_depth",
        mode="hold",
        note=(
            "Default search depth is held after p8 produced no gate-cross, no changed "
            "paths, and one outer rank regression."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="search.max_depth",
        mode="hold",
        note=(
            "Maximum search depth is held after p8 produced no gate-cross, no changed "
            "paths, and negative acceptance-prescreen noise."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.development",
        mode="hold",
        note=(
            "Development ordering is held after baseline and perturbation-amplified "
            "p8 runs both produced no gate-cross or applied change."
        ),
        spsa_learning_rate=0.60,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.05,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.early_rook_penalty",
        mode="hold",
        note=(
            "Early rook penalty is held after p8 retest produced no gate-cross, "
            "no changed paths, and all-zero line-quality signals."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.minor_development_bonus",
        mode="hold",
        note=(
            "Minor development bonus is held at 21 after the updated-policy p8 "
            "candidate 21 to 12 failed stable p16 validation."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.center_pawn_development_bonus",
        mode="hold",
        note=(
            "Center pawn development bonus is held after p8 retest produced no "
            "gate-cross, no changed paths, and all-zero line-quality signals."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.early_queen_penalty",
        mode="hold",
        note=(
            "Early queen penalty is held after p8 retest produced no gate-cross, "
            "no changed paths, and all-zero line-quality signals."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.castling_bonus",
        mode="hold",
        note=(
            "Castling bonus is held after p8 retest produced no gate-cross, no changed "
            "paths, and one no-change rank regression."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.center_bonus",
        mode="hold",
        note=(
            "Center ordering bonus is held after p8 retest produced two negative "
            "rounds and one shadow-ready round with unstable direction."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.extended_center_bonus",
        mode="hold",
        note=(
            "Extended center ordering bonus is held at 10 after promotion-confirm "
            "and post-promotion p16 stability checks passed."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.check_bonus",
        mode="hold",
        note=(
            "Check ordering bonus is held after p8 retest produced no gate-cross, "
            "no changed paths, and one rank regression."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.tactical",
        mode="hold",
        note=(
            "Full tactical ordering is held after the p8 revisit produced repeated "
            "negative direction on the only seed with applied changes."
        ),
        spsa_learning_rate=0.60,
        spsa_perturbation=0.35,
        min_effective_score_difference=0.03,
    ),
    AutonomousBlockPolicy(
        block_name="piece_activity",
        mode="hold",
        note=(
            "Broad piece-activity tuning is held after repeated direction-unstable "
            "self-play rounds; focused center-bonus validation is used instead."
        ),
        spsa_learning_rate=0.70,
        spsa_perturbation=0.40,
        min_effective_score_difference=0.005,
    ),
    AutonomousBlockPolicy(
        block_name="piece_activity.center_bonus",
        mode="hold",
        note=(
            "Center activity is held at the promoted value after p8 cross-checks rejected "
            "the next lower candidate while preserving the promoted baseline."
        ),
        spsa_learning_rate=0.85,
        spsa_perturbation=0.20,
        min_effective_score_difference=0.05,
    ),
    AutonomousBlockPolicy(
        block_name="piece_activity.extended_center_bonus",
        mode="hold",
        note=(
            "Extended-center activity is held after repeated promotion-confirm rounds "
            "pushed it to the lower bound under stable p8 and p16 evidence."
        ),
        spsa_learning_rate=0.75,
        spsa_perturbation=0.20,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="piece_activity.minor_rank_bonus_weight",
        mode="hold",
        note=(
            "Minor-piece rank activity is held after an amplified single-parameter "
            "candidate crossed the gate but failed feedback prescreen in p8 repeats."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="piece_activity.minor_center_distance_penalty",
        mode="hold",
        note=(
            "Minor-piece center-distance penalty is held after a real single-parameter "
            "candidate crossed the gate but failed feedback prescreen in p8 repeats."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="pawn_structure",
        mode="hold",
        note=(
            "Broad pawn structure is held after p8 produced real changed paths but "
            "repeated negative inner and acceptance-prescreen signals."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="pawn_structure.advance_bonus_per_rank",
        mode="hold",
        note=(
            "Pawn advance bonus is held after the real 3 -> 4 candidate produced "
            "repeated negative inner, acceptance, and feedback signals in p8."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="pawn_structure.isolated_penalty",
        mode="hold",
        note=(
            "Isolated-pawn penalty is held after baseline and amplified p8 runs both "
            "produced zero score gradient and no discrete gate-cross."
        ),
        spsa_learning_rate=12.00,
        spsa_perturbation=1.00,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="pawn_structure.doubled_penalty",
        mode="hold",
        note=(
            "Doubled-pawn penalty is held after baseline and amplified p8 runs both "
            "produced zero score gradient and no discrete gate-cross."
        ),
        spsa_learning_rate=12.00,
        spsa_perturbation=1.00,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="king_safety",
        mode="hold",
        note=(
            "Broad king safety is held after p8 produced real changed paths but "
            "repeated negative inner/static-prescreen signals and froze."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="king_safety.attacked_ring_penalty",
        mode="hold",
        note=(
            "Attacked king-ring penalty is held after repeated p8, p16, and "
            "promotion-confirm evidence pushed it to the lower bound."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="king_safety.pawn_shield_bonus",
        mode="hold",
        note=(
            "Pawn-shield bonus is held after p8 produced a real changed path but "
            "repeated negative inner signal."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="king_safety.piece_shield_bonus",
        mode="hold",
        note=(
            "Piece-shield bonus is held after p8 produced repeated negative inner, "
            "acceptance-prescreen, and feedback-prescreen signals."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="king_safety.attacked_king_penalty",
        mode="hold",
        note=(
            "Attacked-king penalty is held after baseline, amplified, repeated, and "
            "step-1 p8 runs failed to produce a reproducible gate-cross."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=1.00,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.promotion_bonus",
        mode="hold",
        note=(
            "Promotion ordering bonus is held after p8 retest produced no gate-cross, "
            "no changed paths, and one rank regression."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.capture_base_bonus",
        mode="hold",
        note=(
            "Capture base ordering bonus is held after updated-policy p8 retest "
            "produced one negative changed seed and otherwise no effective movement."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.capture_victim_multiplier",
        mode="hold",
        note=(
            "Capture victim ordering multiplier is held at 10 after updated-policy "
            "p8 retest produced no gate-cross, no changed paths, and all-zero signals."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
    AutonomousBlockPolicy(
        block_name="move_ordering.capture_attacker_penalty",
        mode="hold",
        note=(
            "Capture attacker penalty is held after updated-policy p8 retest "
            "reproduced a negative changed seed and direction instability."
        ),
        spsa_learning_rate=8.00,
        spsa_perturbation=0.50,
        min_effective_score_difference=0.04,
    ),
]

STABILITY_FIRST_FAILURES = {"interface_error", "illegal_move", "timeout"}
FREEZE_REASON_CODES = {"direction_unstable", "negative_signal"}
MAX_SHADOW_NEGATIVE_SEEDS = 3


def run_autonomous_tuning_round(
    *,
    round_id: str,
    failure_type: str,
    memory_records: List[Dict[str, Any]],
    strategy_profile_path: Path = DEFAULT_STRATEGY_PROFILE_PATH,
    registry_path: Path = DEFAULT_TUNING_REGISTRY_PATH,
    match_timeout_slack_ms: int = 5,
    match_timeout_slack_ratio: float = 0.20,
    selected_block: Optional[str] = None,
    promote: bool = False,
) -> AutonomousTuningReport:
    if failure_type in STABILITY_FIRST_FAILURES:
        return AutonomousTuningReport(
            action="skipped",
            reason_code="stability_first",
            reason="Reliability issues take priority; autonomous parameter tuning is disabled.",
        )

    policy = _select_active_policy(memory_records, selected_block=selected_block)
    if policy is None:
        return AutonomousTuningReport(
            action="skipped",
            reason_code="no_active_block",
            reason=(
                "No online-ready tuning block is currently available; keep using offline "
                "research until a block is unfrozen or newly promoted to active."
            ),
        )

    report = AutonomousTuningReport(
        enabled=True,
        selected_block=policy.block_name,
        selected_block_mode=policy.mode,
        selected_block_note=policy.note,
    )
    for seed in policy.seeds:
        result = optimize_profile(
            strategy_profile_path=Path(strategy_profile_path),
            registry_path=Path(registry_path),
            block_names=[policy.block_name],
            preset=policy.preset,
            iterations=policy.iterations,
            inner_pair_count=policy.inner_pair_count,
            acceptance_pair_count=policy.acceptance_pair_count,
            time_limit_ms=policy.time_limit_ms,
            max_plies=policy.max_plies,
            match_timeout_slack_ms=match_timeout_slack_ms,
            match_timeout_slack_ratio=match_timeout_slack_ratio,
            random_seed=seed,
            spsa_config=SpsaConfig(
                learning_rate=policy.spsa_learning_rate,
                perturbation=policy.spsa_perturbation,
                stability_constant=policy.spsa_stability_constant,
                min_effective_score_difference=policy.min_effective_score_difference,
            ),
            promote=False,
        )
        block_report = result.blocks_run[0]
        iteration = block_report.spsa_iterations[-1]
        acceptance_match = block_report.acceptance_match
        acceptance_prescreen = block_report.acceptance_prescreen
        seed_result = AutonomousTuningSeedResult(
            seed=seed,
            score_difference=iteration.score_difference,
            prescreen_score_difference=iteration.prescreen_score_difference,
            applied_change_count=iteration.applied_change_count,
            applied_change_paths=iteration.applied_change_paths,
            acceptance_prescreen_difference=(
                acceptance_prescreen.score_difference if acceptance_prescreen is not None else 0.0
            ),
            acceptance_mean_score_a=(
                acceptance_match.mean_score_a if acceptance_match is not None else 0.5
            ),
            sprt_decision=(
                block_report.sprt_result.decision.value
                if block_report.sprt_result is not None
                else ""
            ),
            player_a_timeouts=(
                acceptance_match.player_a_timeouts if acceptance_match is not None else 0
            ),
            player_b_timeouts=(
                acceptance_match.player_b_timeouts if acceptance_match is not None else 0
            ),
            player_a_crashes=(
                acceptance_match.player_a_crashes if acceptance_match is not None else 0
            ),
            proposed_profile=block_report.proposed_profile,
        )
        report.seeds.append(seed_result)

    _summarize_seed_results(report)
    _apply_policy_decision(
        report=report,
        policy=policy,
        memory_records=memory_records,
        strategy_profile_path=Path(strategy_profile_path),
        round_id=round_id,
        promote=promote,
    )
    return report


def _select_active_policy(
    memory_records: List[Dict[str, Any]],
    selected_block: Optional[str] = None,
) -> Optional[AutonomousBlockPolicy]:
    active_policies = [policy for policy in AUTONOMOUS_BLOCK_POLICIES if policy.mode == "active"]
    available = [
        policy for policy in active_policies if not _is_block_frozen(memory_records, policy)
    ]
    if not available:
        return None

    requested_block = (selected_block or "").strip()
    if requested_block:
        for policy in available:
            if policy.block_name == requested_block:
                return policy
        return None

    active_names = [policy.block_name for policy in active_policies]
    available_by_name = {policy.block_name: policy for policy in available}
    focused = _select_promising_recent_policy(memory_records, available_by_name)
    if focused is not None:
        return focused

    last_selected = _last_selected_active_block(memory_records, active_names)
    if last_selected is None:
        return available[0]

    last_index = active_names.index(last_selected)
    for offset in range(1, len(active_names) + 1):
        name = active_names[(last_index + offset) % len(active_names)]
        if name in available_by_name:
            return available_by_name[name]
    return None


def _select_promising_recent_policy(
    memory_records: List[Dict[str, Any]],
    available_by_name: Dict[str, AutonomousBlockPolicy],
) -> Optional[AutonomousBlockPolicy]:
    for record in reversed([record for record in memory_records if _same_runtime_policy(record)]):
        tuning = _memory_tuning(record)
        selected = str(tuning.get("selected_block", ""))
        policy = available_by_name.get(selected)
        if policy is None:
            return None
        if not _is_promising_hold(tuning):
            return None
        recent_same_block_count = _recent_same_block_count(memory_records, selected)
        if recent_same_block_count >= policy.focus_after_promising_rounds:
            return None
        return policy
    return None


def _is_promising_hold(tuning: Dict[str, Any]) -> bool:
    return (
        str(tuning.get("action", "")) in {"hold", "shadow_ready"}
        and str(tuning.get("reason_code", "")) in {"acceptance_unconfirmed", "shadow_ready"}
        and int(tuning.get("gate_cross_count", 0) or 0) > 0
        and int(tuning.get("positive_inner_count", 0) or 0)
        >= int(tuning.get("negative_inner_count", 0) or 0)
    )


def _recent_same_block_count(memory_records: List[Dict[str, Any]], selected_block: str) -> int:
    count = 0
    for record in reversed([record for record in memory_records if _same_runtime_policy(record)]):
        tuning = _memory_tuning(record)
        if str(tuning.get("selected_block", "")) != selected_block:
            break
        count += 1
    return count


def _last_selected_active_block(
    memory_records: List[Dict[str, Any]],
    active_names: List[str],
) -> Optional[str]:
    active_name_set = set(active_names)
    for record in reversed([record for record in memory_records if _same_runtime_policy(record)]):
        selected = str(_memory_tuning(record).get("selected_block", ""))
        if selected in active_name_set:
            return selected
    return None


def _is_block_frozen(
    memory_records: List[Dict[str, Any]],
    policy: AutonomousBlockPolicy,
) -> bool:
    recent: List[tuple[str, str]] = []
    for tuning in reversed(_effective_block_history(memory_records, policy)):
        action = str(tuning.get("action", ""))
        reason_code = str(tuning.get("reason_code", ""))
        if action == "promote":
            return False
        recent.append((action, reason_code))
        if len(recent) >= 3:
            break
    if not recent:
        return False
    latest_action, latest_reason = recent[0]
    if latest_action == "freeze" and latest_reason in FREEZE_REASON_CODES:
        return True
    if len(recent) < 3:
        return False
    reasons = {reason for _, reason in recent}
    return (
        len(reasons) == 1
        and latest_reason in FREEZE_REASON_CODES
        and all(action in {"hold", "freeze"} for action, _ in recent)
    )


def _effective_block_history(
    memory_records: List[Dict[str, Any]],
    policy: AutonomousBlockPolicy,
) -> List[Dict[str, Any]]:
    start_index = 0
    last_promote_index = -1
    last_freeze_index = -1
    current_records = [record for record in memory_records if _same_runtime_policy(record)]
    for index, record in enumerate(current_records):
        tuning = _memory_tuning(record)
        if tuning.get("selected_block") != policy.block_name:
            continue
        action = str(tuning.get("action", ""))
        if action == "promote":
            last_promote_index = index
        elif action == "freeze":
            last_freeze_index = index
    if last_promote_index >= 0:
        start_index = last_promote_index + 1
    if (
        last_freeze_index >= 0
        and (len(current_records) - last_freeze_index - 1) >= policy.thaw_after_rounds
    ):
        start_index = max(start_index, last_freeze_index + 1)
    history: List[Dict[str, Any]] = []
    for record in current_records[start_index:]:
        tuning = _memory_tuning(record)
        if tuning.get("selected_block") == policy.block_name:
            history.append(tuning)
    return history


def _same_runtime_policy(record: Dict[str, Any]) -> bool:
    return (
        str(record.get("runtime_policy", "")).strip() == RUNTIME_POLICY
        and str(record.get("formal_execution_backend", "")).strip() == FORMAL_EXECUTION_BACKEND
    )


def _summarize_seed_results(report: AutonomousTuningReport) -> None:
    report.gate_cross_count = sum(1 for item in report.seeds if item.applied_change_count > 0)
    report.positive_inner_count = sum(1 for item in report.seeds if item.score_difference > 0.0)
    report.negative_inner_count = sum(1 for item in report.seeds if item.score_difference < 0.0)
    report.positive_acceptance_prescreen_count = sum(
        1 for item in report.seeds if item.acceptance_prescreen_difference > 0.0
    )
    report.negative_acceptance_prescreen_count = sum(
        1 for item in report.seeds if item.acceptance_prescreen_difference < 0.0
    )
    report.safe_seed_count = sum(1 for item in report.seeds if _seed_is_safe(item))


def _apply_policy_decision(
    *,
    report: AutonomousTuningReport,
    policy: AutonomousBlockPolicy,
    memory_records: List[Dict[str, Any]],
    strategy_profile_path: Path,
    round_id: str,
    promote: bool,
) -> None:
    promotable = [
        item
        for item in report.seeds
        if item.score_difference > 0.0
        and item.applied_change_count > 0
        and item.acceptance_prescreen_difference >= 0.0
        and item.acceptance_mean_score_a >= 0.5
        and _seed_is_safe(item)
    ]
    shadow_promotable = [
        item
        for item in promotable
        if item.prescreen_score_difference >= 0.0
    ]
    if report.gate_cross_count == 0:
        report.reason_code = "no_gate_cross"
        report.reason = (
            "Autonomous tuning produced no real discrete parameter change; keep this block "
            "under observation instead of promoting it."
        )
        _finalize_hold_or_freeze(report, memory_records, policy)
        return
    if report.negative_inner_count >= 2 and report.positive_inner_count == 0:
        report.reason_code = "negative_signal"
        report.reason = (
            "Most seeds point in a negative direction for this block; do not auto-promote "
            "the candidate profile."
        )
        _finalize_hold_or_freeze(report, memory_records, policy)
        return
    if report.positive_inner_count == 0 or report.negative_inner_count > 0:
        if _mark_shadow_ready_if_promising(report, shadow_promotable):
            return
        report.reason_code = "direction_unstable"
        report.reason = (
            "Seed-to-seed direction is not stable enough for autonomous promotion; keep "
            "the block active but unpromoted."
        )
        _finalize_hold_or_freeze(report, memory_records, policy)
        return
    if len(promotable) < 2 or report.safe_seed_count < len(report.seeds):
        if _mark_shadow_ready_if_promising(report, shadow_promotable):
            return
        report.reason_code = "acceptance_unconfirmed"
        report.reason = (
            "At least one seed crossed the discrete gate, but acceptance evidence is still "
            "too weak for autonomous promotion."
        )
        report.action = "hold"
        return

    chosen = max(
        promotable,
        key=lambda item: (
            item.score_difference,
            item.acceptance_prescreen_difference,
            item.acceptance_mean_score_a,
            item.applied_change_count,
        ),
    )
    report.reason_code = "candidate_ready"
    report.reason = (
        "The selected block crossed the discrete gate with stable positive direction and "
        "safe acceptance metrics."
    )
    report.chosen_seed = chosen.seed
    report.chosen_changed_paths = list(chosen.applied_change_paths)
    if promote:
        archive_path = _promote_strategy_profile(
            chosen.proposed_profile,
            strategy_profile_path,
            round_id,
        )
        report.action = "promote"
        report.promoted_strategy_profile = True
        report.promoted_profile_path = str(strategy_profile_path)
        report.archived_profile_path = str(archive_path) if archive_path is not None else ""
        return
    report.action = "ready"


def _mark_shadow_ready_if_promising(
    report: AutonomousTuningReport,
    shadow_promotable: List[AutonomousTuningSeedResult],
) -> bool:
    if (
        not shadow_promotable
        or report.negative_inner_count > MAX_SHADOW_NEGATIVE_SEEDS
        or report.safe_seed_count != len(report.seeds)
    ):
        return False
    chosen = max(
        shadow_promotable,
        key=lambda item: (
            item.score_difference,
            item.prescreen_score_difference,
            item.acceptance_prescreen_difference,
            item.acceptance_mean_score_a,
            item.applied_change_count,
        ),
    )
    report.action = "shadow_ready"
    report.reason_code = "shadow_ready"
    report.reason = (
        "At least one seed produced a real positive candidate with non-negative prescreen "
        "and acceptance evidence, but the full multi-seed promotion standard was not met. "
        "Keep the candidate for larger shadow confirmation instead of writing it to the "
        "formal profile."
    )
    report.chosen_seed = chosen.seed
    report.chosen_changed_paths = list(chosen.applied_change_paths)
    return True


def _finalize_hold_or_freeze(
    report: AutonomousTuningReport,
    memory_records: List[Dict[str, Any]],
    policy: AutonomousBlockPolicy,
) -> None:
    report.consecutive_similar_holds = _consecutive_reason_count(
        memory_records,
        policy,
        report.reason_code,
    )
    if report.reason_code in FREEZE_REASON_CODES and report.consecutive_similar_holds >= 2:
        report.action = "freeze"
        report.reason = (
            f"{report.reason} This same pattern has repeated across consecutive rounds, "
            "so the block is frozen for autonomous online tuning."
        )
        return
    report.action = "hold"


def _consecutive_reason_count(
    memory_records: List[Dict[str, Any]],
    policy: AutonomousBlockPolicy,
    reason_code: str,
) -> int:
    count = 0
    for tuning in reversed(_effective_block_history(memory_records, policy)):
        if tuning.get("action") == "promote":
            break
        if tuning.get("reason_code") != reason_code:
            break
        if tuning.get("action") not in {"hold", "freeze"}:
            break
        count += 1
    return count


def _seed_is_safe(seed: AutonomousTuningSeedResult) -> bool:
    if seed.player_a_crashes > 0:
        return False
    return seed.player_a_timeouts <= seed.player_b_timeouts + max(1, seed.player_b_timeouts)


def _memory_tuning(record: Dict[str, Any]) -> Dict[str, Any]:
    tuning = record.get("tuning")
    return tuning if isinstance(tuning, dict) else {}


def _promote_strategy_profile(
    proposed_profile: Dict[str, Any],
    strategy_profile_path: Path,
    round_id: str,
) -> Optional[Path]:
    if not proposed_profile:
        return None
    strategy_profile_path = Path(strategy_profile_path)
    strategy_profile_path.parent.mkdir(parents=True, exist_ok=True)
    archive_dir = strategy_profile_path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / (
        f"{strategy_profile_path.stem}_{round_id}{strategy_profile_path.suffix}"
    )
    if strategy_profile_path.exists():
        shutil.copy2(strategy_profile_path, archive_path)
    strategy_profile_path.write_text(
        json.dumps(proposed_profile, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return archive_path
