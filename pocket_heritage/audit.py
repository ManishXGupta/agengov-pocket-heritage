"""Append-only, hash-chained audit log (Section IV.D, Table IV).

Each record stores a SHA-256 digest of the previous record, so any deletion,
insertion or edit breaks the chain and is detected by ``verify_chain``.
Raw images and voice are never stored: only content hashes and pseudonymous IDs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

GENESIS = "0" * 64

# Field groups of Table IV in the paper.
REQUIRED_FIELDS = (
    "request",      # request ID, UTC time, channel, language
    "requester",    # pseudonymous ID, role, consent / lawful-basis reference
    "input",        # image or audio hash; raw media not kept
    "passport",     # object ID, passport version, interpretation strands used
    "sources",      # source IDs, approver roles, review dates
    "scores",       # S, P, C, R, H, T; D, U, X, B, L, Q; A
    "decision",     # answer / review / refuse and the rule triggered
    "human_action", # curator ID, action, reason, time (or null)
    "output",       # response hash, labels shown, model and policy versions
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _digest(record: dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return sha256_text(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


class AuditLog:
    """In-memory audit log with optional JSONL persistence. The agent can append but not edit."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._records: list[dict[str, Any]] = []
        if self.path and self.path.exists():
            self._records = [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def append(self, fields: dict[str, Any]) -> dict[str, Any]:
        missing = [f for f in REQUIRED_FIELDS if f not in fields]
        if missing:
            raise ValueError(f"audit record missing fields: {missing}")
        record = dict(fields)
        record["seq"] = len(self._records)
        record["prev_hash"] = self._records[-1]["hash"] if self._records else GENESIS
        record["hash"] = _digest(record)
        self._records.append(record)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        return record


def verify_chain(records: Iterable[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Return (ok, problems). Checks sequence numbers, back-links and each record digest."""
    problems: list[str] = []
    prev = GENESIS
    for i, rec in enumerate(records):
        if rec.get("seq") != i:
            problems.append(f"record {i}: sequence number {rec.get('seq')} out of order")
        if rec.get("prev_hash") != prev:
            problems.append(f"record {i}: prev_hash does not match previous record")
        if _digest(rec) != rec.get("hash"):
            problems.append(f"record {i}: content digest mismatch (record altered)")
        missing = [f for f in REQUIRED_FIELDS if f not in rec]
        if missing:
            problems.append(f"record {i}: missing fields {missing}")
        prev = rec.get("hash", "")
    return (not problems), problems


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
