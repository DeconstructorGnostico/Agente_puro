"""CAPA 1 — Consejo de cinco roles expertos, dependiente de la solicitud."""

from __future__ import annotations

import json
from typing import Callable

from meta_agent_ml.backend import HeuristicBackend, ModelBackend, parse_json_content
from meta_agent_ml.knowledge import DOMAINS
from meta_agent_ml.models import Intent, RoleAnalysis
from meta_agent_ml.text import clip


ROLES: list[dict[str, str]] = [
    {
        "id": "arquitecto_ml",
        "rol": "Arquitecto de ML",
        "foco": "familias de modelos, arquitectura, estrategia de entrenamiento y métricas",
    },
    {
        "id": "ingeniero_datos",
        "rol": "Ingeniero de datos",
        "foco": "fuentes, calidad, etiquetado, fugas y diseño del pipeline",
    },
    {
        "id": "mlops",
        "rol": "MLOps",
        "foco": "despliegue, monitoreo, CI/CD, infraestructura y retraining",
    },
    {
        "id": "red_team",
        "rol": "Red team",
        "foco": "riesgos de seguridad, sesgo, privacidad, abuso y mitigaciones",
    },
    {
        "id": "estrategia_producto",
        "rol": "Estrategia de producto",
        "foco": "valor, usuarios, métricas de negocio, adopción y puesta en marcha",
    },
]


def _join(items: list[str]) -> str:
    if not items:
        return "no se declararon"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " y " + items[-1]


def _domain(intent: Intent) -> dict:
    return DOMAINS.get(intent.dominio, DOMAINS["general"])


def _arquitecto(intent: Intent) -> RoleAnalysis:
    d = _domain(intent)
    vars_ = _join(intent.variables) if intent.variables else "las variables que aún hay que inventariar"
    metrics = _join(intent.metricas)
    hallazgos = [
        f"El objetivo declarado es: {intent.objetivo}.",
        f"El problema se encuadra en {intent.etiqueta_dominio}.",
        f"Las variables o señales disponibles incluyen {vars_}.",
        f"Las métricas de referencia para este dominio son {metrics}.",
    ]
    recomendaciones = [f"Probar primero {d['modelos'][0]}."]
    if len(d["modelos"]) > 1:
        recomendaciones.append(f"Si la línea base no alcanza el umbral, escalar a {d['modelos'][1]}.")
    if any("interpretab" in x.lower() or "explicab" in x.lower() for x in intent.restricciones):
        recomendaciones.append(
            "Priorizar un modelo interpretable o añadir reason codes / explicaciones locales."
        )
    if any("latenc" in x.lower() or "tiempo real" in x.lower() for x in intent.restricciones):
        recomendaciones.append(
            "Acotar el presupuesto de inferencia desde el diseño (modelo compacto, destilación o caché)."
        )
    return RoleAnalysis(
        id="arquitecto_ml",
        rol="Arquitecto de ML",
        resumen=(
            f"Para «{clip(intent.objetivo, 160)}» propongo partir de {d['modelos'][0]} "
            f"y medir {intent.metricas[0] if intent.metricas else 'una métrica de tarea clara'}."
        ),
        hallazgos=hallazgos,
        recomendaciones=recomendaciones,
        evidencias=intent.variables[:4] or intent.palabras_clave[:4],
    )


def _ingeniero(intent: Intent) -> RoleAnalysis:
    d = _domain(intent)
    vars_ = _join(intent.variables) if intent.variables else "un inventario de features aún no listado"
    recursos = _join(intent.recursos) if intent.recursos else "fuentes aún no declaradas"
    hallazgos = [
        f"Hay que construir el dataset alrededor de: {vars_}.",
        f"Recursos mencionados: {recursos}.",
        *[clip(item, 220) for item in d["datos"]],
    ]
    recomendaciones = [
        "Definir la unidad de decisión y el instante en que cada feature está realmente disponible.",
        "Separar entrenamiento y validación de forma honesta para este dominio (por tiempo, paciente, cámara o usuario, no al azar si no aplica).",
        "Documentar la guía de etiquetado y medir acuerdo entre anotadores cuando la etiqueta sea humana.",
    ]
    if intent.variables:
        recomendaciones.append(
            f"Validar calidad, nulos y fugas específicamente en {_join(intent.variables[:4])}."
        )
    return RoleAnalysis(
        id="ingeniero_datos",
        rol="Ingeniero de datos",
        resumen=(
            f"El pipeline de datos debe sostener el objetivo «{clip(intent.objetivo, 140)}» "
            f"con {vars_}, sin fugas y con un split acorde a {intent.etiqueta_dominio}."
        ),
        hallazgos=hallazgos,
        recomendaciones=recomendaciones,
        evidencias=intent.variables[:4] or intent.recursos[:4] or intent.palabras_clave[:4],
    )


def _mlops(intent: Intent) -> RoleAnalysis:
    d = _domain(intent)
    restricciones = _join(intent.restricciones) if intent.restricciones else "ninguna restricción explícita de despliegue"
    hallazgos = [
        f"Restricciones operativas declaradas: {restricciones}.",
        f"Patrón de despliegue recomendado para este dominio: {d['mlops']}.",
    ]
    recomendaciones = [
        "Versionar datos, código, preprocesado y modelo como una unidad desplegable.",
        "Monitorear drift de entradas, de la métrica de negocio y de la latencia.",
        "Definir un criterio de rollback y un entorno de sombra antes del tráfico real.",
    ]
    if any("on-premise" in x.lower() or "on premise" in x.lower() or "local" in x.lower() or "sin nube" in x.lower() for x in intent.restricciones):
        recomendaciones.append("Diseñar el serving para infraestructura propia, sin dependencia de APIs externas en la ruta crítica.")
    if any("presupuesto" in x.lower() or "sin gpu" in x.lower() for x in intent.restricciones):
        recomendaciones.append("Dimensionar el serving para CPU o un presupuesto de cómputo bajo: lote, cuantización o modelo compacto.")
    if any("latenc" in x.lower() or "tiempo real" in x.lower() for x in intent.restricciones):
        recomendaciones.append("Incluir presupuesto de latencia (p95) en las pruebas de aceptación del servicio.")
    return RoleAnalysis(
        id="mlops",
        rol="MLOps",
        resumen=(
            f"El sistema que cubre «{clip(intent.objetivo, 140)}» debe desplegarse con "
            f"{d['mlops']} respetando {restricciones}."
        ),
        hallazgos=hallazgos,
        recomendaciones=recomendaciones,
        evidencias=intent.restricciones[:4] or intent.recursos[:4] or intent.palabras_clave[:4],
    )


def _red_team(intent: Intent) -> RoleAnalysis:
    d = _domain(intent)
    hallazgos = [
        f"Superficie de riesgo de {intent.etiqueta_dominio}:",
        *[clip(item, 220) for item in d["riesgos"]],
    ]
    recomendaciones = [
        "Red-teamear el flujo de decisión con casos adversarios y de abuso antes del lanzamiento.",
        "Registrar quién pidió qué, qué decidió el modelo y con qué umbral.",
    ]
    if any("privacidad" in x.lower() or "gdpr" in x.lower() or "datos" in x.lower() for x in intent.restricciones) or intent.dominio in {"salud", "credito", "fraude"}:
        recomendaciones.append("Minimizar datos, controlar acceso y evaluar si hace falta anonimizar o cifrar features sensibles.")
    if intent.dominio in {"salud", "credito"}:
        recomendaciones.append("Tratar este sistema como de alto impacto: revisión humana en casos límite y análisis de sesgo por grupo.")
    if intent.dominio == "nlp":
        recomendaciones.append("Probar inyección de instrucciones en el texto de entrada y exigir citas verificables si hay generación.")
    return RoleAnalysis(
        id="red_team",
        rol="Red team",
        resumen=(
            f"El principal riesgo de «{clip(intent.objetivo, 140)}» está en "
            f"{d['riesgos'][0] if d['riesgos'] else 'un uso no controlado del modelo'}."
        ),
        hallazgos=hallazgos,
        recomendaciones=recomendaciones,
        evidencias=d["riesgos"][:2] + intent.restricciones[:2] + intent.palabras_clave[:2],
    )


def _producto(intent: Intent) -> RoleAnalysis:
    metricas = _join(intent.metricas) if intent.metricas else "una métrica de negocio aún no fijada"
    hallazgos = [
        f"La propuesta de valor debe atarse al objetivo: {intent.objetivo}.",
        f"Las métricas con las que el negocio puede aceptar o rechazar el sistema son {metricas}.",
    ]
    if intent.restricciones:
        hallazgos.append(f"Las restricciones de producto/operación son {_join(intent.restricciones)}.")
    recomendaciones = [
        f"Definir el usuario y la decisión que cambia este sistema para «{clip(intent.objetivo, 120)}», con un umbral de aceptación acordado antes de entrenar.",
        f"Lanzar en un perímetro reducido de {intent.etiqueta_dominio} y comparar contra la línea base actual.",
        f"Traducir {metricas} a un impacto de negocio medible (por ejemplo, quiebre evitado, pérdida evitada o tiempo de atención).",
    ]
    return RoleAnalysis(
        id="estrategia_producto",
        rol="Estrategia de producto",
        resumen=(
            f"El producto que resuelve «{clip(intent.objetivo, 140)}» solo vale si mejora "
            f"{intent.metricas[0] if intent.metricas else 'una decisión de negocio concreta'} "
            f"frente a la operación actual."
        ),
        hallazgos=hallazgos,
        recomendaciones=recomendaciones,
        evidencias=intent.metricas[:3] or intent.palabras_clave[:4],
    )


HEURISTIC_GENERATORS: dict[str, Callable[[Intent], RoleAnalysis]] = {
    "arquitecto_ml": _arquitecto,
    "ingeniero_datos": _ingeniero,
    "mlops": _mlops,
    "red_team": _red_team,
    "estrategia_producto": _producto,
}


_LLM_SYSTEM = (
    "Eres un experto de un consejo de ML. Respondes SOLO con un JSON válido "
    "con las claves: resumen (string), hallazgos (lista de strings), "
    "recomendaciones (lista de strings), evidencias (lista de strings). "
    "El análisis debe depender de la solicitud y de la intención extraída. "
    "Escribe en español, concreto, sin relleno."
)


class ExpertCouncil:
    def __init__(self, backend: ModelBackend | None = None) -> None:
        self.backend = backend or HeuristicBackend()

    def run(self, intent: Intent) -> dict[str, RoleAnalysis]:
        results: dict[str, RoleAnalysis] = {}
        for spec in ROLES:
            results[spec["id"]] = self._analyze_role(spec, intent)
        return results

    def _analyze_role(self, spec: dict[str, str], intent: Intent) -> RoleAnalysis:
        generator = HEURISTIC_GENERATORS[spec["id"]]
        if isinstance(self.backend, HeuristicBackend) or getattr(self.backend, "name", "") == "heuristic":
            return generator(intent)
        try:
            user = (
                f"Rol: {spec['rol']}. Foco: {spec['foco']}.\n"
                f"Solicitud: {intent.texto_original}\n"
                f"Intención: {intent.model_dump_json()}"
            )
            raw = self.backend.complete(_LLM_SYSTEM, user)
            data = parse_json_content(raw)
            return RoleAnalysis(
                id=spec["id"],
                rol=spec["rol"],
                resumen=str(data.get("resumen") or "").strip(),
                hallazgos=list(data.get("hallazgos") or []),
                recomendaciones=list(data.get("recomendaciones") or []),
                evidencias=list(data.get("evidencias") or []),
            )
        except Exception:
            return generator(intent)
