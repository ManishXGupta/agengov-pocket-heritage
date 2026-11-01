"""Hash-chained audit log (Section IV.D, Table IV)."""
import copy

import pytest

from pocket_heritage import AuditLog, verify_chain
from pocket_heritage.audit import REQUIRED_FIELDS


def _fields(i: int) -> dict:
    return {f: {"i": i} for f in REQUIRED_FIELDS} | {"human_action": None}


def _log(n: int = 4) -> AuditLog:
    log = AuditLog()
    for i in range(n):
        log.append(_fields(i))
    return log


def test_intact_chain_verifies():
    ok, problems = verify_chain(_log().records)
    assert ok, problems


def test_missing_fields_rejected():
    with pytest.raises(ValueError):
        AuditLog().append({"request": {}})


def test_edit_detected():
    recs = [copy.deepcopy(r) for r in _log().records]
    recs[1]["decision"] = {"action": "answer"}
    ok, problems = verify_chain(recs)
    assert not ok and any("altered" in p for p in problems)


def test_deletion_detected():
    recs = list(_log().records)
    del recs[2]
    assert not verify_chain(recs)[0]


def test_reorder_detected():
    recs = list(_log().records)
    recs[1], recs[2] = recs[2], recs[1]
    assert not verify_chain(recs)[0]


def test_persistence_roundtrip(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append(_fields(0))
    log.append(_fields(1))
    reloaded = AuditLog(path)
    assert len(reloaded) == 2 and verify_chain(reloaded.records)[0]
    reloaded.append(_fields(2))
    assert verify_chain(AuditLog(path).records)[0]


def test_agent_uses_supplied_empty_log_and_persists(tmp_path):
    """Regression: an empty AuditLog is falsy (len 0) and must still be used by the agent."""
    from pocket_heritage import Candidate, GovernedHeritageAgent, Request

    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    agent = GovernedHeritageAgent(audit=log)
    assert agent.audit is log
    agent.handle(Request(request_id="r1", role="tourist", candidates=[Candidate("bronze-coin", 0.9)]))
    assert path.exists() and len(AuditLog(path)) == 1
