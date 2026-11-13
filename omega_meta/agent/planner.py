"""Planner: descompone la meta en subtareas ejecutables (pasos = herramientas).

- GreedyPlanner: en cada paso toma la herramienta ejecutable con mejor cobertura/costo.
- BestFirstPlanner: búsqueda en árbol best-first (tipo A*) sobre planes parciales;
  f = costo acumulado + h (requisitos faltantes × costo mínimo por requisito), con costos
  ajustados por la memoria (herramientas con mejor puntuación histórica del crítico
  cuestan menos) y por las heurísticas mutables del DGM (`strategy_priors`).
Determinismo parcial: desempates con `random.Random(seed)`.
"""
from __future__ import annotations

import heapq
import itertools
import random

MAX_EXPANSIONS = 4000


def _cost(spec, domain, memory, priors):
    c = spec.cost * float(priors.get(spec.name, 1.0))
    if memory is not None:
        m = memory.mean_score(domain, spec.name)
        if m is not None:
            c *= (1.25 - 0.5 * m)  # mejor historial => más barato
    return c


def _produces(name):
    return {"analyze_intent": "intent", "council_full": "roles", "council_lite": "roles", "single_agent": "roles",
            "blue_deep": "report", "optimize": "optimization", "design_agent": "design", "evaluate": "evaluation",
            "recall_memory": "antecedentes", "calculate": "calc"}.get(name)


class GreedyPlanner:
    name = "greedy"

    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)

    def plan(self, reqs: set, have: set, registry, domain="general", memory=None, priors=None, exclude=()):
        priors = priors or {}
        plan, cov, avail = [], set(have), set(k for k in ("objective",))
        avail |= {k for k in ("intent", "roles", "report", "optimization", "design") if k in have}
        tools = [t for t in registry.tools.values() if not t.side_effect and t.name not in exclude]
        for _ in range(12):
            need = reqs - cov
            if not need:
                break
            cands = []
            for t in tools:
                gain = len(t.covers & need)
                if gain and t.requires <= avail and t.name not in plan:
                    cands.append((-(gain / _cost(t, domain, memory, priors)), self.rng.random(), t))
            if not cands:
                # habilitar dependencias: herramienta ejecutable que produce algo nuevo
                for t in tools:
                    p = _produces(t.name)
                    if t.requires <= avail and p in {"intent", "roles", "report", "optimization", "design"} and p not in avail and t.name not in plan:
                        cands.append((_cost(t, domain, memory, priors), self.rng.random(), t))
                if not cands:
                    break
            cands.sort(key=lambda x: (x[0], x[1]))
            t = cands[0][2]
            plan.append(t.name)
            cov |= t.covers
            if _produces(t.name):
                avail.add(_produces(t.name))
        return plan


class BestFirstPlanner:
    name = "best_first"

    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)

    def plan(self, reqs: set, have: set, registry, domain="general", memory=None, priors=None, exclude=()):
        priors = priors or {}
        tools = [t for t in registry.tools.values() if not t.side_effect and t.name not in exclude]
        costs = {t.name: _cost(t, domain, memory, priors) for t in tools}
        min_c = min(costs.values()) if costs else 1.0
        start_av = frozenset({"objective"} | {k for k in ("intent", "roles", "report", "optimization", "design") if k in have})
        start = (frozenset(have) & frozenset(reqs), start_av, ())
        tie = itertools.count()
        frontier = [(len(reqs - start[0]) * min_c, 0.0, next(tie), start)]
        seen = set()
        best = None
        for _ in range(MAX_EXPANSIONS):
            if not frontier:
                break
            f, g, _, (cov, av, plan) = heapq.heappop(frontier)
            if reqs <= cov:
                return list(plan)
            key = (cov, av)
            if key in seen:
                continue
            seen.add(key)
            if best is None or len(cov) > len(best[0]):
                best = (cov, plan)
            for t in tools:
                if t.name in plan or not t.requires <= av:
                    continue
                p = _produces(t.name)
                ncov = cov | (t.covers & reqs)
                nav = av | ({p} if p else set())
                if ncov == cov and nav == av:
                    continue
                ng = g + costs[t.name]
                h = len(reqs - ncov) * min_c
                heapq.heappush(frontier, (ng + h + 1e-6 * self.rng.random(), ng, next(tie), (ncov, nav, plan + (t.name,))))
        return list(best[1]) if best else []


def make(name: str, seed: int = 7):
    return {"greedy": GreedyPlanner, "best_first": BestFirstPlanner}[name](seed)
