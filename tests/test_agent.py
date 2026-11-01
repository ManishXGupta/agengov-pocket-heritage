"""End-to-end behaviour of the governed loop, including the Table V scenarios."""
import datetime as dt

import pytest

from pocket_heritage import Candidate, Decision, GovernedHeritageAgent, Request, verify_chain

TODAY = dt.date(2026, 11, 1)
LEAKS = ("RESTRICTED-", "PERSONAL-DATA-DETAIL", "UNAPPROVED-CLAIM", "sea captain")


@pytest.fixture
def agent():
    return GovernedHeritageAgent(today=TODAY)


def ask(agent, role, obj, conf, intent="identify", **kw):
    cands = [Candidate(obj, conf)] if obj else []
    return agent.handle(Request(request_id=f"{role}-{obj}-{intent}", role=role, intent=intent, candidates=cands, **kw))


def no_leak(res):
    text = res.response + " ".join(c["text"] for c in res.released_claims)
    return not any(m in text for m in LEAKS)


def test_tourist_gate_mural_answered(agent):
    r = ask(agent, "tourist", "sea-gate-mural", 0.82)
    assert r.decision is Decision.ANSWER
    assert "Possible match, 82%" in r.response and "reviewed 2026-03-15" in r.response
    assert "ai-generated" in r.labels


def test_contested_history_shows_both_strands(agent):
    r = ask(agent, "student", "sea-gate-mural", 0.88, intent="history", consent=True)
    assert r.decision is Decision.ANSWER
    assert {c["strand_id"] for c in r.released_claims} == {"museum-record", "community-account"}
    assert "plural-interpretations" in r.labels
    assert no_leak(r)   # withdrawn guidebook claim dropped


def test_protected_location_refused_even_with_high_trust(agent):
    r = ask(agent, "visitor", "ritual-chamber", 0.95, intent="location")
    assert r.decision is Decision.REFUSE and r.A == 0 and r.T >= 0.8
    assert r.curator_task is not None and no_leak(r)


def test_sacred_object_identity_only(agent):
    r = ask(agent, "tourist", "ritual-chamber", 0.93)
    assert r.decision is Decision.ANSWER and no_leak(r)


def test_community_restricted_strand_never_released_even_to_curator(agent):
    r = ask(agent, "curator", "ritual-chamber", 0.95, intent="practice")
    assert r.decision is Decision.REFUSE and no_leak(r)


def test_unmatched_object_says_unsure(agent):
    r = ask(agent, "tourist", "bronze-coin", 0.31)
    assert r.decision is Decision.REFUSE and "not sure" in r.response and "unsure" in r.labels


def test_unapproved_source_cannot_be_answered(agent):
    r = ask(agent, "tourist", "carved-gate", 0.99)
    assert r.decision is Decision.REFUSE and r.trust["S"] == 0 and no_leak(r)


def test_stale_unapproved_record_goes_to_curator(agent):
    r = ask(agent, "tourist", "ceremonial-statue", 0.70)
    assert r.decision is Decision.REVIEW and "curator" in r.response.lower()
    assert r.trust["R"] == 0.0 and r.trust["H"] == 0.0


def test_student_needs_consent(agent):
    assert ask(agent, "student", "bronze-coin", 0.9, intent="explore").decision is Decision.REFUSE
    r = ask(agent, "student", "bronze-coin", 0.9, intent="explore", consent=True)
    assert r.decision is Decision.ANSWER and r.learning and len(r.learning["quiz"]) == 3


def test_role_based_claim_filtering(agent):
    tourist = ask(agent, "tourist", "bronze-coin", 0.9, intent="history")
    student = ask(agent, "student", "bronze-coin", 0.9, intent="history", consent=True)
    assert "bc-hist-2" not in {c["claim_id"] for c in tourist.released_claims}
    assert "bc-hist-2" in {c["claim_id"] for c in student.released_claims}


def test_non_english_is_labelled(agent):
    r = ask(agent, "tourist", "sea-gate-mural", 0.82, language="es")
    assert any(l.startswith("machine-translated:es") for l in r.labels)


def test_fail_closed(agent, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("index offline")
    monkeypatch.setattr(agent, "_run", boom)
    r = ask(agent, "tourist", "sea-gate-mural", 0.9)
    assert r.decision is Decision.REFUSE and "fail-closed" in r.rule
    assert len(agent.audit) == 1


def test_every_request_audited_and_chain_intact(agent):
    for obj, conf in [("sea-gate-mural", 0.8), ("ritual-chamber", 0.9), ("carved-gate", 0.9), (None, 0)]:
        ask(agent, "tourist", obj, conf)
    assert len(agent.audit) == 4
    assert verify_chain(agent.audit.records)[0]
    rec = agent.audit.records[0]
    assert rec["input"]["raw_media_stored"] is False
    assert set(rec["scores"]) >= {"S", "P", "C", "R", "H", "T", "D", "U", "X", "B", "L", "Q", "A"}


def test_curator_override_logged_and_requires_reason(agent):
    r = ask(agent, "tourist", "ceremonial-statue", 0.7)
    with pytest.raises(ValueError):
        agent.curator_action(r, "cur-01", "approve_release", "  ")
    rec = agent.curator_action(r, "cur-01", "approve_release", "Date confirmed against 2026 catalogue")
    assert rec["human_action"]["reason"].startswith("Date confirmed")
    assert rec["scores"]["Q"] == r.Q
    assert verify_chain(agent.audit.records)[0]
