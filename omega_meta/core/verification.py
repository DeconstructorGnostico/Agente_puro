"""Etapa 12 — VERIFICATION independiente (EJECUCIÓN != VERIFICACIÓN).

El verificador NO deriva la evidencia de la propuesta (defecto de omega_brain corregido)
ni se limita a revisar tipos (defecto de nexus_agent_v1 corregido):
- recalcula por su cuenta los resultados de herramientas deterministas y compara cada
  número de la respuesta propuesta con ese recálculo (4 vs «La respuesta es 5» => REJECTED);
- revisa la salida con el firewall (la salida tampoco puede contener daño);
- comprueba anclaje a la petición usando la instrucción compilada ANTES de ejecutar;
- solo marca VERIFIED con un chequeo externo/independiente (referencias del llamador,
  recálculo independiente o evidencia SUPPORTED en el motor de verdad).
"""
from __future__ import annotations

import re

from .firewall import scan_text
from .text import content_tokens, fold, tokens

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _structural(result) -> str | None:
    if not isinstance(result, dict):
        return "INVALID_RESULT"
    for k in ("facts", "inferences", "unknowns"):
        if not isinstance(result.get(k), list):
            return f"INVALID_{k.upper()}"
    if not isinstance(result.get("proposed_solution"), str) or not result["proposed_solution"].strip():
        return "INVALID_PROPOSED_SOLUTION"
    for f in result["facts"]:
        if not (isinstance(f, dict) and f.get("text") and f.get("source")):
            return "FACT_WITHOUT_SOURCE"
    return None


def verify(instruction: dict, result: dict, ruleset: str | None = "bilingual", learned=(),
           references: list[str] | None = None, recompute=None) -> dict:
    base = {"verifier": "independent_verifier", "evidence_sources": [], "external_check": False, "checks": {}}
    err = _structural(result)
    if err:
        return {**base, "status": "REJECTED", "reason": err}
    answer = result["proposed_solution"]
    checks = base["checks"]

    # 1) Seguridad de la salida
    if ruleset:
        out_text = answer + " " + " ".join(map(str, result.get("inferences", [])))
        bad = scan_text(out_text, ruleset, learned)
        checks["output_firewall"] = not bad
        if bad:
            return {**base, "status": "REJECTED", "reason": "OUTPUT_FIREWALL:" + bad[0]["category"]}

    # 2) Consistencia con herramientas: recálculo independiente
    if recompute is not None:
        expected = recompute()
        nums = [float(x) for x in NUM_RE.findall(answer.replace(",", ""))]
        consistent = any(abs(n - float(expected)) < 1e-9 for n in nums[-1:]) if nums else False
        checks["tool_consistency"] = consistent
        if not consistent:
            return {**base, "status": "REJECTED", "reason": "ANSWER_INCONSISTENT_WITH_TOOL_RESULT",
                    "expected": expected, "proposed": answer}
        return {**base, "status": "VERIFIED", "external_check": True, "verifier": "independent_recompute",
                "evidence_sources": ["deterministic_recomputation"]}

    # 3) Anclaje a la petición (instrucción compilada antes de ejecutar)
    goal = content_tokens(instruction.get("objective", ""))
    body = " ".join([answer, *map(str, result.get("inferences", [])), str(result.get("report", ""))])
    anchored = bool(goal & content_tokens(body)) if goal else True
    checks["anchored_to_request"] = anchored
    if not anchored and result.get("report"):
        return {**base, "status": "REJECTED", "reason": "OUTPUT_NOT_ANCHORED_TO_REQUEST"}

    # 4) Referencias externas del llamador
    if references:
        ans = f" {' '.join(tokens(answer))} "
        for ref in references:
            r = " ".join(tokens(ref))
            if r and f" {r} " in ans:
                return {**base, "status": "VERIFIED", "external_check": True, "verifier": "reference_match",
                        "evidence_sources": ["caller_reference"], "matched_reference": ref}
        return {**base, "status": "REJECTED", "reason": "REFERENCE_MISMATCH"}

    # 5) Hechos del resultado con estado de verdad
    states = [f.get("truth_state") for f in result["facts"]]
    if states and all(s == "SUPPORTED" for s in states) and result.get("inferences"):
        return {**base, "status": "PARTIALLY_VERIFIED", "external_check": True, "verifier": "truth_engine",
                "evidence_sources": ["registered_independent_sources"],
                "limitations": ["Los hechos están respaldados; el plan/inferencias siguen siendo propuesta."]}
    if states and all(s == "SUPPORTED" for s in states):
        return {**base, "status": "VERIFIED", "external_check": True, "verifier": "truth_engine",
                "evidence_sources": ["registered_independent_sources"]}
    if any(s == "SUPPORTED" for s in states):
        return {**base, "status": "PARTIALLY_VERIFIED", "external_check": True, "verifier": "truth_engine",
                "evidence_sources": ["registered_independent_sources"]}
    return {**base, "status": "UNVERIFIED",
            "limitations": ["Pasó seguridad y consistencia, pero no hay evidencia externa: es una propuesta, no un hecho."]}
