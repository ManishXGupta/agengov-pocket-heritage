"""AGenGov Pocket Heritage: reference implementation of the governed heritage loop.

Companion code for "AGenGov Pocket Heritage: A Governed Multimodal Agentic AI
Framework for Trusted Heritage Tourism and Student Learning" (M. Gupta, ICSH 2026).
All data in this repository are synthetic.
"""
from .agent import Candidate, GovernedHeritageAgent, Request, Result
from .audit import AuditLog, verify_chain
from .config import GovernanceConfig, load_config
from .passport import Passport, load_passports, validate_passport
from .scoring import Decision, RiskFactors, TrustFactors, decide, risk_score, trust_score

__version__ = "0.1.0"

__all__ = [
    "AuditLog", "Candidate", "Decision", "GovernanceConfig", "GovernedHeritageAgent", "Passport",
    "Request", "Result", "RiskFactors", "TrustFactors", "decide", "load_config", "load_passports",
    "risk_score", "trust_score", "validate_passport", "verify_chain",
]
