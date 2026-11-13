"""CAPA 3 — Optimizador: puntúa opciones candidatas según utilidad, costo, riesgo y tiempo."""

from __future__ import annotations

from omega_meta.team.models import (
    BlueDeepReport,
    CandidateOption,
    Intent,
    OptimizationResult,
)


SEVERITY_RISK = {"baja": 0.25, "media": 0.45, "alta": 0.7, "critica": 0.85}


def _weights(intent: Intent, report: BlueDeepReport) -> dict[str, float]:
    # utilidad / (costo + riesgo + tiempo), expresado como pesos que suman 1
    w = {"utilidad": 0.45, "costo": 0.20, "riesgo": 0.20, "tiempo": 0.15}
    text = " ".join(intent.restricciones).lower()
    if "presupuesto" in text or "sin gpu" in text or "barato" in text:
        w["costo"] += 0.12
        w["utilidad"] -= 0.06
        w["tiempo"] -= 0.06
    if "latenc" in text or "tiempo real" in text:
        w["tiempo"] += 0.10
        w["utilidad"] -= 0.05
        w["costo"] -= 0.05
    if report.riesgo.severidad in {"alta", "critica"} or "privacidad" in text or "regulator" in text:
        w["riesgo"] += 0.12
        w["utilidad"] -= 0.07
        w["costo"] -= 0.05
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def _score(utilidad: float, costo: float, riesgo: float, tiempo: float, w: dict[str, float]) -> float:
    """Puntuación en [0, 1]: utilidad ponderada menos penalizaciones de costo/riesgo/tiempo."""
    raw = (
        utilidad * w["utilidad"]
        + (1 - costo) * w["costo"]
        + (1 - riesgo) * w["riesgo"]
        + (1 - tiempo) * w["tiempo"]
    )
    return round(min(1.0, max(0.0, raw)), 4)


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


class Optimizer:
    """Genera opciones concretas y elige la de mejor puntuación según el reporte."""

    def optimize(self, intent: Intent, report: BlueDeepReport) -> OptimizationResult:
        base_risk = SEVERITY_RISK[report.riesgo.severidad]
        constrained = " ".join(intent.restricciones).lower()
        tight_budget = "presupuesto" in constrained or "sin gpu" in constrained
        tight_latency = "latenc" in constrained or "tiempo real" in constrained
        on_prem = "on-premise" in constrained or "on premise" in constrained or "sin nube" in constrained or "local" in constrained

        options_spec = [
            {
                "id": "linea_base",
                "nombre": "Línea base simple y medible",
                "descripcion": (
                    "Modelo sencillo, pipeline mínimo y evaluación honesta. "
                    "Sirve de piso y de control frente a cualquier propuesta más cara."
                ),
                "utilidad": 0.55,
                "costo": 0.25,
                "riesgo": _clip01(base_risk - 0.15),
                "tiempo": 0.30,
            },
            {
                "id": "equilibrio",
                "nombre": "Contendiente de equilibrio",
                "descripcion": (
                    "Línea base más un modelo de mayor capacidad, con monitoreo y umbral de aceptación. "
                    "Escala la complejidad solo si gana en validación."
                ),
                "utilidad": 0.80,
                "costo": 0.50,
                "riesgo": _clip01(base_risk - 0.05),
                "tiempo": 0.55,
            },
            {
                "id": "avanzado",
                "nombre": "Sistema avanzado de extremo a extremo",
                "descripcion": (
                    "Arquitectura completa, entrenamiento costoso y automatización amplia. "
                    "Máxima utilidad potencial, mayor costo, más superficie de riesgo y más tiempo."
                ),
                "utilidad": 0.95,
                "costo": 0.85,
                "riesgo": _clip01(base_risk + 0.15),
                "tiempo": 0.85,
            },
        ]

        if on_prem or "privacidad" in constrained:
            options_spec.append(
                {
                    "id": "local_compacto",
                    "nombre": "Modelo compacto en infraestructura propia",
                    "descripcion": (
                        "Serving local o on-premise, modelo compacto o destilado, sin API externa en la ruta crítica."
                    ),
                    "utilidad": 0.70,
                    "costo": 0.55,
                    "riesgo": _clip01(base_risk - 0.10),
                    "tiempo": 0.60,
                }
            )
        else:
            options_spec.append(
                {
                    "id": "api_tercero",
                    "nombre": "API o modelo de terceros + capa propia",
                    "descripcion": (
                        "Usar un proveedor externo para la inferencia y concentrar el esfuerzo en datos, "
                        "guardrails y la decisión de negocio. Rápido de arrancar; costo recurrente y dependencia."
                    ),
                    "utilidad": 0.68,
                    "costo": 0.60,
                    "riesgo": _clip01(base_risk + 0.10),
                    "tiempo": 0.35,
                }
            )

        if tight_budget:
            for spec in options_spec:
                if spec["id"] in {"avanzado", "api_tercero"}:
                    spec["costo"] = _clip01(spec["costo"] + 0.08)
        if tight_latency:
            for spec in options_spec:
                if spec["id"] in {"avanzado", "api_tercero"}:
                    spec["tiempo"] = _clip01(spec["tiempo"] + 0.05)
                if spec["id"] in {"linea_base", "local_compacto"}:
                    spec["utilidad"] = _clip01(spec["utilidad"] + 0.04)

        weights = _weights(intent, report)
        opciones: list[CandidateOption] = []
        for spec in options_spec:
            puntuacion = _score(spec["utilidad"], spec["costo"], spec["riesgo"], spec["tiempo"], weights)
            justificacion = (
                f"utilidad={spec['utilidad']:.2f}, costo={spec['costo']:.2f}, "
                f"riesgo={spec['riesgo']:.2f}, tiempo={spec['tiempo']:.2f} → "
                f"puntuación {puntuacion:.3f}"
            )
            opciones.append(CandidateOption(justificacion=justificacion, puntuacion=puntuacion, **spec))

        best = max(opciones, key=lambda o: (o.puntuacion, -o.costo, -o.riesgo))
        criterio = (
            "puntuación = utilidad·w_u + (1-costo)·w_c + (1-riesgo)·w_r + (1-tiempo)·w_t, "
            f"con pesos { {k: round(v, 3) for k, v in weights.items()} } "
            f"ajustados a las restricciones y a la severidad {report.riesgo.severidad} del reporte de riesgo."
        )
        razon = (
            f"Se elige «{best.nombre}» porque obtiene la mejor puntuación ({best.puntuacion:.3f}) "
            f"dado el reporte de riesgo (severidad {report.riesgo.severidad}) "
            f"y las restricciones {intent.restricciones or ['ninguna explícita']}. "
            f"Plan técnico de referencia: {report.tecnica.titulo}."
        )
        return OptimizationResult(
            opciones=opciones,
            seleccionada=best.id,
            criterio=criterio,
            razon=razon,
        )
