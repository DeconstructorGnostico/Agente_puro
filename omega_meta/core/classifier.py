"""Hook opcional para un clasificador aprendido (apagado por defecto).

- `ollama`: Llama Guard vía Ollama local (OLLAMA_ENDPOINT, OMEGA_GUARD_MODEL=llama-guard3).
- `openai_moderation`: endpoint /moderations compatible con OpenAI (OPENAI_API_KEY).
Si el clasificador no está disponible, se reporta `available: False` y el firewall de
reglas sigue decidiendo (el hook es consultivo; `fail_closed=True` bloquea si falla).
"""
from __future__ import annotations

import json
import os
import urllib.request


class NoClassifier:
    name = "none"

    def classify(self, text: str) -> dict:
        return {"available": False, "name": self.name, "unsafe": None}


class OllamaGuard:
    name = "ollama_llama_guard"

    def __init__(self, model=None, endpoint=None, timeout=10.0):
        self.model = model or os.getenv("OMEGA_GUARD_MODEL", "llama-guard3")
        self.endpoint = endpoint or os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434/api/chat")
        self.timeout = timeout

    def classify(self, text: str) -> dict:
        body = json.dumps({"model": self.model, "stream": False,
                           "messages": [{"role": "user", "content": text}]}).encode()
        try:
            req = urllib.request.Request(self.endpoint, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = json.loads(r.read())["message"]["content"].strip().lower()
            return {"available": True, "name": self.name, "unsafe": out.startswith("unsafe"), "raw": out[:80]}
        except Exception as e:  # noqa: BLE001
            return {"available": False, "name": self.name, "unsafe": None, "error": type(e).__name__}


class OpenAIModeration:
    name = "openai_moderation"

    def __init__(self, timeout=10.0):
        self.key = os.getenv("OPENAI_API_KEY", "")
        self.base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    def classify(self, text: str) -> dict:
        if not self.key:
            return {"available": False, "name": self.name, "unsafe": None, "error": "NO_API_KEY"}
        try:
            req = urllib.request.Request(f"{self.base}/moderations", data=json.dumps({"input": text}).encode(),
                                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.key}"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                res = json.loads(r.read())["results"][0]
            return {"available": True, "name": self.name, "unsafe": bool(res["flagged"])}
        except Exception as e:  # noqa: BLE001
            return {"available": False, "name": self.name, "unsafe": None, "error": type(e).__name__}


def resolve(name: str | None):
    if not name or name == "none":
        return NoClassifier()
    if name == "ollama":
        return OllamaGuard()
    if name == "openai_moderation":
        return OpenAIModeration()
    raise ValueError(f"clasificador desconocido: {name}")
