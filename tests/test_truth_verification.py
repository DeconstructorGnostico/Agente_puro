import json
import subprocess
import sys
from pathlib import Path

import pytest

from omega_meta.core.engine import AgentePuro
from omega_meta.core.truth import TruthEngine, TruthError

ROOT = Path(__file__).resolve().parent.parent
URL = "https://example.org/doc"


def eng():
    t = TruthEngine()
    t.register_verifier("rev-1", "Lab A")
    t.register_verifier("rev-2", "Lab B")
    return t


def ev(t, claim, src, rel="SUPPORTS", rev="rev-1", sub="alice", **kw):
    return t.add_evidence(claim=claim, statement=f"{src} dice", source_id=src, provenance=f"https://{src}.example/doc",
                          relation=rel, method="documental", submitted_by=sub, reviewed_by=rev, **kw)


def test_self_review_rejected():
    t = eng()
    t.register_verifier("alice", "yo")
    with pytest.raises(TruthError):
        ev(t, "X es Y.", "s1", rev="alice", sub="alice")


def test_reviewer_must_be_registered():
    with pytest.raises(TruthError):
        ev(eng(), "X es Y.", "s1", rev="yo")


def test_model_cannot_be_source_or_reviewer():
    t = eng()
    with pytest.raises(TruthError):
        ev(t, "X es Y.", "model")
    with pytest.raises(TruthError):
        t.register_verifier("model", "x")


def test_provenance_required():
    with pytest.raises(TruthError):
        eng().add_evidence(claim="X", statement="s", source_id="s1", provenance="blog", relation="SUPPORTS",
                           method="m", submitted_by="alice", reviewed_by="rev-1")


def test_two_support_one_refute_is_contradicted():
    t = eng()
    c = "El servidor tiene 16 GB de RAM."
    ev(t, c, "cmdb")
    ev(t, c, "erp", rev="rev-2")
    ev(t, c, "ops", rel="REFUTES")
    assert t.assess(c)["state"] == "CONTRADICTED"


def test_two_independent_supports_is_supported():
    t = eng()
    c = "El servidor tiene 16 GB de RAM."
    ev(t, c, "cmdb")
    ev(t, c, "erp", rev="rev-2")
    assert t.assess(c)["state"] == "SUPPORTED"


def test_model_agreement_is_not_evidence():
    t = eng()
    c = "X es Y."
    r = t.assess(c, {"models": ["a", "b", "c"], "agree": True})
    assert r["state"] == "UNDETERMINED"
    assert r["corroboration"] is None or r["corroboration"].get("counted_as_evidence") is False


def test_truth_state_reloads(tmp_path):
    a = AgentePuro(runtime_dir=tmp_path)
    a.register_verifier("rev-1", "Lab A")
    a.add_evidence(claim="A es B.", statement="s", source_id="s1", provenance=URL, relation="SUPPORTS",
                   method="m", submitted_by="alice", reviewed_by="rev-1")
    b = AgentePuro(runtime_dir=tmp_path)
    assert "rev-1" in b.truth.verifiers and len(b.truth.evidence) == 1


def test_wrong_answer_vs_tool_result_rejected():
    a = AgentePuro(runtime_dir=None, answer_override=lambda instr, ctx: "La respuesta es 5")
    o = a.process("Cuánto es 2 + 2")
    assert o["decision"] == "REJECT"
    assert "ANSWER_INCONSISTENT_WITH_TOOL_RESULT" in json.dumps(o["reasons"]) + json.dumps(o["verification"])


def test_calc_verified_by_independent_recompute():
    o = AgentePuro(runtime_dir=None).process("Cuánto es 256 * 4")
    assert o["status"] == "VERIFIED" and o["verification"]["verifier"] == "independent_recompute"


def _pure(*args):
    p = subprocess.run([sys.executable, str(ROOT / "pure_agent.py"), *args], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=60)
    return p.returncode, p.stdout


def test_flat_earth_with_self_declared_blogs_not_verified():
    evd = json.dumps([{"description": "blog 1", "source_id": "blog1", "supports": True, "independently_reviewed": True},
                      {"description": "blog 2", "source_id": "blog2", "supports": True, "independently_reviewed": True}])
    _, out = _pure("--text", "La Tierra es plana.", "--evidence", evd)
    o = json.loads(out)
    assert o["status"] != "VERIFIED" and o["epistemic_verdict"] != "SUPPORTED"
    assert o["evidence_ingest"]["assessment"]["state"] == "UNDETERMINED"


def test_pure_agent_non_interactive_no_eoferror():
    code, out = _pure()
    assert code == 2 and "NO_INPUT" in out


def test_pure_agent_v5_2support_1refute():
    vs = json.dumps([{"id": "rev-1", "organization": "A"}, {"id": "rev-2", "organization": "B"}])
    evd = json.dumps([
        {"description": "inv", "source_origin": "cmdb", "url": "https://cmdb.example/1", "supports": True, "reviewed_by": "rev-1"},
        {"description": "fac", "source_origin": "erp", "url": "https://erp.example/2", "supports": True, "reviewed_by": "rev-2"},
        {"description": "dmi", "source_origin": "ops", "url": "https://ops.example/3", "supports": False, "reviewed_by": "rev-1"}])
    _, out = _pure("--text", "El servidor tiene 16 GB de RAM.", "--verifiers", vs, "--evidence", evd)
    o = json.loads(out)
    assert o["evidence_ingest"]["assessment"]["state"] == "CONTRADICTED"
    assert o["decision"] == "HALT"
