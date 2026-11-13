"""Backend de modelo enchufable: heurístico (por defecto) u OpenAI-compatible."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class ModelBackend(Protocol):
    name: str

    def complete(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        ...


class HeuristicBackend:
    """No llama a ningún modelo. Las capas usan generadores deterministas."""

    name = "heuristic"

    def complete(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        # El consejo de expertos no depende de este método; se expone para
        # conservar una interfaz única y para pruebas.
        return f"[heuristic] {user[:200]}"


@dataclass
class OpenAICompatBackend:
    """Cliente mínimo de /chat/completions (OpenAI, xAI u otro compatible)."""

    api_key: str
    base_url: str
    model: str
    timeout: float = 45.0
    name: str = "openai_compat"

    @classmethod
    def from_env(cls) -> "OpenAICompatBackend":
        key = (
            os.environ.get("META_AGENT_API_KEY")
            or os.environ.get("XAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()
        if not key:
            raise RuntimeError(
                "No hay llave de API. Define META_AGENT_API_KEY, XAI_API_KEY o OPENAI_API_KEY."
            )
        if os.environ.get("META_AGENT_BASE_URL"):
            base = os.environ["META_AGENT_BASE_URL"].rstrip("/")
        elif os.environ.get("XAI_BASE_URL"):
            base = os.environ["XAI_BASE_URL"].rstrip("/")
        elif os.environ.get("OPENAI_BASE_URL"):
            base = os.environ["OPENAI_BASE_URL"].rstrip("/")
        elif os.environ.get("XAI_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
            base = "https://api.x.ai/v1"
        else:
            base = "https://api.openai.com/v1"
        model = (
            os.environ.get("META_AGENT_MODEL")
            or os.environ.get("XAI_MODEL")
            or os.environ.get("OPENAI_MODEL")
            or ("grok-4" if "x.ai" in base else "gpt-4o-mini")
        )
        return cls(api_key=key, base_url=base, model=model)

    def complete(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"El proveedor de modelos respondió {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"No se pudo contactar al proveedor de modelos: {exc}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Respuesta de modelo inesperada: {body!r}") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("El modelo devolvió una respuesta vacía.")
        return content.strip()


def api_key_present() -> bool:
    return bool(
        os.environ.get("META_AGENT_API_KEY")
        or os.environ.get("XAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )


def resolve_backend(name: str | None = None) -> ModelBackend:
    """Elige el backend. Por defecto: heurístico, salvo que haya llave y mode=auto."""
    mode = (name or os.environ.get("META_AGENT_BACKEND") or "heuristic").strip().lower()
    if mode in {"heuristic", "offline", "local"}:
        return HeuristicBackend()
    if mode in {"openai", "openai_compat", "llm", "xai"}:
        return OpenAICompatBackend.from_env()
    if mode == "auto":
        if api_key_present():
            return OpenAICompatBackend.from_env()
        return HeuristicBackend()
    raise ValueError(f"Backend desconocido: {mode}")


def parse_json_content(text: str) -> dict[str, Any]:
    """Extrae el primer objeto JSON de una respuesta de modelo."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop fence
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(text[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("No se encontró un objeto JSON en la respuesta del modelo.")
