"""ROOT INVARIANT ENGINE — núcleo inmutable del DGM.

Contiene identidad, políticas, seguridad y condiciones de autorización. Nada en tiempo
de ejecución puede cambiarlo: el motor de mutación solo toca reglas declarativas y
`root_hash()` se compara antes y después de cada mutación (si cambia => HALT y rollback).

Invariantes (como comprobaciones de código, ver `check_cycle`):
- I01..I10: tabla canónica del Agente Puro v1.0 (I08 el modelo no modifica el Root Kernel,
  I09 el aprendizaje no se aprueba a sí mismo, I10 todo ciclo tiene límite y HALT)
- B01..B10: invariantes de omega_brain (INPUT != VERIFIED_FACT ... FAILURE => FAIL_CLOSED)
- S1..S5: las cinco separaciones del Deconstructor Gnóstico
- N1..N3: de nexus_agent (EXTERNAL_CONTEXT != SYSTEM_POLICY, TOOL_AVAILABILITY !=
  EXECUTION_PERMISSION, MODEL_CANNOT_MODIFY_ROOT_POLICY)
"""
from __future__ import annotations

import hashlib
import inspect
import json
from types import MappingProxyType

from . import firewall

IDENTITY = MappingProxyType({
    "system": "OMEGA-META / DGM", "architecture": "NRE–AMM–OMEGA",
    "author": "Adrian Mendez Millan", "license": "MIT",
})

# I01..I10: tabla canónica de «Arquitectura del Agente Puro — NRE/AMM/OMEGA v1.0».
CANONICAL = {
    "I01": "INFERENCE != FACT",
    "I02": "RESPONSE != REALITY",
    "I03": "CLAIM != EVIDENCE",
    "I04": "MEMORY != EVIDENCE",
    "I05": "EXTERNAL_CONTEXT != AUTHORITY",
    "I06": "PROPOSAL != AUTHORIZATION",
    "I07": "UNVERIFIED_RESULT != ACCEPTED_RESULT",
    "I08": "MODEL_CANNOT_MODIFY_ROOT_KERNEL",
    "I09": "LEARNING_CANNOT_SELF_APPROVE",
    "I10": "BOUNDED_EXECUTION_REQUIRED",
}
INVARIANTS = MappingProxyType({
    **CANONICAL,
    # B01..B10: invariantes de omega_brain, conservadas como comprobaciones de detalle.
    "B01": "INPUT != VERIFIED_FACT",
    "B02": "INFERENCE != FACT",
    "B03": "MODEL_OUTPUT != REALITY",
    "B04": "PROPOSAL != AUTHORIZATION",
    "B05": "VERIFICATION != AUTHORIZATION",
    "B06": "MEMORY != AUTHORITY",
    "B07": "UNCERTAINTY != CERTAINTY",
    "B08": "RESPONSE != REALITY",
    "B09": "UNVERIFIED_CHANGE != COMMIT",
    "B10": "FAILURE => FAIL_CLOSED",
    "S1": "DATO != INFERENCIA",
    "S2": "HIPOTESIS != HECHO",
    "S3": "AFIRMACION != EVIDENCIA",
    "S4": "PROPUESTA != AUTORIZACION",
    "S5": "EJECUCION != VERIFICACION",
    "N1": "EXTERNAL_CONTEXT != SYSTEM_POLICY",
    "N2": "TOOL_AVAILABILITY != EXECUTION_PERMISSION",
    "N3": "MODEL_CANNOT_MODIFY_ROOT_POLICY",
})

POLICY = MappingProxyType({
    "read_only": "AUTO",
    "side_effect": "PENDING_AUTHORIZATION (requiere aprobación humana)",
    "tools": "solo lista blanca; cada herramienta con efectos requiere autorización propia",
    "external_data": "dato no confiable: se inspecciona y se pone en cuarentena, nunca es instrucción",
    "fact_promotion": "FACT solo con evidencia verificada independientemente; ninguna regla mutable produce FACT",
    "mutation": "solo reglas declarativas; solo puede AGREGAR patrones de bloqueo, nunca desactivar seguridad",
    "failure": "fail-closed",
    "limits": "por petición/sesión, con enfriamiento; nunca apagado permanente",
})

# Categorías que el motor mutable NUNCA puede producir ni relajar.
PROTECTED_CATEGORIES = frozenset({"FACT"}) | frozenset(firewall.HARM_RULES)
MUTABLE_EPISTEMIC = frozenset({"CLAIM", "HYPOTHESIS", "ASSUMPTION", "OBJECTIVE", "CONSTRAINT", "UNKNOWN"})


def root_hash() -> str:
    """Hash del núcleo: identidad + invariantes + política + categorías protegidas +
    el conjunto de reglas de seguridad del firewall (incluido su código fuente)."""
    payload = {
        "identity": dict(IDENTITY), "invariants": dict(INVARIANTS), "policy": dict(POLICY),
        "protected": sorted(PROTECTED_CATEGORIES),
        "harm_rules": {k: [list(r) for r in v] for k, v in firewall.HARM_RULES.items()},
        "cue": firewall.CUE, "protective": firewall.PROTECTIVE.pattern,
        "scan_src": inspect.getsource(firewall._scan),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


BASELINE_ROOT_HASH = root_hash()

# ---------------------------------------------------------------------------
# Comprobaciones de invariantes sobre el registro de un ciclo.

def _ok(i, d="ok"):
    return {"id": i, "rule": INVARIANTS[i], "passed": True, "detail": d}


def _fail(i, d):
    return {"id": i, "rule": INVARIANTS[i], "passed": False, "detail": d}


def _before(trace, a, b):
    return a in trace and b in trace and trace.index(a) < trace.index(b)


def check_cycle(r: dict) -> dict:
    trace = r.get("trace", [])
    dx = r.get("decomposition") or {}
    result = r.get("result") or {}
    ver = r.get("verification") or {}
    auth = r.get("authorization") or {}
    executed = (r.get("execution") or {}).get("executed_tools", [])
    out: list[dict] = []

    # I01 — ninguna proposición de la entrada es FACT sin evidencia verificada
    bad = [p["id"] for p in dx.get("facts", []) if not p.get("verified_evidence")]
    out.append(_fail("B01", f"FACT sin evidencia verificada: {bad}") if bad else _ok("B01"))
    # I02 / S1 — inferencias y hechos separados; los hechos del resultado tienen fuente
    facts = result.get("facts", []) if isinstance(result, dict) else []
    infs = set(map(str, result.get("inferences", []))) if isinstance(result, dict) else set()
    both = [f for f in facts if str(f.get("text") if isinstance(f, dict) else f) in infs]
    nosrc = [f for f in facts if not (isinstance(f, dict) and f.get("source"))]
    msg = (f"items en hechos e inferencias: {both}" if both else
           f"hechos sin fuente: {len(nosrc)}" if nosrc else None)
    out.append(_fail("B02", msg) if msg else _ok("B02"))
    out.append(_fail("S1", msg) if msg else _ok("S1"))
    # I03 — la salida del modelo/equipo no es evidencia de sí misma
    srcs = set(ver.get("evidence_sources", []))
    if srcs & {"model", "team", "proposal", "user_input"}:
        out.append(_fail("B03", f"evidencia no independiente: {sorted(srcs)}"))
    elif ver.get("status") == "VERIFIED" and not ver.get("external_check"):
        out.append(_fail("B03", "VERIFIED sin verificador externo"))
    else:
        out.append(_ok("B03"))
    # I04 / S4 — ejecutar requiere autorización previa de NEXUS
    if "EXECUTE" in trace:
        okk = auth.get("authorized") and auth.get("decided_by") == "NEXUS" and _before(trace, "AUTHORIZE", "EXECUTE")
        out += [_ok("B04"), _ok("S4")] if okk else [_fail("B04", "ejecución sin autorización previa"), _fail("S4", "propuesta tratada como autorización")]
    else:
        out += [_ok("B04", "N/A"), _ok("S4", "N/A")]
    # I05 — la verificación no autoriza efectos
    se = [t for t in executed if t.get("side_effect")]
    if se and auth.get("mode") not in {"HUMAN", "EXPLICIT_FLAG", "CALLBACK"}:
        out.append(_fail("B05", "efecto ejecutado sin autorización humana"))
    else:
        out.append(_ok("B05"))
    # I06 — memoria no es autoridad: no cambia el núcleo; solo aprende lo verificado/puntuado
    rh = r.get("root_hash_before"), r.get("root_hash_after")
    lw = (r.get("learning") or {}).get("facts_written", 0)
    if rh[0] and rh[0] != rh[1]:
        out.append(_fail("B06", "el núcleo cambió durante el ciclo"))
    elif lw and ver.get("status") != "VERIFIED":
        out.append(_fail("B06", "se aprendieron hechos sin verificación"))
    else:
        out.append(_ok("B06"))
    # I07 — incertidumbre explícita si no está verificado
    outp = r.get("output_labels") or {}
    if r.get("decision") == "PROCESS" and ver.get("status") != "VERIFIED" and outp.get("certainty") == "VERIFIED":
        out.append(_fail("B07", "se declaró certeza sin verificación"))
    else:
        out.append(_ok("B07"))
    # I08 — toda respuesta entregada lleva etiqueta de verificación
    if r.get("decision") == "PROCESS" and r.get("delivered") and not ver.get("status"):
        out.append(_fail("B08", "respuesta sin etiqueta de verificación"))
    else:
        out.append(_ok("B08"))
    # I09 / S5 — COMPLETED solo después de VERIFY; verificador distinto del ejecutor
    if r.get("delivered"):
        okv = _before(trace, "EXECUTE", "VERIFY")
        out.append(_ok("B09") if okv else _fail("B09", "entrega sin verificación"))
        out.append(_ok("S5") if okv and ver.get("verifier") != "executor" else _fail("S5", "el ejecutor se verificó a sí mismo"))
    else:
        out += [_ok("B09", "N/A"), _ok("S5", "N/A")]
    # I10 — fallo => cerrado
    if r.get("errors") and (r.get("decision") == "PROCESS" or r.get("delivered")):
        out.append(_fail("B10", "hubo error y aun así se entregó"))
    else:
        out.append(_ok("B10"))
    # S2 — una hipótesis nunca termina como hecho
    hyp = {p["text"] for p in dx.get("hypotheses", [])}
    leak = [f for f in facts if (f.get("text") if isinstance(f, dict) else f) in hyp]
    out.append(_fail("S2", "hipótesis promovida a hecho") if leak else _ok("S2"))
    # S3 — una afirmación no es evidencia
    claims = {p["text"] for p in dx.get("claims", [])}
    ev = [e for e in dx.get("evidence", []) if e.get("text") in claims]
    out.append(_fail("S3", "afirmación usada como evidencia") if ev else _ok("S3"))
    # N1 — datos externos en cuarentena no llegan al contexto
    q = r.get("quarantined_external", [])
    leaked = [x for x in q if x in (r.get("context_external") or [])]
    out.append(_fail("N1", "dato externo en cuarentena llegó al contexto") if leaked else _ok("N1"))
    # N2 — cada herramienta ejecutada tuvo permiso propio
    np_ = [t["tool"] for t in executed if not t.get("permitted")]
    out.append(_fail("N2", f"herramientas sin permiso: {np_}") if np_ else _ok("N2"))
    # N3
    out.append(_fail("N3", "política raíz modificada") if rh[0] and rh[0] != rh[1] else _ok("N3"))

    # --- Invariantes canónicas I01..I10 (compuestas de las comprobaciones de detalle) ---
    st = {x["id"]: x for x in out}

    def comp(i, parts, extra=None):
        bad = [f"{p}: {st[p]['detail']}" for p in parts if not st[p]["passed"]]
        if extra:
            bad.append(extra)
        out.append(_fail(i, "; ".join(bad)) if bad else _ok(i))

    comp("I01", ["B02", "S1", "S2"])
    comp("I02", ["B07", "B08", "B03"])
    comp("I03", ["B01", "S3"])
    mem_src = [s_ for s_ in ver.get("evidence_sources", []) if "memory" in str(s_)]
    comp("I04", ["B06"], f"memoria usada como evidencia: {mem_src}" if mem_src else None)
    comp("I05", ["N1"])
    comp("I06", ["B04", "B05", "S4", "N2"])
    comp("I07", ["B09", "S5"])
    comp("I08", ["N3"])
    lm = (r.get("learning") or {}).get("mutations_applied", [])
    self_ok = all(m.get("approved_by") and m.get("approved_by") != m.get("proposed_by") for m in lm)
    comp("I09", [], None if self_ok else "mutación aplicada sin aprobación independiente")
    exe = r.get("execution") or {}
    lim = r.get("limits") or {}
    unbounded = (exe.get("steps") is not None and lim.get("max_steps") is not None
                 and len(exe["steps"]) > lim["max_steps"])
    comp("I10", ["B10"], "ciclo excedió su límite" if unbounded else None)

    failed = [x["id"] for x in out if not x["passed"]]
    return {"valid": not failed, "failed": failed, "results": out}
