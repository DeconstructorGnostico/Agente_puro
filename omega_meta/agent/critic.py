"""Critic: puntuación objetiva por paso, detección de desviación y señal de replanificación.

La puntuación de un paso = fracción de los requisitos que la herramienta declaró cubrir
y que de verdad quedaron cubiertos en el pizarrón (comprobaciones concretas, no el texto
del propio paso). Si la salida no comparte ningún término con el objetivo => desviación.
"""
from __future__ import annotations

from omega_meta.core.text import content_tokens

THRESHOLD = 0.6


def _roles(ctx):
    return ctx.get("roles") or {}


CHECKS = {
    "objetivo": lambda c: bool(c.get("intent")) and len(c["intent"].objetivo) >= 8,
    "variables": lambda c: bool(c.get("intent")),
    "restricciones": lambda c: bool(c.get("intent")),
    "modelo": lambda c: "arquitecto_ml" in _roles(c) and bool(_roles(c)["arquitecto_ml"].recomendaciones),
    "datos": lambda c: "ingeniero_datos" in _roles(c) and bool(_roles(c)["ingeniero_datos"].recomendaciones),
    "despliegue": lambda c: "mlops" in _roles(c) and bool(_roles(c)["mlops"].recomendaciones),
    "riesgos": lambda c: "red_team" in _roles(c) and bool(_roles(c)["red_team"].hallazgos),
    "producto": lambda c: "estrategia_producto" in _roles(c),
    "plan_tactico": lambda c: bool(c.get("report")) and len(c["report"].tactica.acciones_inmediatas) >= 2,
    "mitigaciones": lambda c: bool(c.get("report")) and len(c["report"].riesgo.mitigaciones) >= 1
                     and ("red_team" in _roles(c)),
    "decision": lambda c: bool(c.get("optimization")) and c["optimization"].seleccionada in {o.id for o in c["optimization"].opciones},
    "arquitectura": lambda c: bool(c.get("design")) and len(c["design"].componentes) >= 4 and len(c["design"].ciclo) >= 6,
    "autoevaluacion": lambda c: bool(c.get("evaluation")) and c["evaluation"].estado == "VALIDATED",
    "antecedentes": lambda c: "antecedentes" in c,
    "calculo": lambda c: "calc" in c,
}


def covered(ctx: dict) -> set[str]:
    out = set()
    for req, fn in CHECKS.items():
        try:
            if fn(ctx):
                out.add(req)
        except Exception:  # noqa: BLE001
            pass
    return out


def _anchored(ctx: dict) -> bool:
    goal = content_tokens(ctx.get("objective", ""))
    if not goal or not ctx.get("intent"):
        return True
    i = ctx["intent"]
    text = " ".join([i.objetivo, i.etiqueta_dominio, *i.variables, *i.restricciones])
    return bool(goal & content_tokens(text))


def score_step(spec, ctx: dict, error: str | None = None, goal: set | None = None) -> dict:
    if error:
        return {"score": 0.0, "deviation": False, "error": error, "satisfied": [], "replan": True}
    cov = covered(ctx)
    target = (spec.covers & goal) if goal and (spec.covers & goal) else spec.covers
    sat = sorted(target & cov)
    score = len(sat) / max(1, len(target))
    deviation = not _anchored(ctx)
    if deviation:
        score *= 0.5
    return {"score": round(score, 3), "deviation": deviation, "satisfied": sat,
            "replan": score < THRESHOLD}


def goal_score(requirements: set[str], ctx: dict) -> float:
    return round(len(requirements & covered(ctx)) / max(1, len(requirements)), 3)
