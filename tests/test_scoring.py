"""Equations (1) to (3) and the paper's worked example (Section III.C)."""
import math

import pytest

from pocket_heritage import Decision, RiskFactors, TrustFactors, decide, load_config, risk_score, trust_score

CFG = load_config()


def test_weights_sum_to_one():
    assert math.isclose(sum(CFG.trust_weights.values()), 1.0)
    assert math.isclose(sum(CFG.risk_weights.values()), 1.0)


def test_scores_bounded():
    assert trust_score(TrustFactors(1, 1, 1, 1, 1), CFG) == pytest.approx(1.0)
    assert risk_score(RiskFactors(1, 1, 1, 1, 1), CFG) == pytest.approx(1.0)
    assert trust_score(TrustFactors(0, 0, 0, 0, 0), CFG) == 0.0


def test_factor_out_of_range_rejected():
    with pytest.raises(ValueError):
        trust_score(TrustFactors(1.2, 0, 0, 0, 0), CFG)


# Worked example from the revised paper.
def test_worked_example_sea_gate_answers():
    T = trust_score(TrustFactors(S=1.0, P=0.90, C=0.82, R=0.95, H=1.0), CFG)
    Q = risk_score(RiskFactors(D=0.0, U=0.2, X=0.1, B=0.3, L=0.1), CFG)
    assert T == pytest.approx(0.9315)   # reported as 0.93 in the paper
    assert Q == pytest.approx(0.125)    # reported as 0.13 in the paper
    assert decide(T, Q, 1, CFG)[0] is Decision.ANSWER


def test_worked_example_ritual_chamber_refused_despite_high_trust():
    T = trust_score(TrustFactors(S=1.0, P=0.90, C=0.80, R=0.90, H=1.0), CFG)
    Q = risk_score(RiskFactors(D=0.0, U=1.0, X=1.0, B=0.2, L=0.1), CFG)
    assert T == pytest.approx(0.92)
    assert Q == pytest.approx(0.49)
    assert decide(T, Q, 1, CFG)[0] is Decision.REVIEW   # risk alone would send it to review
    assert decide(T, Q, 0, CFG)[0] is Decision.REFUSE   # the tourist role (A = 0) refuses it


def test_worked_example_no_passport_unsure():
    T = trust_score(TrustFactors(S=0.5, P=0.2, C=0.30, R=0.5, H=0.0), CFG)
    assert T == pytest.approx(0.335)   # reported as 0.34 in the paper
    assert decide(T, 0.0, 1, CFG)[0] is Decision.REFUSE


@pytest.mark.parametrize(
    "T,Q,A,expected",
    [
        (0.95, 0.10, 1, Decision.ANSWER),
        (0.80, 0.29, 1, Decision.ANSWER),   # boundaries are inclusive for answer
        (0.79, 0.10, 1, Decision.REVIEW),
        (0.95, 0.30, 1, Decision.REVIEW),
        (0.55, 0.59, 1, Decision.REVIEW),
        (0.54, 0.10, 1, Decision.REFUSE),
        (0.99, 0.60, 1, Decision.REFUSE),
        (1.00, 0.00, 0, Decision.REFUSE),   # precedence: A = 0 always refuses
    ],
)
def test_decision_rule_and_precedence(T, Q, A, expected):
    assert decide(T, Q, A, CFG)[0] is expected
