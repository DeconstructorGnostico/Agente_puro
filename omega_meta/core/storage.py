"""L7 — Persistencia: estado, historial de peticiones (incluye rechazos) y auditoría."""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from .audit import AuditLog


def state_hash(state: dict) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Storage:
    """`runtime_dir=None` => todo en memoria (útil para evaluación y pruebas)."""

    def __init__(self, runtime_dir: str | Path | None = "omega_runtime"):
        self.root = Path(runtime_dir) if runtime_dir else None
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)
        self.audit = AuditLog(self.root / "audit.jsonl" if self.root else None)
        self._lock = threading.Lock()
        self._history: list[dict] = []
        self._state: dict | None = None

    # -- historial: TODA petición queda registrada, también los rechazos del firewall
    def append_history(self, item: dict) -> None:
        with self._lock:
            if self.root:
                with (self.root / "history.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
            else:
                self._history.append(item)

    def history(self) -> list[dict]:
        if not self.root:
            return list(self._history)
        p = self.root / "history.jsonl"
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    # -- estado (estadísticas; NO contiene interruptores de apagado permanente)
    def load_state(self, defaults: dict) -> dict:
        if self.root and (self.root / "state.json").exists():
            st = json.loads((self.root / "state.json").read_text(encoding="utf-8"))
            for k, v in defaults.items():
                st.setdefault(k, v)
            return st
        return dict(defaults)

    def save_state(self, state: dict, reason: str) -> str:
        digest = state_hash(state)
        if self.root:
            tmp = self.root / "state.json.tmp"
            tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.root / "state.json")
        self._state = dict(state)
        self.audit.record("STATE_SAVED", reason=reason, state_hash=digest)
        return digest

    def state_hash_on_disk(self) -> str | None:
        if self.root and (self.root / "state.json").exists():
            return state_hash(json.loads((self.root / "state.json").read_text(encoding="utf-8")))
        return state_hash(self._state) if self._state is not None else None
