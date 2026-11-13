"""L5 — Gateway multimodelo y ejecutor con tiempo límite."""

from __future__ import annotations

import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from .text import fold


class ExecutionTimeout(RuntimeError):
    pass


class MockProvider:
    """Proveedor determinista sin modelo real.

    Sin `answers` devuelve un marcador honesto ("no se ejecutó inferencia").
    Con `answers` ({pregunta: respuesta}) simula un modelo que responde
    (correcta o incorrectamente) para pruebas y benchmark.
    """

    name = "mock"

    def __init__(self, answers: dict[str, str] | None = None):
        self.answers = {fold(k): v for k, v in (answers or {}).items()}

    def generate(self, instruction: dict, plan: dict) -> dict:
        key = fold(instruction["objective"])
        if key in self.answers:
            answer = self.answers[key]
            return {"provider": self.name, "facts": [answer], "inferences": [],
                    "unknowns": [], "proposed_solution": answer}
        return {
            "provider": self.name,
            "facts": [],
            "inferences": ["No se ejecutó inferencia de modelo (proveedor mock)."],
            "unknowns": ["No hay evidencia externa disponible."],
            "proposed_solution": "Conecta un proveedor de modelo para procesar el objetivo.",
        }


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str | None = None, endpoint: str | None = None):
        self.model = model or os.getenv("OMEGA_MODEL", "llama3.2")
        self.endpoint = endpoint or os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/chat")

    def generate(self, instruction: dict, plan: dict) -> dict:
        prompt = json.dumps({
            "objective": instruction["objective"],
            "constraints": instruction["constraints"],
            "execution_plan": plan,
            "output_requirements": {"facts": [], "inferences": [], "unknowns": [],
                                    "proposed_solution": ""},
        }, ensure_ascii=False)
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False, "format": "json", "options": {"temperature": 0.1},
        }).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        content = json.loads(data["message"]["content"])
        return {"provider": self.name, "model": self.model, **content}


class ModelGateway:

    def __init__(self, provider=None):
        if provider is None:
            provider = os.getenv("OMEGA_PROVIDER", "mock")
        if isinstance(provider, str):
            if provider == "mock":
                provider = MockProvider()
            elif provider == "ollama":
                provider = OllamaProvider()
            else:
                raise ValueError("UNSUPPORTED_PROVIDER")
        self.provider = provider

    def generate(self, instruction: dict, plan: dict) -> dict:
        return self.provider.generate(instruction, plan)


class Executor:
    """Ejecuta el gateway con tiempo límite. Un timeout se traduce en HALT."""

    def __init__(self, gateway: ModelGateway | None = None, timeout_s: float = 120.0):
        self.gateway = gateway or ModelGateway()
        self.timeout_s = timeout_s

    def run(self, instruction: dict, plan: dict) -> dict:
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(self.gateway.generate, instruction, plan)
        try:
            return future.result(timeout=self.timeout_s)
        except FutureTimeout as exc:
            raise ExecutionTimeout(f"EXECUTION_TIMEOUT after {self.timeout_s}s") from exc
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
