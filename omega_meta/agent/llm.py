"""Core LLM local OPCIONAL (Ollama o servidor llama.cpp compatible con OpenAI).

Apagado por defecto: todo funciona sin internet ni modelo. `ContextBuffer` mantiene un
contexto corto (últimos N turnos con presupuesto de caracteres). La salida del modelo
es PROPUESTA: nunca evidencia ni autorización.
"""
from __future__ import annotations

import json
import os
import urllib.request
from collections import deque


class ContextBuffer:
    def __init__(self, max_turns: int = 6, max_chars: int = 4000):
        self.turns: deque = deque(maxlen=max_turns)
        self.max_chars = max_chars

    def add(self, role: str, text: str) -> None:
        self.turns.append({"role": role, "content": text[: self.max_chars // 2]})

    def window(self) -> list[dict]:
        out, total = [], 0
        for t in reversed(self.turns):
            total += len(t["content"])
            if total > self.max_chars:
                break
            out.append(t)
        return list(reversed(out))


class LocalLLM:
    def __init__(self, kind: str = "ollama", model: str | None = None, endpoint: str | None = None, timeout=60.0):
        self.kind = kind
        self.model = model or os.getenv("OMEGA_LLM_MODEL", "llama3.2")
        self.endpoint = endpoint or (os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434/api/chat") if kind == "ollama"
                                     else os.getenv("LLAMACPP_ENDPOINT", "http://127.0.0.1:8080/v1/chat/completions"))
        self.timeout = timeout
        self.buffer = ContextBuffer()

    def complete(self, system: str, user: str) -> str:
        self.buffer.add("user", user)
        msgs = [{"role": "system", "content": system}, *self.buffer.window()]
        payload = {"model": self.model, "messages": msgs, "stream": False}
        req = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read())
        text = data["message"]["content"] if self.kind == "ollama" else data["choices"][0]["message"]["content"]
        self.buffer.add("assistant", text)
        return text
