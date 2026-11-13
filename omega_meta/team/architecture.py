"""CAPA 4 — Arquitectura de agente: componentes, herramientas, memoria y ciclo."""

from __future__ import annotations

from omega_meta.team.knowledge import DOMAINS
from omega_meta.team.models import AgentDesign, BlueDeepReport, Intent, OptimizationResult


class AgentArchitect:
    """Propone un diseño concreto de agente, no un párrafo genérico."""

    def design(
        self,
        intent: Intent,
        report: BlueDeepReport,
        optimization: OptimizationResult,
    ) -> AgentDesign:
        domain = DOMAINS.get(intent.dominio, DOMAINS["general"])
        selected = next(
            (o for o in optimization.opciones if o.id == optimization.seleccionada),
            None,
        )
        selected_name = selected.nombre if selected else optimization.seleccionada

        componentes = [
            "Orquestador que recibe la solicitud y preserva el estado del ciclo",
            "Analizador de intención (objetivo, variables, restricciones, métricas)",
            "Consejo de expertos (arquitecto, datos, MLOps, red team, producto)",
            "Motor de síntesis (reporte técnico, táctico y de riesgo)",
            "Optimizador de opciones (utilidad / costo / riesgo / tiempo)",
            "Verificador independiente que acepta o rechaza el plan",
            "Almacén de estado e historial auditable",
        ]
        if report.riesgo.severidad in {"alta", "critica"}:
            componentes.append("Compuerta humana obligatoria antes de una acción de alto impacto")

        herramientas = list(domain.get("herramientas") or [])
        herramientas.extend(
            [
                "registro de experimentos",
                "evaluador de la métrica de aceptación",
            ]
        )
        if intent.variables:
            herramientas.append("validador de features: " + ", ".join(intent.variables[:4]))
        if any("privacidad" in x.lower() or "gdpr" in x.lower() for x in intent.restricciones) or intent.dominio in {"salud", "credito"}:
            herramientas.append("redactor / minimizador de datos sensibles")
        # unique, preserve order
        seen: set[str] = set()
        tools = []
        for item in herramientas:
            if item not in seen:
                seen.add(item)
                tools.append(item)

        memoria = {
            "episodica": "Historial JSONL de cada corrida (solicitud, decisión, evaluación) para auditoría.",
            "semantica": f"Base de conocimiento de {intent.etiqueta_dominio} (modelos, métricas, riesgos y herramientas).",
            "de trabajo": "Estado de la corrida actual: intención, reportes de roles, opciones y umbrales.",
        }
        if intent.dominio in {"nlp", "recomendacion"}:
            memoria["de recuperacion"] = "Índice de documentos o de ítems para RAG / candidatos, versionado junto al modelo."

        ciclo = [
            "Percibir: leer la solicitud y el contexto operativo",
            "Interpretar: extraer objetivo, variables, restricciones y métricas",
            "Consultar: pedir análisis a los cinco roles",
            "Sintetizar: armar el reporte técnico, táctico y de riesgo",
            "Optimizar: puntuar opciones y elegir un plan",
            "Diseñar: proponer componentes, herramientas, memoria y ciclo del agente objetivo",
            "Verificar: validar calidad, dependencia de la entrada y consistencia",
            "Persistir: guardar el último estado y anexar la corrida al historial",
            "Actuar o detener: solo continuar si la evaluación es VALIDATED",
        ]

        integraciones = [
            "Backend heurístico (sin llaves) o un modelo OpenAI-compatible",
        ]
        if optimization.seleccionada == "api_tercero":
            integraciones.append("Proveedor externo de inferencia, aislado detrás de una capa de control")
        if optimization.seleccionada == "local_compacto":
            integraciones.append("Serving en infraestructura propia (sin ruta crítica hacia una API externa)")
        integraciones.append("Opcional: NRE como compuerta de autorización y verificación antes de ejecutar acciones")

        justificacion = (
            f"El agente se diseña para «{intent.objetivo}» en el dominio "
            f"{intent.etiqueta_dominio}, siguiendo la opción elegida «{selected_name}». "
            f"Las herramientas salen del dominio y de las restricciones {intent.restricciones or ['ninguna explícita']}. "
            f"El ciclo no salta la verificación: si el evaluador rechaza, no hay ejecución."
        )
        nombre = f"Agente de {intent.etiqueta_dominio}"
        return AgentDesign(
            nombre=nombre,
            componentes=componentes,
            herramientas=tools,
            memoria=memoria,
            ciclo=ciclo,
            integraciones=integraciones,
            justificacion=justificacion,
        )
