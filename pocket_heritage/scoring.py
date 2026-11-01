"""Evidence-trust score T (Eq. 1), governance-risk score Q (Eq. 2) and the decision rule (Eq. 3).

All factor values are normalised to [0, 1]. The weights and thresholds come from
config/governance.yaml and are illustrative until calibrated (see README).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from .config import GovernanceConfig


class Decision(str, Enum):
    ANSWER = "answer"
    REVIEW = "review"
    REFUSE = "refuse"


@dataclass(frozen=True)
class TrustFactors:
    S: float  # approved-source authority
    P: float  # passport / provenance match
    C: float  # multimodal identification confidence
    R: float  # record freshness
    H: float  # curator approval

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class RiskFactors:
    D: float  # personal-data sensitivity
    U: float  # cultural or community sensitivity
    X: float  # restricted-location or security exposure
    B: float  # bias or contested-history risk
    L: float  # child or learner impact

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def _check_unit(values: dict[str, float]) -> None:
    for k, v in values.items():
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"factor {k}={v} is outside [0, 1]")


def trust_score(f: TrustFactors, cfg: GovernanceConfig) -> float:
    """Eq. (1): T = 0.35S + 0.25P + 0.20C + 0.15R + 0.10H (default weights)."""
    d = f.as_dict()
    _check_unit(d)
    return sum(cfg.trust_weights[k] * d[k] for k in d)


def risk_score(f: RiskFactors, cfg: GovernanceConfig) -> float:
    """Eq. (2): Q = 0.30D + 0.25U + 0.20X + 0.15B + 0.10L (default weights)."""
    d = f.as_dict()
    _check_unit(d)
    return sum(cfg.risk_weights[k] * d[k] for k in d)


def decide(T: float, Q: float, A: int, cfg: GovernanceConfig) -> tuple[Decision, str]:
    """Eq. (3), evaluated in the fixed order refuse -> review -> answer.

    Returns the decision and the rule that triggered it. A high T can never
    offset a failed access check (A = 0) or a high Q.
    """
    th = cfg.thresholds
    if A == 0:
        return Decision.REFUSE, "refuse: access check failed (A = 0)"
    if Q >= th.refuse_min_risk:
        return Decision.REFUSE, f"refuse: Q >= {th.refuse_min_risk}"
    if T < th.review_min_trust:
        return Decision.REFUSE, f"refuse: T < {th.review_min_trust}"
    if T < th.answer_min_trust:
        return Decision.REVIEW, f"review: {th.review_min_trust} <= T < {th.answer_min_trust}"
    if Q >= th.answer_max_risk:
        return Decision.REVIEW, f"review: {th.answer_max_risk} <= Q < {th.refuse_min_risk}"
    return Decision.ANSWER, f"answer: T >= {th.answer_min_trust}, Q < {th.answer_max_risk}, A = 1"
