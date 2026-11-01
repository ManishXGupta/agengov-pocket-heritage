"""Load and validate the governance configuration (config/governance.yaml)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "governance.yaml"


@dataclass(frozen=True)
class Thresholds:
    answer_min_trust: float
    review_min_trust: float
    answer_max_risk: float
    refuse_min_risk: float


@dataclass(frozen=True)
class GovernanceConfig:
    trust_weights: dict[str, float]
    risk_weights: dict[str, float]
    thresholds: Thresholds
    min_match_confidence: float
    freshness_window_days: int
    freshness_zero_after_days: int
    roles: dict[str, list[str]]
    consent_required_roles: list[str]
    sensitivity_scores: dict[str, float]
    learner_impact: dict[str, float]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def policy_version(self) -> str:
        """Short, stable fingerprint of the configuration, written to every audit record."""
        import hashlib, json

        blob = json.dumps(self.raw, sort_keys=True).encode()
        return "cfg-" + hashlib.sha256(blob).hexdigest()[:12]


def _check_weights(name: str, weights: dict[str, float], keys: set[str]) -> None:
    if set(weights) != keys:
        raise ValueError(f"{name} must define exactly {sorted(keys)}, got {sorted(weights)}")
    if any(w < 0 for w in weights.values()):
        raise ValueError(f"{name} must be non-negative")
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError(f"{name} must sum to 1.0, got {sum(weights.values())}")


def load_config(path: str | Path = DEFAULT_CONFIG) -> GovernanceConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    tw, rw = raw["trust_weights"], raw["risk_weights"]
    _check_weights("trust_weights", tw, {"S", "P", "C", "R", "H"})
    _check_weights("risk_weights", rw, {"D", "U", "X", "B", "L"})
    th = Thresholds(**raw["thresholds"])
    if not (0 <= th.review_min_trust < th.answer_min_trust <= 1):
        raise ValueError("require 0 <= review_min_trust < answer_min_trust <= 1")
    if not (0 <= th.answer_max_risk < th.refuse_min_risk <= 1):
        raise ValueError("require 0 <= answer_max_risk < refuse_min_risk <= 1")
    return GovernanceConfig(
        trust_weights=tw,
        risk_weights=rw,
        thresholds=th,
        min_match_confidence=raw["identification"]["min_match_confidence"],
        freshness_window_days=raw["freshness"]["window_days"],
        freshness_zero_after_days=raw["freshness"]["zero_after_days"],
        roles=raw["roles"],
        consent_required_roles=raw.get("consent_required_roles", []),
        sensitivity_scores=raw["sensitivity_scores"],
        learner_impact=raw["learner_impact"],
        raw=raw,
    )
