"""Orquestación de las capas del meta-agente."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from meta_agent_ml.agents import ExpertCouncil
from meta_agent_ml.architecture import AgentArchitect
from meta_agent_ml.backend import ModelBackend, resolve_backend
from meta_agent_ml.blue_deep import BlueDeepEngine
from meta_agent_ml.evaluator import Evaluator
from meta_agent_ml.intent import IntentAnalyzer
from meta_agent_ml.models import Evaluation, PipelineResult
from meta_agent_ml.optimizer import Optimizer
from meta_agent_ml.storage import StateStore


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
        self.store = StateStore(data_dir) if persist else None

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
