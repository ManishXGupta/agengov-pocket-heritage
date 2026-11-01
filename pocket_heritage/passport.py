"""Heritage Digital Passport loading, schema validation and source admission (Section III.B)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .config import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema" / "passport.schema.json"
DEFAULT_PASSPORT_DIR = REPO_ROOT / "data" / "passports"

ADMISSION_CRITERIA = (
    "traceable_provenance",
    "scholarly_or_institutional_standing",
    "community_consent",
    "review_date_recorded",
    "conflict_of_interest_checked",
)

INTENT_TOPICS = {
    "identify": {"identity"},
    "history": {"identity", "history", "provenance"},
    "explore": {"identity", "history", "meaning"},
    "location": {"location"},
    "practice": {"practice", "meaning"},
    "provenance": {"provenance"},
}


def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_passport(doc: dict[str, Any]) -> list[str]:
    """Return a list of schema-validation messages (empty when valid)."""
    errors = sorted(_validator().iter_errors(doc), key=lambda e: list(e.path))
    msgs = [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]
    # Cross-reference check: every claim must cite sources that exist in the passport.
    known = {s["source_id"] for s in doc.get("sources", [])}
    for strand in doc.get("strands", []):
        for claim in strand.get("claims", []):
            for sid in claim.get("source_ids", []):
                if sid not in known:
                    msgs.append(f"claim {claim.get('claim_id')}: unknown source {sid}")
    return msgs


def source_admitted(source: dict[str, Any]) -> bool:
    """A source is admitted only if the board approved it and all five criteria hold."""
    appr = source["approval"]
    return appr["status"] == "approved" and all(appr["criteria"][c] for c in ADMISSION_CRITERIA)


@dataclass
class Passport:
    doc: dict[str, Any]

    @property
    def object_id(self) -> str:
        return self.doc["object_id"]

    @property
    def version(self) -> int:
        return self.doc["passport_version"]

    @property
    def sources(self) -> dict[str, dict[str, Any]]:
        return {s["source_id"]: s for s in self.doc["sources"]}

    def admitted_source_ids(self) -> set[str]:
        return {sid for sid, s in self.sources.items() if source_admitted(s)}

    def claims_for(self, intent: str) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
        """Yield (strand, claim) pairs whose topic matches the request intent."""
        topics = INTENT_TOPICS.get(intent, {"identity"})
        for strand in self.doc["strands"]:
            for claim in strand["claims"]:
                if claim.get("topic", "identity") in topics:
                    yield strand, claim


def load_passports(directory: str | Path = DEFAULT_PASSPORT_DIR, validate: bool = True) -> dict[str, Passport]:
    out: dict[str, Passport] = {}
    for path in sorted(Path(directory).glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if validate:
            errs = validate_passport(doc)
            if errs:
                raise ValueError(f"{path.name} is not a valid passport: {errs}")
        out[doc["object_id"]] = Passport(doc)
    return out
