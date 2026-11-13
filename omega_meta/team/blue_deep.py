"""CAPA 2 — Motor Azul Profundo: sintetiza técnica, táctica y riesgo a partir de los roles."""

from __future__ import annotations

from omega_meta.team.knowledge import DOMAINS
from omega_meta.team.models import (
    BlueDeepReport,
    Intent,
    RiskReport,
    RoleAnalysis,
    TacticalReport,
    TechnicalReport,
)
from omega_meta.team.text import clip


def _role(results: dict[str, RoleAnalysis], role_id: str) -> RoleAnalysis | None:
    return results.get(role_id)


def _recs(results: dict[str, RoleAnalysis], role_id: str, n: int = 2) -> list[str]:
    role = _role(results, role_id)
    if not role:
        return []
    return role.recomendaciones[:n]


def _first(items: list[str], fallback: str) -> str:
    return items[0] if items else fallback


class BlueDeepEngine:
    """Usa de verdad los resultados de los agentes; no inventa un reporte genérico."""

    def synthesize(
        self, intent: Intent, agent_results: dict[str, RoleAnalysis]
    ) -> BlueDeepReport:
        domain = DOMAINS.get(intent.dominio, DOMAINS["general"])
        arch = _role(agent_results, "arquitecto_ml")
        data = _role(agent_results, "ingeniero_datos")
        ops = _role(agent_results, "mlops")
        red = _role(agent_results, "red_team")
        prod = _role(agent_results, "estrategia_producto")

        enfoque = arch.resumen if arch else _first(domain["modelos"], "una línea base simple")
        datos_plan = data.resumen if data else _first(domain["datos"], "un pipeline de datos por definir")
        despliegue = ops.resumen if ops else domain["mlops"]

        componentes = [
            "ingesta y validación de features",
            "entrenamiento y evaluación",
            "servicio de inferencia",
            "monitoreo y retraining",
        ]
        if intent.variables:
            componentes.insert(1, "features: " + ", ".join(intent.variables[:4]))

        tecnica = TechnicalReport(
            titulo=f"Plan técnico para {intent.etiqueta_dominio}",
            plan=(
                f"Para el objetivo «{clip(intent.objetivo, 200)}» se integra la propuesta "
                f"del arquitecto ({clip(enfoque, 220)}) con el pipeline de datos "
                f"({clip(datos_plan, 180)}) y el patrón de despliegue ({clip(despliegue, 180)})."
            ),
            enfoque_modelado=clip(enfoque, 400),
            datos_y_pipeline=clip(datos_plan, 400),
            despliegue=clip(despliegue, 400),
            componentes=componentes,
        )

        acciones = []
        for role_id in ("arquitecto_ml", "ingeniero_datos", "mlops", "estrategia_producto"):
            acciones.extend(_recs(agent_results, role_id, 1))
        if not acciones:
            acciones = ["Definir métrica de aceptación y una línea base medible."]

        fases = [
            "1. Formalizar objetivo, restricciones y métrica de aceptación.",
            f"2. Construir el dataset y el split honesto ({intent.etiqueta_dominio}).",
            "3. Entrenar la línea base y un contendiente, compararlos en validación.",
            "4. Desplegar en sombra, monitorear y solo entonces cortar tráfico.",
        ]
        hitos = [
            "Dataset versionado y guía de etiquetado listos",
            "Línea base evaluada en el split acordado",
            "Servicio en sombra con monitoreo de drift y latencia",
            "Decisión de go / no-go contra la métrica de negocio",
        ]
        if intent.restricciones:
            hitos.append("Restricciones verificadas: " + "; ".join(intent.restricciones[:3]))

        tactica = TacticalReport(
            fases=fases,
            acciones_inmediatas=acciones[:6],
            hitos=hitos,
            responsables_sugeridos=[
                "Arquitecto de ML: modelo y métricas",
                "Ingeniero de datos: pipeline y calidad",
                "MLOps: serving, monitoreo y rollback",
                "Producto: perímetro de lanzamiento y umbral de aceptación",
                "Red team: abuso, sesgo y privacidad",
            ],
        )

        riesgos = list(domain["riesgos"])
        if red:
            # incorporar hallazgos del red team que no sean el encabezado
            for item in red.hallazgos + red.recomendaciones:
                if item not in riesgos and not item.lower().startswith("superficie de riesgo"):
                    riesgos.append(item)
        if any("privacidad" in x.lower() or "on-premise" in x.lower() or "on premise" in x.lower() for x in intent.restricciones):
            riesgos.append("Hay una restricción explícita de privacidad o de localidad de los datos que el diseño no puede ignorar.")

        high_impact = intent.dominio in {"salud", "credito", "fraude"}
        if high_impact:
            severidad: str = "alta"
        elif intent.restricciones:
            severidad = "media"
        else:
            severidad = "media" if intent.dominio != "general" else "baja"
        if intent.dominio == "salud":
            severidad = "critica"

        mitigaciones = _recs(agent_results, "red_team", 4)
        if not mitigaciones:
            mitigaciones = ["Evaluar sesgo, privacidad y abuso antes del lanzamiento."]
        if ops:
            mitigaciones.append("Sostener rollback y monitoreo como control operativo de los riesgos residuales.")

        riesgo = RiskReport(
            riesgos=riesgos[:8],
            severidad=severidad,  # type: ignore[arg-type]
            mitigaciones=mitigaciones[:6],
            residual=(
                f"Queda un riesgo residual de severidad {severidad} propio de "
                f"{intent.etiqueta_dominio}: el modelo puede degradarse o usarse fuera de contexto. "
                f"No se elimina; se acota con monitoreo, umbrales y revisión humana donde el impacto lo exige."
            ),
        )

        fragmentos = []
        for role in (arch, data, ops, red, prod):
            if role and role.recomendaciones:
                fragmentos.append(f"{role.rol}: {role.recomendaciones[0]}")
        sintesis = (
            f"Síntesis para «{clip(intent.objetivo, 180)}». "
            + " ".join(fragmentos)
        ).strip()

        return BlueDeepReport(
            tecnica=tecnica,
            tactica=tactica,
            riesgo=riesgo,
            sintesis=sintesis,
        )
