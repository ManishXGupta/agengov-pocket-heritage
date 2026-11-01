"""The synthetic evaluation must pass end to end."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_eval_harness(tmp_path):
    spec = importlib.util.spec_from_file_location("run_eval", ROOT / "eval" / "run_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    m = mod.run(ROOT / "eval" / "testset.jsonl", tmp_path)
    assert m["decision_accuracy"] == 1.0
    assert m["G2_sensitive_leak_rate"] == 0.0
    assert m["G1_approved_source_share"] == 1.0
    assert m["G6_audit_completeness"] == 1.0
    assert m["plurality_coverage"] == 1.0
