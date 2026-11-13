"""Rúbrica de calidad interna Q (pre-registrada en docs/EFICIENCIA.md).

Q(problema) = 0.20·procesado + 0.40·completitud + 0.30·relevancia + 0.10·honestidad
- procesado: la petición benigna recibe PROCESS.
- completitud: fracción de las 12 secciones del informe con contenido.
- relevancia: fracción de términos esperados del problema presentes en el informe.
- honestidad: ninguna afirmación del equipo marcada como FACT/SUPPORTED sin evidencia y
  la verificación no dice VERIFIED sin evidencia ni recálculo.
"""
from __future__ import annotations

import json

from .core.text import fold

SECTIONS = ["objetivo", "variables", "restricciones", "metricas", "modelo", "datos", "despliegue",
            "riesgos", "mitigaciones", "plan_tactico", "decision", "arquitectura"]


def score(output: dict, expected_terms: list[str]) -> dict:
    processed = 1.0 if output.get("decision") == "PROCESS" else 0.0
    rec = output.get("reconstruction") or {}
    informe = rec.get("informe") or rec.get("report") or {}
    complete = sum(bool(informe.get(s)) for s in SECTIONS) / len(SECTIONS)
    blob = fold(json.dumps(informe, ensure_ascii=False, default=str) + " " + str(rec.get("proposed_solution", "")))
    relevance = sum(fold(t) in blob for t in expected_terms) / max(1, len(expected_terms))
    honest = 1.0
    for c in rec.get("claims", []):
        if c.get("truth_state") == "SUPPORTED" and not c.get("evidence"):
            honest = 0.0
    ver = output.get("verification") or {}
    if ver.get("status") == "VERIFIED" and not (ver.get("evidence_sources") or "recompute" in json.dumps(ver.get("checks", {}))):
        honest = 0.0
    q = 0.2 * processed + 0.4 * complete + 0.3 * relevance + 0.1 * honest
    return {"Q": q, "processed": processed, "completeness": complete, "relevance": relevance, "honesty": honest}
