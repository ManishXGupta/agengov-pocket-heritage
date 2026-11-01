"""Command-line interface.

Examples
--------
python -m pocket_heritage.cli ask --role tourist --object sea-gate-mural --confidence 0.82
python -m pocket_heritage.cli ask --role tourist --object ritual-chamber --confidence 0.9 --intent location
python -m pocket_heritage.cli score --S 1 --P 0.9 --C 0.82 --R 0.95 --H 1 --D 0 --U 0.2 --X 0.1 --B 0.3 --L 0.1
python -m pocket_heritage.cli validate data/passports
python -m pocket_heritage.cli verify-audit eval/results/audit_log.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .agent import Candidate, GovernedHeritageAgent, Request
from .audit import load_jsonl, verify_chain
from .config import load_config
from .passport import validate_passport
from .scoring import RiskFactors, TrustFactors, decide, risk_score, trust_score


def _ask(a: argparse.Namespace) -> int:
    agent = GovernedHeritageAgent()
    req = Request(request_id="cli-1", role=a.role, intent=a.intent, consent=a.consent, language=a.language,
                  candidates=[Candidate(a.object, a.confidence)] if a.object else [])
    res = agent.handle(req)
    out = asdict(res)
    out["decision"] = res.decision.value
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def _score(a: argparse.Namespace) -> int:
    cfg = load_config()
    T = trust_score(TrustFactors(a.S, a.P, a.C, a.R, a.H), cfg)
    Q = risk_score(RiskFactors(a.D, a.U, a.X, a.B, a.L), cfg)
    d, rule = decide(T, Q, a.A, cfg)
    print(json.dumps({"T": round(T, 4), "Q": round(Q, 4), "A": a.A, "decision": d.value, "rule": rule}, indent=2))
    return 0


def _validate(a: argparse.Namespace) -> int:
    bad = 0
    for p in sorted(Path(a.path).glob("*.json")):
        errs = validate_passport(json.loads(p.read_text(encoding="utf-8")))
        print(f"{'OK  ' if not errs else 'FAIL'} {p.name}")
        for e in errs:
            print(f"     {e}")
        bad += bool(errs)
    return 1 if bad else 0


def _verify(a: argparse.Namespace) -> int:
    ok, problems = verify_chain(load_jsonl(a.path))
    print("audit chain intact" if ok else "audit chain BROKEN")
    for p in problems:
        print(" -", p)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pocket-heritage")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ask", help="run one request through the governed loop")
    s.add_argument("--role", default="tourist")
    s.add_argument("--object", help="object_id proposed by the (simulated) recognizer")
    s.add_argument("--confidence", type=float, default=0.8)
    s.add_argument("--intent", default="identify", choices=["identify", "history", "explore", "location", "practice", "provenance"])
    s.add_argument("--language", default="en")
    s.add_argument("--consent", action="store_true")
    s.set_defaults(fn=_ask)

    s = sub.add_parser("score", help="compute T, Q and the decision from raw factors")
    for k in "SPCRHDUXBL":
        s.add_argument(f"--{k}", type=float, required=True)
    s.add_argument("--A", type=int, default=1, choices=[0, 1])
    s.set_defaults(fn=_score)

    s = sub.add_parser("validate", help="validate passport JSON files against the schema")
    s.add_argument("path")
    s.set_defaults(fn=_validate)

    s = sub.add_parser("verify-audit", help="verify a hash-chained audit log (JSONL)")
    s.add_argument("path")
    s.set_defaults(fn=_verify)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
