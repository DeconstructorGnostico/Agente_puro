"""Evaluador de calidad: no basta con que existan las claves."""

from __future__ import annotations

import re

from omega_meta.team.models import (
    AgentDesign,
    BlueDeepReport,
    Evaluation,
    Intent,
    OptimizationResult,
    PipelineResult,
    RoleAnalysis,
)
from omega_meta.team.text import fold, overlap, token_set


_GENERIC_ROLE = re.compile(
    r"^analizar\b.+\bdesde la perspectiva de\b",
    re.IGNORECASE,
)
_GENERIC_STUBS = {
    "reporte tecnico",
    "reporte técnico",
    "reporte táctico",
    "reporte tactico",
    "reporte de riesgo",
}


def _anchors(intent: Intent) -> set[str]:
    parts = [
        intent.objetivo,
        intent.etiqueta_dominio,
        intent.dominio,
        *intent.variables,
        *intent.restricciones,
        *intent.recursos,
        *intent.metricas,
        *intent.palabras_clave,
    ]
    tokens: set[str] = set()
    for part in parts:
        tokens |= token_set(part)
    return tokens


def _text_of_role(role: RoleAnalysis) -> str:
    return " ".join(
        [role.resumen, *role.hallazgos, *role.recomendaciones, *role.evidencias]
    )


def _text_of_report(report: BlueDeepReport) -> str:
    t = report.tecnica
    k = report.tactica
    r = report.riesgo
    return " ".join(
        [
            t.titulo,
            t.plan,
            t.enfoque_modelado,
            t.datos_y_pipeline,
            t.despliegue,
            *t.componentes,
            *k.fases,
            *k.acciones_inmediatas,
            *k.hitos,
            *r.riesgos,
            *r.mitigaciones,
            r.residual,
            report.sintesis,
        ]
    )


def _non_empty_list(items: list, min_items: int = 1) -> bool:
    return len([x for x in items if str(x).strip()]) >= min_items


class Evaluator:
    """Devuelve VALIDATED o REJECTED con razones; las advertencias no rechazan por sí solas."""

    def __init__(self, expected_roles: set[str] | None = None) -> None:
        self.expected_roles = expected_roles

    def evaluate(self, result: PipelineResult) -> Evaluation:
        razones: list[str] = []
        advertencias: list[str] = []
        puntos = 0
        total = 8

        razones.extend(self._check_intent(result.intent))
        razones.extend(self._check_roles(result.intent, result.agent_results))
        razones.extend(self._check_blue_deep(result.intent, result.agent_results, result.blue_deep))
        razones.extend(self._check_optimizer(result.optimizacion, result.blue_deep))
        razones.extend(self._check_architecture(result.arquitectura_agente))
        advertencias.extend(self._consistency_warnings(result))

        # Scoring: one point per major section that produced no rejection reason prefix
        checks = {
            "intención": "intención",
            "roles": "rol ",
            "azul profundo": "azul profundo",
            "reporte técnico": "técnico",
            "táctico": "táctico",
            "riesgo": "riesgo",
            "optimización": "optimización",
            "arquitectura": "arquitectura",
        }
        joined = " ".join(razones).lower()
        for _label, needle in checks.items():
            if needle not in joined:
                puntos += 1

        if not result.solicitud or not result.solicitud.strip():
            razones.append("La solicitud está vacía.")

        estado = "VALIDATED" if not razones else "REJECTED"
        calidad = puntos / total if estado == "VALIDATED" else max(0.0, (puntos - 1) / total)
        if estado == "VALIDATED" and not razones:
            razones = [
                "El plan está completo, depende de la solicitud y es internamente consistente."
            ]
        return Evaluation(
            estado=estado,
            razones=razones,
            advertencias=advertencias,
            puntuacion_calidad=round(calidad, 3),
        )

    def _check_intent(self, intent: Intent) -> list[str]:
        errors = []
        if not intent.objetivo or len(intent.objetivo.strip()) < 8:
            errors.append("La intención no tiene un objetivo utilizable.")
        if not intent.texto_original.strip():
            errors.append("La intención no conserva el texto original de la solicitud.")
        return errors

    def _check_roles(self, intent: Intent, roles: dict[str, RoleAnalysis]) -> list[str]:
        errors = []
        expected = self.expected_roles or {
            "arquitecto_ml",
            "ingeniero_datos",
            "mlops",
            "red_team",
            "estrategia_producto",
        }
        missing = expected - set(roles)
        if missing:
            errors.append(f"Faltan roles en el consejo: {sorted(missing)}.")
            return errors
        anchors = _anchors(intent)
        for role_id, role in roles.items():
            text = _text_of_role(role)
            if not role.resumen or len(role.resumen.strip()) < 20:
                errors.append(f"El rol {role.rol} tiene un resumen vacío o demasiado corto.")
            if not _non_empty_list(role.hallazgos) or not _non_empty_list(role.recomendaciones):
                errors.append(f"El rol {role.rol} no aporta hallazgos o recomendaciones.")
            if _GENERIC_ROLE.search(role.resumen.strip()):
                errors.append(
                    f"El rol {role.rol} devolvió una frase genérica y no un análisis."
                )
            if anchors and not (token_set(text) & anchors):
                errors.append(
                    f"El rol {role.rol} no demuestra dependencia de la solicitud (sin anclas del problema)."
                )
        # Distinctness: all five summaries should not be identical
        summaries = [r.resumen.strip() for r in roles.values()]
        if len(set(summaries)) < min(3, len(summaries)):
            errors.append("Los roles producen resúmenes casi idénticos; el consejo no está diferenciado.")
        return errors

    def _check_blue_deep(
        self,
        intent: Intent,
        roles: dict[str, RoleAnalysis],
        report: BlueDeepReport,
    ) -> list[str]:
        errors = []
        t, k, r = report.tecnica, report.tactica, report.riesgo
        for label, text in (
            ("técnico", t.plan),
            ("técnico", t.enfoque_modelado),
            ("táctico", " ".join(k.fases + k.acciones_inmediatas)),
            ("de riesgo", " ".join(r.riesgos + r.mitigaciones) + " " + r.residual),
        ):
            folded = fold(text)
            if not text or len(text.strip()) < 20:
                errors.append(f"El reporte {label} de Azul Profundo está vacío o es demasiado corto.")
            if folded.strip() in _GENERIC_STUBS:
                errors.append(f"El reporte {label} de Azul Profundo es un stub genérico.")
        if not _non_empty_list(t.componentes, 3):
            errors.append("El plan técnico no lista componentes suficientes.")
        if not _non_empty_list(k.fases, 3) or not _non_empty_list(k.acciones_inmediatas):
            errors.append("El reporte táctico no tiene fases o acciones inmediatas suficientes.")
        if not _non_empty_list(r.riesgos) or not _non_empty_list(r.mitigaciones):
            errors.append("El reporte de riesgo no tiene riesgos o mitigaciones.")
        if r.severidad not in {"baja", "media", "alta", "critica"}:
            errors.append("La severidad de riesgo no es un valor reconocido.")

        # Must use agent results: at least one role recommendation appears in the synthesis or reports
        role_fragments = []
        for role in roles.values():
            role_fragments.extend(role.recomendaciones[:2])
            if role.resumen:
                role_fragments.append(role.resumen)
        report_text = _text_of_report(report)
        used = False
        for fragment in role_fragments:
            piece = fragment.strip()
            if len(piece) >= 24 and piece[:24] in report_text:
                used = True
                break
            if len(token_set(piece)) >= 4 and len(overlap(piece, report_text)) >= 4:
                used = True
                break
        if roles and not used:
            errors.append(
                "Azul Profundo no usa los resultados de los agentes: la síntesis no refleja sus recomendaciones."
            )
        anchors = _anchors(intent)
        if anchors and not (token_set(report_text) & anchors):
            errors.append("El reporte de Azul Profundo no depende de la solicitud.")
        if not report.sintesis or len(report.sintesis) < 30:
            errors.append("Falta una síntesis de Azul Profundo.")
        return errors

    def _check_optimizer(self, opt: OptimizationResult, report: BlueDeepReport) -> list[str]:
        errors = []
        if len(opt.opciones) < 2:
            errors.append("La optimización no propone al menos dos opciones candidatas.")
            return errors
        ids = [o.id for o in opt.opciones]
        if opt.seleccionada not in ids:
            errors.append("La opción seleccionada no está en la lista de candidatas.")
        for option in opt.opciones:
            for name, value in (
                ("utilidad", option.utilidad),
                ("costo", option.costo),
                ("riesgo", option.riesgo),
                ("tiempo", option.tiempo),
                ("puntuacion", option.puntuacion),
            ):
                if not 0.0 <= value <= 1.0:
                    errors.append(f"La opción {option.id} tiene {name} fuera de [0, 1].")
            if not option.nombre or not option.descripcion:
                errors.append(f"La opción {option.id} está incompleta.")
        best = max(opt.opciones, key=lambda o: o.puntuacion)
        if opt.seleccionada in ids and opt.seleccionada != best.id:
            errors.append(
                "La opción seleccionada no es la de mayor puntuación; la decisión no es consistente con el criterio."
            )
        if report.tecnica.titulo and report.tecnica.titulo not in opt.razon and "severidad" not in opt.razon:
            # soft: we just want the optimizer to mention the report
            if report.riesgo.severidad not in opt.razon and report.riesgo.severidad not in opt.criterio:
                errors.append("El optimizador no usa el reporte (no menciona la severidad ni el plan técnico).")
        return errors

    def _check_architecture(self, design: AgentDesign) -> list[str]:
        errors = []
        if not design.nombre:
            errors.append("La arquitectura de agente no tiene nombre.")
        if not _non_empty_list(design.componentes, 3):
            errors.append("La arquitectura no propone componentes suficientes.")
        if not _non_empty_list(design.herramientas, 2):
            errors.append("La arquitectura no lista herramientas suficientes.")
        if not design.memoria:
            errors.append("La arquitectura no describe la memoria del agente.")
        if not _non_empty_list(design.ciclo, 4):
            errors.append("La arquitectura no describe un ciclo de trabajo suficiente.")
        # The loop should include a verification / evaluation step
        cycle_text = fold(" ".join(design.ciclo))
        if "verific" not in cycle_text and "valid" not in cycle_text and "evalu" not in cycle_text:
            errors.append("El ciclo del agente no incluye un paso de verificación.")
        if not design.justificacion or len(design.justificacion) < 30:
            errors.append("La arquitectura no justifica el diseño.")
        return errors

    def _consistency_warnings(self, result: PipelineResult) -> list[str]:
        warnings = []
        text = " ".join(result.intent.restricciones).lower()
        opt = result.optimizacion
        selected = next((o for o in opt.opciones if o.id == opt.seleccionada), None)
        if selected and ("presupuesto" in text or "sin gpu" in text):
            costliest = max(opt.opciones, key=lambda o: o.costo)
            if selected.id == costliest.id:
                warnings.append(
                    "Hay una restricción de presupuesto y se eligió la opción de mayor costo; conviene revisarlo."
                )
        if result.blue_deep.riesgo.severidad in {"alta", "critica"}:
            cycle = fold(" ".join(result.arquitectura_agente.componentes + result.arquitectura_agente.ciclo))
            if "humana" not in cycle and "compuerta" not in cycle and "verific" not in cycle:
                warnings.append(
                    "El riesgo es alto y la arquitectura no deja explícita una compuerta humana o de verificación."
                )
        return warnings
