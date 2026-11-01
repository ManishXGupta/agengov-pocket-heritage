"""The governed heritage loop (Section IV.A, Table II):

identify -> authenticate -> retrieve -> verify -> govern -> explain -> audit -> learn

This is a rule-based reference implementation. Image and speech recognition are
NOT implemented: the request carries the candidate matches that a multimodal
recognition service would return. Translation is not implemented either; non-English
requests are only labelled. Plug real services in behind these interfaces.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Callable

from .audit import AuditLog, sha256_text
from .config import GovernanceConfig, load_config
from .passport import Passport, load_passports, source_admitted
from .scoring import Decision, RiskFactors, TrustFactors, decide, risk_score, trust_score

MODEL_VERSION = "rule-based-reference-0.1"
PERSONAL_DATA_LEVELS = {"none": 0.0, "incidental": 0.5, "direct": 1.0}
CONTESTED_RISK = 0.3


@dataclass
class Candidate:
    object_id: str
    confidence: float


@dataclass
class Request:
    request_id: str
    role: str
    intent: str = "identify"
    candidates: list[Candidate] = field(default_factory=list)
    pseudonym: str = "anon"
    consent: bool = False
    channel: str = "phone"
    language: str = "en"
    input_type: str = "photo"
    input_ref: str = ""
    personal_data: str = "none"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Request":
        d = dict(d)
        d["candidates"] = [Candidate(**c) for c in d.get("candidates", [])]
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in allowed})


@dataclass
class Result:
    request_id: str
    decision: Decision
    rule: str
    T: float
    Q: float
    A: int
    trust: dict[str, float]
    risk: dict[str, float]
    response: str
    released_claims: list[dict[str, Any]]
    labels: list[str]
    object_id: str | None
    learning: dict[str, Any] | None = None
    curator_task: dict[str, Any] | None = None
    audit_hash: str | None = None


def freshness(reviewed_on: str, now: dt.date, cfg: GovernanceConfig) -> float:
    age = (now - dt.date.fromisoformat(reviewed_on)).days
    if age <= cfg.freshness_window_days:
        return 1.0
    if age >= cfg.freshness_zero_after_days:
        return 0.0
    span = cfg.freshness_zero_after_days - cfg.freshness_window_days
    return round(1.0 - (age - cfg.freshness_window_days) / span, 4)


class GovernedHeritageAgent:
    def __init__(
        self,
        passports: dict[str, Passport] | None = None,
        cfg: GovernanceConfig | None = None,
        audit: AuditLog | None = None,
        today: dt.date | None = None,
        clock: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self.cfg = cfg or load_config()
        self.passports = passports if passports is not None else load_passports()
        self.audit = audit if audit is not None else AuditLog()
        self.today = today or dt.date.today()
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self.curator_queue: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ public
    def handle(self, req: Request) -> Result:
        """Run the governed loop. Any internal failure fails closed (refuse + curator task)."""
        try:
            result = self._run(req)
        except Exception as exc:  # fail closed, never answer ungoverned
            result = Result(
                request_id=req.request_id, decision=Decision.REFUSE,
                rule=f"refuse: fail-closed ({type(exc).__name__})", T=0.0, Q=1.0, A=0,
                trust={}, risk={}, response="I can't answer this right now. A curator has been notified.",
                released_claims=[], labels=["ai-generated", "fail-closed"], object_id=None,
            )
            result.curator_task = self._task(req, "governance layer failure", None)
        self._write_audit(req, result)
        return result

    def curator_action(self, result: Result, curator_id: str, action: str, reason: str) -> dict[str, Any]:
        """Log a curator decision on a reviewed or refused request.

        A curator approval can release an answer, but it never lowers Q: the original
        scores stay in the record and the override is logged with a mandatory reason.
        """
        if action not in {"approve_release", "confirm_refusal", "edit_passport"}:
            raise ValueError(f"unknown curator action {action}")
        if not reason.strip():
            raise ValueError("a curator action must state a reason")
        return self.audit.append({
            "request": {"request_id": result.request_id, "time": self.clock().isoformat(), "channel": "curator-console", "language": "en"},
            "requester": {"pseudonym": curator_id, "role": "curator", "consent_ref": "staff"},
            "input": {"type": "curator-action", "content_hash": sha256_text(reason), "raw_media_stored": False},
            "passport": {"object_id": result.object_id},
            "sources": [],
            "scores": {"T": result.T, "Q": result.Q, "A": result.A, "note": "original scores retained; override does not change Q"},
            "decision": {"action": action, "rule": f"curator override of '{result.rule}'"},
            "human_action": {"curator_id": curator_id, "action": action, "reason": reason, "time": self.clock().isoformat()},
            "output": {"response_hash": None, "labels": ["curator-decision"], "model_version": MODEL_VERSION, "policy_version": self.cfg.policy_version},
        })

    # ------------------------------------------------------------------ steps
    def _run(self, req: Request) -> Result:
        cfg = self.cfg
        # 1 Identify
        best = max(req.candidates, key=lambda c: c.confidence, default=None)
        if best is None or best.confidence < cfg.min_match_confidence or best.object_id not in self.passports:
            return self._unmatched(req, best)
        passport = self.passports[best.object_id]

        # 2 Authenticate
        levels = set(cfg.roles.get(req.role, []))
        role_ok = req.role in cfg.roles
        consent_ok = req.consent or req.role not in cfg.consent_required_roles

        # 3 Retrieve: intent-relevant claims, never from community-restricted strands
        relevant = [(s, c) for s, c in passport.claims_for(req.intent) if not s.get("restricted_by_community", False)]
        accessible = [(s, c) for s, c in relevant if c["access"] in levels]
        A = int(role_ok and consent_ok and bool(accessible))

        # 4 Verify: source admission, provenance coverage, freshness, curator approval
        admitted = passport.admitted_source_ids()
        supported = [(s, c) for s, c in relevant if any(sid in admitted for sid in c["source_ids"])]
        cited = sorted({sid for _, c in supported for sid in c["source_ids"] if sid in admitted})
        S = sum(passport.sources[sid]["authority"] for sid in cited) / len(cited) if cited else 0.0
        P = len(supported) / len(relevant) if relevant else 0.0
        approval = passport.doc["curator_approval"]
        trust = TrustFactors(S=S, P=P, C=best.confidence, R=freshness(approval["reviewed_on"], self.today, cfg), H=1.0 if approval["approved"] else 0.0)

        # 5 Govern
        sens = passport.doc["sensitivity"]
        D = PERSONAL_DATA_LEVELS.get(req.personal_data, 1.0)
        if sens.get("personal_data") and req.intent in {"history", "provenance"}:
            D = max(D, 0.5)
        X = (1.0 if req.intent == "location" else 0.1) if sens.get("restricted_location") else 0.0
        contested = passport.doc.get("contested", False) and not passport.doc.get("consensus_strand")
        risk = RiskFactors(D=D, U=cfg.sensitivity_scores[sens["cultural"]], X=X, B=CONTESTED_RISK if contested else 0.0, L=cfg.learner_impact.get(req.role, 0.1))
        T, Q = trust_score(trust, cfg), risk_score(risk, cfg)
        decision, rule = decide(T, Q, A, cfg)

        # 6 Explain
        releasable = [(s, c) for s, c in accessible if any(sid in admitted for sid in c["source_ids"])]
        labels = ["ai-generated"]
        if req.language != "en":
            labels.append(f"machine-translated:{req.language} (back-check required; translation not implemented in reference code)")
        name = passport.doc["identity"]["name"]
        task = None
        learning = None
        if decision is Decision.ANSWER:
            released = releasable
            response = self._compose_answer(passport, released, best, contested)
            labels.append("documented")
            if contested and len({s["strand_id"] for s, _ in released}) > 1:
                labels.append("plural-interpretations")
            # 8 Learn
            if req.intent == "explore" and passport.doc.get("learning"):
                learning = passport.doc["learning"]
                labels.append("learning-mode")
        elif decision is Decision.REVIEW:
            released = [(s, c) for s, c in releasable if c.get("topic") == "identity"]
            tentative = " ".join(c["text"] for _, c in released) or f"This may be the {name}."
            response = f"{tentative} Curator confirmation is required; a curator has been asked to confirm."
            labels.append("unconfirmed")
            task = self._task(req, rule, passport.object_id)
        else:
            released = []
            if A == 0:
                response = "I can't share that information because it is restricted. Your request has been passed to a curator."
            else:
                response = "I don't have approved evidence to answer that. A curator has been told."
            task = self._task(req, rule, passport.object_id)

        return Result(
            request_id=req.request_id, decision=decision, rule=rule, T=round(T, 4), Q=round(Q, 4), A=A,
            trust=trust.as_dict(), risk=risk.as_dict(), response=response,
            released_claims=[{"claim_id": c["claim_id"], "strand_id": s["strand_id"], "perspective": s["perspective"],
                              "attribution": s["attribution"], "text": c["text"],
                              "source_ids": [sid for sid in c["source_ids"] if sid in admitted]} for s, c in released],
            labels=labels, object_id=passport.object_id, learning=learning, curator_task=task,
        )

    def _unmatched(self, req: Request, best: Candidate | None) -> Result:
        cfg = self.cfg
        conf = best.confidence if best else 0.0
        trust = TrustFactors(S=0.0, P=0.0, C=conf, R=0.0, H=0.0)
        risk = RiskFactors(D=PERSONAL_DATA_LEVELS.get(req.personal_data, 1.0), U=0.0, X=0.0, B=0.0, L=cfg.learner_impact.get(req.role, 0.1))
        T, Q = trust_score(trust, cfg), risk_score(risk, cfg)
        A = int(req.role in cfg.roles)
        _, rule = decide(T, Q, A, cfg)
        closest = sorted(req.candidates, key=lambda c: -c.confidence)[:3]
        names = ", ".join(f"{self.passports[c.object_id].doc['identity']['name']} ({c.confidence:.0%})" for c in closest if c.object_id in self.passports)
        response = "I am not sure what this object is." + (f" Closest matches: {names}." if names else "") + " A curator has been told."
        return Result(
            request_id=req.request_id, decision=Decision.REFUSE, rule=rule + " (unmatched object)", T=round(T, 4), Q=round(Q, 4), A=A,
            trust=trust.as_dict(), risk=risk.as_dict(), response=response, released_claims=[],
            labels=["ai-generated", "unsure"], object_id=None, curator_task=self._task(req, "unmatched object", None),
        )

    def _compose_answer(self, passport: Passport, released, best: Candidate, contested: bool) -> str:
        name = passport.doc["identity"]["name"]
        parts = [f"Possible match, {best.confidence:.0%}: {name}."]
        strands: dict[str, list] = {}
        for s, c in released:
            strands.setdefault(s["strand_id"], [s, []])[1].append(c)
        if contested and len(strands) > 1:
            parts.append("Accounts differ, and both are approved:")
            for s, claims in strands.values():
                parts.append(f"[{s['perspective']}, {s['attribution']}] " + " ".join(c["text"] for c in claims))
        else:
            parts.extend(c["text"] for _, c in released)
        approval = passport.doc["curator_approval"]
        cited = sorted({sid for _, c in released for sid in c["source_ids"] if sid in passport.admitted_source_ids()})
        parts.append(f"Sources: {', '.join(cited)}. Passport v{passport.version}, reviewed {approval['reviewed_on']}. You are talking to an AI system.")
        return " ".join(parts)

    def _task(self, req: Request, reason: str, object_id: str | None) -> dict[str, Any]:
        task = {"request_id": req.request_id, "object_id": object_id, "reason": reason, "intent": req.intent, "role": req.role}
        self.curator_queue.append(task)
        return task

    # ------------------------------------------------------------------ 7 Audit
    def _write_audit(self, req: Request, r: Result) -> None:
        passport = self.passports.get(r.object_id) if r.object_id else None
        consent_ref = "consent:recorded" if req.consent else ("consent:missing" if req.role in self.cfg.consent_required_roles else "consent:not-required")
        src_meta = []
        if passport:
            for sid in sorted({sid for c in r.released_claims for sid in c["source_ids"]}):
                s = passport.sources[sid]
                src_meta.append({"source_id": sid, "approver_roles": s["approval"]["approver_roles"], "reviewed_on": s["approval"]["reviewed_on"], "admitted": source_admitted(s)})
        rec = self.audit.append({
            "request": {"request_id": req.request_id, "time": self.clock().isoformat(), "channel": req.channel, "language": req.language},
            "requester": {"pseudonym": req.pseudonym, "role": req.role, "consent_ref": consent_ref},
            "input": {"type": req.input_type, "content_hash": sha256_text(req.input_ref or req.request_id), "raw_media_stored": False},
            "passport": {"object_id": r.object_id, "version": passport.version if passport else None,
                         "strands_used": sorted({c["strand_id"] for c in r.released_claims})},
            "sources": src_meta,
            "scores": {**r.trust, "T": r.T, **r.risk, "Q": r.Q, "A": r.A},
            "decision": {"action": r.decision.value, "rule": r.rule},
            "human_action": None,
            "output": {"response_hash": sha256_text(r.response), "labels": r.labels, "model_version": MODEL_VERSION, "policy_version": self.cfg.policy_version},
        })
        r.audit_hash = rec["hash"]
