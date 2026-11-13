"""Ciclo autónomo ACOTADO: meta -> plan -> por paso: ejecutar, puntuar (crítico),
guardar en memoria; si la puntuación < umbral o el plan se agota sin cumplir la meta,
replanificar y USAR el plan nuevo.

Correcciones al pseudocódigo del usuario: el plan replanificado reemplaza los pasos
restantes (antes se sobreescribía y se perdía), no hay `while True` (máximo de pasos y
de replanificaciones), se detiene al cumplir la meta y termina en HALT si se agota el
presupuesto sin cumplirla.
"""
from __future__ import annotations

import time

from . import critic
from .tools import ToolDenied


def run(goal_reqs: set, ctx: dict, registry, planner, permit, memory=None, priors=None,
        max_steps: int = 14, max_replans: int = 3, timeout_s: float = 30.0, audit=None) -> dict:
    t0 = time.monotonic()
    domain = "general"

    def have():
        return critic.covered(ctx) | set(ctx)

    plan = planner.plan(goal_reqs, have(), registry, domain, memory, priors)
    plans = [list(plan)]
    steps, executed = [], []
    errored: dict[str, int] = {}  # una herramienta que falla 2 veces se excluye (1 reintento)
    weak: dict[str, frozenset] = {}  # herramienta pobre -> cobertura en ese momento
    replans, status = 0, None
    for i in range(max_steps):  # ciclo ACOTADO (sin while True)
        if time.monotonic() - t0 > timeout_s:
            status = "HALT_TIMEOUT"
            break
        if goal_reqs <= critic.covered(ctx):
            status = "GOAL_SATISFIED"
            break
        if not plan:
            if replans >= max_replans:
                status = "HALT_REPLAN_BUDGET"
                break
            replans += 1
            cov = frozenset(critic.covered(ctx))
            excl = {n for n, k in errored.items() if k >= 2} | {n for n, c in weak.items() if c == cov}
            plan = planner.plan(goal_reqs, have(), registry, domain, memory, priors, exclude=excl)
            plans.append(list(plan))
            if not plan:
                status = "HALT_NO_PLAN"
                break
        name = plan.pop(0)
        spec = registry.tools.get(name)
        err, out = None, None
        try:
            out = registry.execute(name, {}, ctx, permit)
            executed.append({"tool": name, "permitted": True, "side_effect": bool(spec and spec.side_effect)})
        except ToolDenied as e:
            err = f"DENIED:{e}"
        except Exception as e:  # noqa: BLE001 — una herramienta rota no tumba el ciclo
            err = f"ERROR:{type(e).__name__}:{e}"
        if ctx.get("intent") is not None:
            domain = ctx["intent"].dominio
        sc = critic.score_step(spec, ctx, err, goal_reqs) if spec else {"score": 0.0, "replan": True, "error": err}
        steps.append({"step": i + 1, "tool": name, "output": out, **sc})
        if memory is not None:
            memory.record_score(domain, name, sc["score"])
        if audit:
            audit.record("LOOP_STEP", tool=name, score=sc["score"], error=err, request_id=ctx.get("request_id"))
        if err:
            errored[name] = errored.get(name, 0) + 1
        elif sc.get("replan"):
            weak[name] = frozenset(critic.covered(ctx))
        if (err or sc.get("replan")) and replans < max_replans:
            replans += 1
            cov = frozenset(critic.covered(ctx))
            excl = {n for n, k in errored.items() if k >= 2} | {n for n, c in weak.items() if c == cov}
            new_plan = planner.plan(goal_reqs, have(), registry, domain, memory, priors, exclude=excl)
            if new_plan and new_plan != plan:
                plan = new_plan  # el plan nuevo SE USA (el pseudocódigo original lo perdía)
                plans.append(list(new_plan))
            elif not err:
                plans.append(list(plan))  # sin alternativa mejor: se continúa con lo restante
            else:
                plan = new_plan
                plans.append(list(new_plan))
    if status is None:
        status = "GOAL_SATISFIED" if goal_reqs <= critic.covered(ctx) else "HALT_MAX_STEPS"
    return {"status": status, "steps": steps, "plans": plans, "replans": replans,
            "executed_tools": executed, "goal_score": critic.goal_score(goal_reqs, ctx),
            "covered": sorted(goal_reqs & critic.covered(ctx)), "missing": sorted(goal_reqs - critic.covered(ctx))}
