"""L7 — Persistencia: estado, auditoría JSONL y memoria validada."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def state_hash(state: dict) -> str:
    return hashlib.sha256(
        json.dumps(state, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


class Storage:
    """Almacenamiento en disco. Cada cambio de estado queda auditado (I05/I10)."""

    def __init__(self, root: str | Path = "nre_runtime"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "omega_state.json"
        self.audit_path = self.root / "omega_history.jsonl"
        self.memory_path = self.root / "validated_memory.json"
        self._seq = self._last_seq()
        if not self.memory_path.exists():
            self._write_json(self.memory_path, [])

    # -- archivos -------------------------------------------------------
    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    # -- auditoría ------------------------------------------------------
    def _last_seq(self) -> int:
        if not self.audit_path.exists():
            return 0
        last = 0
        for line in self.audit_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                last = json.loads(line).get("seq", last)
        return last

    def audit(self, event: dict) -> dict:
        self._seq += 1
        record = {"seq": self._seq, "timestamp": datetime.now(timezone.utc).isoformat(), **event}
        with self.audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return record

    def read_audit(self) -> list[dict]:
        if not self.audit_path.exists():
            return []
        return [json.loads(l) for l in self.audit_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    # -- estado ---------------------------------------------------------
    def load_state(self, defaults: dict) -> dict:
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            for key, value in defaults.items():
                state.setdefault(key, value)
            return state
        state = dict(defaults)
        self.save_state(state, reason="INITIALIZE")
        return state

    def save_state(self, state: dict, reason: str) -> str:
        self._write_json(self.state_path, state)
        digest = state_hash(state)
        self.audit({"event": "STATE_SAVED", "reason": reason, "state_hash": digest})
        return digest

    def state_hash_on_disk(self) -> str | None:
        if not self.state_path.exists():
            return None
        return state_hash(json.loads(self.state_path.read_text(encoding="utf-8")))

    def last_audited_state_hash(self) -> str | None:
        for event in reversed(self.read_audit()):
            if event.get("event") == "STATE_SAVED":
                return event["state_hash"]
        return None

    # -- memoria --------------------------------------------------------
    def load_memory(self) -> list[dict]:
        return json.loads(self.memory_path.read_text(encoding="utf-8"))

    def save_memory(self, memory: list[dict]) -> None:
        self._write_json(self.memory_path, memory)
