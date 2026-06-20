from tools.strategy_profile import StrategyProfile
from tuning.parameter_registry import load_tuning_registry


def test_tuning_registry_loads_and_exposes_enabled_blocks():
    registry = load_tuning_registry()
    blocks = registry.resolve_blocks()
    names = {block.name for block in blocks}
    assert not names
    assert "search.quiescence_depth" not in names
    assert "search.history_order" not in names
    assert "move_ordering.check_bonus" not in names
    assert "move_ordering.promotion_bonus" not in names
    assert "move_ordering.castling_bonus" not in names
    assert "move_ordering.center_bonus" not in names
    assert "move_ordering.center_pawn_development_bonus" not in names
    assert "move_ordering.early_rook_penalty" not in names
    assert "move_ordering.early_queen_penalty" not in names
    assert "move_ordering.capture_attacker_penalty" not in names
    assert "move_ordering.minor_development_bonus" not in names
    assert "move_ordering.capture_base_bonus" not in names
    assert "move_ordering.extended_center_bonus" not in names
    assert "move_ordering.capture_victim_multiplier" not in names
    assert "search.history_bonus_scale" not in names
    assert "search.history_bonus_power" not in names
    assert "search.root_mate_stop_distance" not in names
    assert "eval.material_weight" not in names
    assert "eval.king_safety_weight" not in names
    assert "eval.piece_activity_weight" not in names
    assert "eval.pawn_structure_weight" not in names
    assert "eval.weights" not in names
    assert "eval.weights_no_mobility" not in names
    assert "search.depth_time" not in names
    assert "external_engine.switch" not in names


def test_tuning_registry_exposes_signal_modes():
    registry = load_tuning_registry()
    assert registry.block("eval.weights").signal_mode == "static_eval"
    assert registry.block("eval.weights_no_mobility").signal_mode == "static_eval"
    assert registry.block("eval.material_weight").signal_mode == "static_eval"
    assert registry.block("eval.mobility_weight").signal_mode == "static_eval"
    assert registry.block("eval.king_safety_weight").signal_mode == "static_eval"
    assert registry.block("eval.piece_activity_weight").signal_mode == "static_eval"
    assert registry.block("eval.pawn_structure_weight").signal_mode == "static_eval"
    assert registry.block("piece_activity.extended_center_bonus").signal_mode == "static_eval"
    assert registry.block("piece_activity.minor_rank_bonus_weight").signal_mode == "static_eval"
    assert (
        registry.block("piece_activity.minor_center_distance_penalty").signal_mode
        == "static_eval"
    )
    assert registry.block("pawn_structure.advance_bonus_per_rank").signal_mode == "static_eval"
    assert registry.block("pawn_structure").signal_mode == "static_eval"
    assert registry.block("pawn_structure.isolated_penalty").signal_mode == "static_eval"
    assert registry.block("pawn_structure.doubled_penalty").signal_mode == "static_eval"
    assert registry.block("king_safety").signal_mode == "static_eval"
    assert registry.block("king_safety.attacked_ring_penalty").signal_mode == "static_eval"
    assert registry.block("king_safety.attacked_king_penalty").signal_mode == "static_eval"
    assert registry.block("king_safety.pawn_shield_bonus").signal_mode == "static_eval"
    assert registry.block("king_safety.piece_shield_bonus").signal_mode == "static_eval"
    assert registry.block("piece_values.knight").signal_mode == "static_eval"
    assert registry.block("piece_values.pawn").signal_mode == "static_eval"
    assert registry.block("piece_values").signal_mode == "static_eval"
    assert registry.block("piece_values.bishop").signal_mode == "static_eval"
    assert registry.block("piece_values.rook").signal_mode == "static_eval"
    assert registry.block("piece_values.queen").signal_mode == "static_eval"
    assert registry.block("phase").signal_mode == "static_eval"
    assert registry.block("phase.opening_fullmove_limit").signal_mode == "static_eval"
    assert registry.block("phase.endgame_non_king_piece_threshold").signal_mode == "static_eval"
    assert registry.block("eval.constants").signal_mode == "static_eval"
    assert registry.block("eval.draw_score").signal_mode == "static_eval"
    assert registry.block("eval.missing_king_penalty").signal_mode == "static_eval"
    assert registry.block("eval.mate_score").signal_mode == "static_eval"
    assert registry.block("search.depth_time").signal_mode == "line_quality"
    assert registry.block("search.root_mate_stop_distance").signal_mode == "search_behavior"
    assert registry.block("search.history_bonus_scale").signal_mode == "search_behavior"
    assert registry.block("search.history_bonus_power").signal_mode == "search_behavior"
    assert registry.block("search.mate_threshold").signal_mode == "line_quality"
    assert registry.block("search.quiescence_depth").signal_mode == "line_quality"
    assert registry.block("search.min_time_margin_ms").signal_mode == "line_quality"
    assert registry.block("search.default_depth").signal_mode == "line_quality"
    assert registry.block("search.max_depth").signal_mode == "line_quality"
    assert registry.block("search.mate_detection_margin").signal_mode == "line_quality"
    assert registry.block("search.history_order").signal_mode == "search_behavior"
    assert registry.block("move_ordering.early_rook_penalty").signal_mode == "line_quality"
    assert registry.block("move_ordering.minor_development_bonus").signal_mode == "line_quality"
    assert (
        registry.block("move_ordering.center_pawn_development_bonus").signal_mode
        == "line_quality"
    )
    assert registry.block("move_ordering.early_queen_penalty").signal_mode == "line_quality"
    assert registry.block("move_ordering.castling_bonus").signal_mode == "line_quality"
    assert registry.block("move_ordering.center_bonus").signal_mode == "line_quality"
    assert registry.block("move_ordering.extended_center_bonus").signal_mode == "line_quality"
    assert registry.block("move_ordering.check_bonus").signal_mode == "line_quality"
    assert registry.block("move_ordering.promotion_bonus").signal_mode == "line_quality"
    assert registry.block("move_ordering.capture_base_bonus").signal_mode == "line_quality"
    assert registry.block("move_ordering.capture_victim_multiplier").signal_mode == "line_quality"
    assert registry.block("move_ordering.capture_attacker_penalty").signal_mode == "line_quality"
    assert registry.block("search.depth_time").prescreen_set == "search.depth_time"
    assert registry.block("search.mate_threshold").prescreen_set == "search.depth_time"
    assert registry.block("search.quiescence_depth").prescreen_set == "search.depth_time"
    assert registry.block("search.min_time_margin_ms").prescreen_set == "search.depth_time"
    assert registry.block("search.default_depth").prescreen_set == "search.depth_time"
    assert registry.block("search.max_depth").prescreen_set == "search.depth_time"
    assert registry.block("eval.weights_no_mobility").prescreen_set == "eval.weights"
    assert registry.block("search.history_bonus_scale").prescreen_set == "search.history_order"
    assert registry.block("search.history_bonus_power").prescreen_set == "search.history_order"
    assert (
        registry.block("move_ordering.early_rook_penalty").prescreen_set
        == "move_ordering.development"
    )
    assert (
        registry.block("move_ordering.minor_development_bonus").prescreen_set
        == "move_ordering.development"
    )
    assert (
        registry.block("move_ordering.center_pawn_development_bonus").prescreen_set
        == "move_ordering.development"
    )
    assert (
        registry.block("move_ordering.early_queen_penalty").prescreen_set
        == "move_ordering.development"
    )
    assert registry.block("move_ordering.castling_bonus").prescreen_set == "move_ordering.tactical"
    assert registry.block("move_ordering.center_bonus").prescreen_set == "move_ordering.development"
    assert (
        registry.block("move_ordering.extended_center_bonus").prescreen_set
        == "move_ordering.development"
    )
    assert registry.block("move_ordering.check_bonus").prescreen_set == "move_ordering.tactical"
    assert registry.block("move_ordering.promotion_bonus").prescreen_set == "move_ordering.tactical"
    assert (
        registry.block("move_ordering.capture_base_bonus").prescreen_set
        == "move_ordering.tactical"
    )
    assert (
        registry.block("move_ordering.capture_victim_multiplier").prescreen_set
        == "move_ordering.tactical"
    )
    assert (
        registry.block("move_ordering.capture_attacker_penalty").prescreen_set
        == "move_ordering.tactical"
    )
    assert registry.block("eval.material_weight").prescreen_set == "eval.weights"
    assert registry.block("piece_values.pawn").prescreen_set == "piece_values"
    assert registry.block("piece_values").prescreen_set == "piece_values"
    assert registry.block("pawn_structure").prescreen_set == "pawn_structure"
    assert registry.block("king_safety").prescreen_set == "king_safety"
    assert registry.block("phase").prescreen_set == "phase"
    assert registry.block("eval.constants").prescreen_set == "eval.constants"
    assert registry.block("search.history_order").prescreen_time_limit_ms == 70
    assert "forcing lines" in registry.block("search.depth_time").research_goal.lower()


def test_tuning_registry_applies_constraints_and_quantization():
    registry = load_tuning_registry()
    block = registry.block("search.depth_time")
    profile = StrategyProfile()
    tuned = registry.profile_from_unit_vector(profile, block, [1.0, 0.0, 0.0, 1.0])
    assert tuned.search.default_depth <= tuned.search.max_depth
    assert tuned.search.quiescence_depth >= 4


def test_tuning_registry_respects_center_and_shield_constraints():
    registry = load_tuning_registry()
    payload = StrategyProfile().model_dump()
    payload["piece_activity"]["extended_center_bonus"] = 50
    payload["piece_activity"]["center_bonus"] = 10
    payload["king_safety"]["piece_shield_bonus"] = 9
    payload["king_safety"]["pawn_shield_bonus"] = 2
    constrained = registry.apply_constraints(payload)
    assert constrained["piece_activity"]["extended_center_bonus"] <= constrained["piece_activity"][
        "center_bonus"
    ]
    assert constrained["king_safety"]["piece_shield_bonus"] <= constrained["king_safety"][
        "pawn_shield_bonus"
    ]


def test_block_update_does_not_quantize_unrelated_registered_parameters():
    registry = load_tuning_registry()
    block = registry.block("search.history_order")
    profile = StrategyProfile()
    profile.move_ordering.center_pawn_development_bonus = 18

    tuned = registry.profile_from_unit_vector(profile, block, [0.5])

    assert tuned.move_ordering.center_pawn_development_bonus == 18
