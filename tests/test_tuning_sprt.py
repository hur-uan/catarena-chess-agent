from tuning.sprt import SprtConfig, SprtDecision, evaluate_sprt


def test_sprt_accepts_h1_for_strong_positive_scores():
    result = evaluate_sprt([1.0] * 40, SprtConfig())
    assert result.decision == SprtDecision.ACCEPT_H1


def test_sprt_accepts_h0_for_strong_negative_scores():
    result = evaluate_sprt([0.0] * 40, SprtConfig())
    assert result.decision == SprtDecision.ACCEPT_H0


def test_sprt_continues_when_signal_is_small():
    result = evaluate_sprt([0.5, 0.0, 1.0, 0.5], SprtConfig())
    assert result.decision == SprtDecision.CONTINUE
