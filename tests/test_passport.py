"""Passport schema and the five source-admission criteria (Section III.B)."""
import copy

from pocket_heritage import load_passports, validate_passport
from pocket_heritage.passport import source_admitted

PASSPORTS = load_passports()


def test_all_sample_passports_valid_and_synthetic():
    assert len(PASSPORTS) >= 5
    for p in PASSPORTS.values():
        assert validate_passport(p.doc) == []
        assert p.doc["synthetic"] is True


def test_unknown_source_reference_flagged():
    doc = copy.deepcopy(PASSPORTS["bronze-coin"].doc)
    doc["strands"][0]["claims"][0]["source_ids"] = ["does-not-exist"]
    assert any("unknown source" in e for e in validate_passport(doc))


def test_schema_rejects_bad_access_level():
    doc = copy.deepcopy(PASSPORTS["bronze-coin"].doc)
    doc["strands"][0]["claims"][0]["access"] = "everyone"
    assert validate_passport(doc)


def test_withdrawn_and_pending_sources_not_admitted():
    sea = PASSPORTS["sea-gate-mural"]
    assert "src-old-guidebook-1972" not in sea.admitted_source_ids()
    assert PASSPORTS["carved-gate"].admitted_source_ids() == set()


def test_every_criterion_is_required():
    src = copy.deepcopy(PASSPORTS["bronze-coin"].sources["src-excavation-2019"])
    assert source_admitted(src)
    for crit in src["approval"]["criteria"]:
        broken = copy.deepcopy(src)
        broken["approval"]["criteria"][crit] = False
        assert not source_admitted(broken), crit
