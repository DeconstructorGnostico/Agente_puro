"""L0 — Invariantes estructurales I01–I10 como comprobaciones ejecutables.

Cada invariante recibe el registro del ciclo (`record`) y devuelve
{"id", "rule", "passed", "detail"}. Todas pueden fallar y tienen tests.
"""

from __future__ import annotations

import hashlib
import json

SEED = 2412598653108

RULES = {
    "I01": "INPUT != VERIFIED_INPUT",
    "I02": "INFERENCE != FACT",
    "I03": "CONTEXT != EVIDENCE",
    "I04": "EXECUTION REQUIRES VALIDATION",
    "I05": "STATE CHANGES REQUIRE AUDIT",
    "I06": "LEARNING REQUIRES ACCEPTANCE",
    "I07": "ERROR_THRESHOLD => HALT",
    "I08": "RESPONSE != REALITY",
    "I09": "UNVERIFIED != VERIFIED",
    "I10": "NO SILENT STATE MUTATION",
}

CONTRACT_KEYS = ("objective", "intent_type", "action_class", "constraints", "evidence")
FORBIDDEN_EVIDENCE_SOURCES = {"model", "user_input", "context"}
LABELS = {"VERIFIED", "PARTIALLY_VERIFIED", "UNVERIFIED"}


def fingerprint() -> str:
    """Identificador de la versión del conjunto de reglas (no es una prueba)."""
    payload = json.dumps(RULES, sort_keys=True)
    return hashlib.sha256(f"{SEED}:{payload}".encode()).hexdigest()


def _ok(i, detail="ok"):
    return {"id": i, "rule": RULES[i], "passed": True, "detail": detail}


def _fail(i, detail):
    return {"id": i, "rule": RULES[i], "passed": False, "detail": detail}


def _before(trace, a, b):
    return a in trace and b in trace and trace.index(a) < trace.index(b)


def check_I01(r):
    """El ejecutor solo recibe la instrucción formal validada, nunca el texto crudo."""
    if not r.get("execution_requested"):
        return _ok("I01", "N/A: no execution")
    instr = r.get("instruction") or {}
    if not instr.get("validated"):
        return _fail("I01", "instruction not validated by firewall")
    missing = [k for k in CONTRACT_KEYS if k not in instr]
    if missing:
        return _fail("I01", f"instruction missing formal fields: {missing}")
    return _ok("I01")


def check_I02(r):
    result = r.get("result")
    if not isinstance(result, dict):
        return _ok("I02", "N/A: no result")
    facts = {str(x) for x in result.get("facts", []) if isinstance(result.get("facts"), list)}
    infs = {str(x) for x in result.get("inferences", []) if isinstance(result.get("inferences"), list)}
    both = facts & infs
    if both:
        return _fail("I02", f"items labelled both fact and inference: {sorted(both)}")
    used = (r.get("verification") or {}).get("evidence_sources", [])
    if "model" in used:
        return _fail("I02", "model output used as evidence for itself")
    return _ok("I02")


def check_I03(r):
    instr = r.get("instruction") or {}
    norm = instr.get("normalized_input", "")
    for item in instr.get("evidence", []):
        if item.get("source") in FORBIDDEN_EVIDENCE_SOURCES:
            return _fail("I03", f"evidence source not independent: {item.get('source')}")
        if norm and item.get("text", "").strip() == norm:
            return _fail("I03", "evidence is identical to the user's own input")
    return _ok("I03")


def check_I04(r):
    if not r.get("execution_requested"):
        return _ok("I04", "N/A: no execution")
    trace = r.get("trace", [])
    if not _before(trace, "VALIDATING", "AWAITING_AUTH"):
        return _fail("I04", "VALIDATING must precede AWAITING_AUTH")
    if not (r.get("firewall") or {}).get("allowed"):
        return _fail("I04", "firewall did not allow the instruction")
    if not (r.get("authorization") or {}).get("authorized"):
        return _fail("I04", "execution without authorization")
    if "EXECUTING" in trace and not _before(trace, "AWAITING_AUTH", "EXECUTING"):
        return _fail("I04", "EXECUTING before AWAITING_AUTH")
    return _ok("I04")


def check_I05(r):
    trace = r.get("trace", [])
    audited = r.get("audited_transitions", 0)
    if audited != len(trace):
        return _fail("I05", f"{len(trace)} states entered but {audited} audited")
    return _ok("I05")


def check_I06(r):
    learning = r.get("learning") or {}
    status = (r.get("verification") or {}).get("status")
    if learning.get("written") and status != "VERIFIED":
        return _fail("I06", f"learning written with status {status}")
    return _ok("I06")


def check_I07(r):
    e = r.get("engine") or {}
    over = e.get("reject_streak", 0) >= e.get("max_reject_streak", 1 << 30) or \
        e.get("cycles", 0) >= e.get("max_cycles", 1 << 30)
    if over and e.get("status") != "HALTED":
        return _fail("I07", "error/cycle threshold reached but engine not HALTED")
    return _ok("I07")


def check_I08(r):
    if r.get("outcome") != "COMMITTED":
        return _ok("I08", "N/A: not delivered")
    status = (r.get("verification") or {}).get("status")
    if status not in LABELS:
        return _fail("I08", "delivered response without verification label")
    return _ok("I08")


def check_I09(r):
    v = r.get("verification") or {}
    if v.get("status") == "VERIFIED" and not (v.get("external_check") and v.get("verifier")):
        return _fail("I09", "VERIFIED without an external verifier")
    return _ok("I09")


def check_I10(r):
    disk, audited = r.get("state_hash_on_disk"), r.get("last_audited_state_hash")
    if disk is None and audited is None:
        return _ok("I10", "N/A: no state")
    if disk != audited:
        return _fail("I10", "state on disk differs from last audited state")
    return _ok("I10")


CHECKS = {f"I{n:02d}": globals()[f"check_I{n:02d}"] for n in range(1, 11)}


def enforce(record: dict, ids=None) -> dict:
    results = [CHECKS[i](record) for i in (ids or CHECKS)]
    return {
        "fingerprint": fingerprint(),
        "valid": all(x["passed"] for x in results),
        "results": results,
        "failed": [x["id"] for x in results if not x["passed"]],
    }
