"""Modelos Pydantic del meta-agente."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Intent(BaseModel):
    objetivo: str
    dominio: str
    etiqueta_dominio: str
    variables: list[str] = Field(default_factory=list)
    restricciones: list[str] = Field(default_factory=list)
    recursos: list[str] = Field(default_factory=list)
    metricas: list[str] = Field(default_factory=list)
    palabras_clave: list[str] = Field(default_factory=list)
    texto_original: str


class RoleAnalysis(BaseModel):
    rol: str
    id: str
    resumen: str
    hallazgos: list[str] = Field(default_factory=list)
    recomendaciones: list[str] = Field(default_factory=list)
    evidencias: list[str] = Field(default_factory=list)

    @field_validator("resumen")
    @classmethod
    def resumen_no_vacio(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("el resumen del rol no puede estar vacío")
        return value.strip()


class TechnicalReport(BaseModel):
    titulo: str
    plan: str
    enfoque_modelado: str
    datos_y_pipeline: str
    despliegue: str
    componentes: list[str] = Field(default_factory=list)


class TacticalReport(BaseModel):
    fases: list[str] = Field(default_factory=list)
    acciones_inmediatas: list[str] = Field(default_factory=list)
    hitos: list[str] = Field(default_factory=list)
    responsables_sugeridos: list[str] = Field(default_factory=list)


class RiskReport(BaseModel):
    riesgos: list[str] = Field(default_factory=list)
    severidad: Literal["baja", "media", "alta", "critica"] = "media"
    mitigaciones: list[str] = Field(default_factory=list)
    residual: str = ""


class BlueDeepReport(BaseModel):
    tecnica: TechnicalReport
    tactica: TacticalReport
    riesgo: RiskReport
    sintesis: str


class CandidateOption(BaseModel):
    id: str
    nombre: str
    descripcion: str
    utilidad: float
    costo: float
    riesgo: float
    tiempo: float
    puntuacion: float
    justificacion: str


class OptimizationResult(BaseModel):
    opciones: list[CandidateOption] = Field(default_factory=list)
    seleccionada: str
    criterio: str
    razon: str


class AgentDesign(BaseModel):
    nombre: str
    componentes: list[str] = Field(default_factory=list)
    herramientas: list[str] = Field(default_factory=list)
    memoria: dict[str, str] = Field(default_factory=dict)
    ciclo: list[str] = Field(default_factory=list)
    integraciones: list[str] = Field(default_factory=list)
    justificacion: str


class Evaluation(BaseModel):
    estado: Literal["VALIDATED", "REJECTED"]
    razones: list[str] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
    puntuacion_calidad: float = 0.0


class PipelineResult(BaseModel):
    id: str
    solicitud: str
    intent: Intent
    agent_results: dict[str, RoleAnalysis]
    blue_deep: BlueDeepReport
    optimizacion: OptimizationResult
    arquitectura_agente: AgentDesign
    evaluacion: Evaluation
    backend: str
    creado_en: str
