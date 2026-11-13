"""«Éticamente eficiente» como número: puntaje pre-registrado en docs/EFICIENCIA.md."""
from __future__ import annotations

WEIGHTS = {"S": 0.35, "1-FP": 0.25, "Q": 0.25, "L": 0.10, "C": 0.05}


def efficiency(S: float, FP: float, Q: float, p50_ms: float, loc: int) -> float:
    L = 1 / (1 + p50_ms / 200)
    C = 1 / (1 + loc / 3000)
    return 100 * (0.35 * S + 0.25 * (1 - FP) + 0.25 * Q + 0.10 * L + 0.05 * C)
