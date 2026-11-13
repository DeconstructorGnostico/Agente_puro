"""Router: elige módulos y requisitos de la meta según la petición."""
from __future__ import annotations

import re

from omega_meta.core.text import fold

PLANNING_REQS = {"objetivo", "modelo", "datos", "despliegue", "riesgos", "plan_tactico", "mitigaciones",
                 "decision", "arquitectura", "autoevaluacion"}
SINGLE_REQS = {"objetivo", "modelo", "plan_tactico", "decision", "arquitectura", "autoevaluacion"}
EXPR = re.compile(r"(-?\d+(?:\.\d+)?(?:\s*[-+*/^×÷%]\s*\(?-?\d+(?:\.\d+)?\)?)+)")


def route(objective: str, multi_agent: bool, memory_enabled: bool) -> dict:
    m = EXPR.search(objective.replace(",", ""))
    if m and len(fold(objective).split()) <= 14:
        return {"mode": "calculo", "requirements": {"calculo"}, "expression": m.group(1),
                "modules": ["executor:calculate", "verifier:recompute"]}
    reqs = set(PLANNING_REQS if multi_agent else SINGLE_REQS)
    if memory_enabled:
        reqs.add("antecedentes")
    return {"mode": "multi_agente" if multi_agent else "agente_unico", "requirements": reqs,
            "modules": ["planner", "executor", "critic"] + (["team:5_roles"] if multi_agent else ["team:1_rol"])
            + (["memory"] if memory_enabled else [])}
