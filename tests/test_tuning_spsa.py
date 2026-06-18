import random

from tuning.spsa import SpsaConfig, apply_spsa_result, spsa_update_step


def test_spsa_step_produces_bounded_plus_and_minus_vectors():
    rng = random.Random(7)
    step = spsa_update_step([0.2, 0.8], 1, SpsaConfig(), rng)
    assert all(0.0 <= value <= 1.0 for value in step.plus_vector)
    assert all(0.0 <= value <= 1.0 for value in step.minus_vector)
    assert len(step.delta) == 2


def test_spsa_update_moves_in_delta_direction_for_positive_score_difference():
    rng = random.Random(11)
    theta = [0.5, 0.5]
    step = spsa_update_step(theta, 1, SpsaConfig(), rng)
    updated = apply_spsa_result(theta, step, score_difference=0.25)
    for old, new in zip(theta, updated):
        assert 0.0 <= new <= 1.0
        assert new != old


def test_spsa_update_can_apply_minimum_effective_signal():
    rng = random.Random(11)
    theta = [0.5, 0.5]
    step = spsa_update_step(theta, 1, SpsaConfig(), rng)

    tiny = apply_spsa_result(theta, step, score_difference=0.001)
    boosted = apply_spsa_result(
        theta,
        step,
        score_difference=0.001,
        min_effective_score_difference=0.05,
    )

    assert max(abs(new - old) for old, new in zip(theta, boosted)) > max(
        abs(new - old) for old, new in zip(theta, tiny)
    )
