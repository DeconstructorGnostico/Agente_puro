import json
from unittest.mock import patch, MagicMock

import pytest

from omega_meta.team.backend import (
    HeuristicBackend,
    OpenAICompatBackend,
    api_key_present,
    parse_json_content,
    resolve_backend,
)


def test_default_backend_is_heuristic(monkeypatch):
    monkeypatch.delenv("META_AGENT_BACKEND", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("META_AGENT_API_KEY", raising=False)
    backend = resolve_backend()
    assert isinstance(backend, HeuristicBackend)
    assert backend.name == "heuristic"


def test_auto_without_keys_is_heuristic(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("META_AGENT_API_KEY", raising=False)
    backend = resolve_backend("auto")
    assert isinstance(backend, HeuristicBackend)


def test_openai_without_keys_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("META_AGENT_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        resolve_backend("openai")


def test_from_env_uses_xai_defaults(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("META_AGENT_BASE_URL", raising=False)
    monkeypatch.delenv("META_AGENT_MODEL", raising=False)
    monkeypatch.delenv("XAI_BASE_URL", raising=False)
    monkeypatch.delenv("XAI_MODEL", raising=False)
    backend = OpenAICompatBackend.from_env()
    assert backend.base_url == "https://api.x.ai/v1"
    assert backend.model == "grok-4"
    assert backend.api_key == "test-key"


def test_openai_compat_request_shape(monkeypatch):
    captured = {}

    class DummyResp:
        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "hola desde el modelo"}}]
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["body"] = json.loads(request.data.decode())
        return DummyResp()

    backend = OpenAICompatBackend(
        api_key="secret",
        base_url="https://example.test/v1",
        model="demo-model",
    )
    with patch("omega_meta.team.backend.urllib.request.urlopen", side_effect=fake_urlopen):
        text = backend.complete("sys", "user-msg")
    assert text == "hola desde el modelo"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["body"]["model"] == "demo-model"
    assert captured["body"]["messages"][1]["content"] == "user-msg"
    assert "secret" in str(captured["headers"].get("authorization", ""))


def test_parse_json_content_from_fenced_block():
    raw = "```json\n{\"resumen\": \"ok\", \"hallazgos\": []}\n```"
    data = parse_json_content(raw)
    assert data["resumen"] == "ok"
