"""Pipeline fijo del equipo de 5 roles (compatibilidad con meta_agent_ml; sin persistencia propia)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from omega_meta.team.agents import ExpertCouncil
from omega_meta.team.architecture import AgentArchitect
from omega_meta.team.backend import ModelBackend, resolve_backend
from omega_meta.team.blue_deep import BlueDeepEngine
from omega_meta.team.evaluator import Evaluator
from omega_meta.team.intent import IntentAnalyzer
from omega_meta.team.models import Evaluation, PipelineResult
from omega_meta.team.optimizer import Optimizer


def _run_id(solicitud: str, stamp: str) -> str:
    digest = hashlib.sha256(f"{stamp}|{solicitud}".encode("utf-8")).hexdigest()[:12]
    return f"run_{digest}"


class MetaAgent:
    def __init__(
        self,
        *,
        data_dir: str | Path | None = None,
        backend: ModelBackend | None = None,
        backend_name: str | None = None,
        persist: bool = True,
    ) -> None:
        self.backend = backend or resolve_backend(backend_name)
        self.intent_analyzer = IntentAnalyzer()
        self.council = ExpertCouncil(self.backend)
        self.blue_deep = BlueDeepEngine()
        self.optimizer = Optimizer()
        self.architect = AgentArchitect()
        self.evaluator = Evaluator()
        self.store = None  # la persistencia la hace L7 del Agente Puro

    def run(self, solicitud: str) -> PipelineResult:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        text = (solicitud or "").strip()
        intent = self.intent_analyzer.analyze(text)
        agent_results = self.council.run(intent)
        report = self.blue_deep.synthesize(intent, agent_results)
        optimization = self.optimizer.optimize(intent, report)
        design = self.architect.design(intent, report, optimization)
        result = PipelineResult(
            id=_run_id(text, stamp),
            solicitud=text,
            intent=intent,
            agent_results=agent_results,
            blue_deep=report,
            optimizacion=optimization,
            arquitectura_agente=design,
            evaluacion=Evaluation(estado="REJECTED", razones=["pendiente"]),
            backend=getattr(self.backend, "name", "unknown"),
            creado_en=stamp,
        )
        result.evaluacion = self.evaluator.evaluate(result)
        if self.store is not None:
            self.store.save(result)
        return result


def run(solicitud: str, *, data_dir: str | Path | None = None, backend_name: str | None = None) -> PipelineResult:
    return MetaAgent(data_dir=data_dir, backend_name=backend_name).run(solicitud)
