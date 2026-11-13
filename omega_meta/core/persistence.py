"""Persistencia versionada con cadena SHA-256 (DGM + Truth State).

Corrige el bug de dgm.py / pure.py: `load()` nunca se llamaba. Aquí el estado aprendido
se CARGA al iniciar, se verifica su cadena de versiones y, si fue manipulado, se vuelve
a la línea base (y se reporta). Escritura atómica con fsync.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

GENESIS = "0" * 64


def atomic_write_json(path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, default=str))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _h(prev: str, payload: dict) -> str:
    return hashlib.sha256((prev + json.dumps(payload, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()


class VersionedState:
    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        self.versions: list[dict] = []

    def commit(self, payload: dict, reason: str) -> dict:
        prev = self.versions[-1]["hash"] if self.versions else GENESIS
        body = {"version": len(self.versions) + 1, "reason": reason, "payload": payload, "previous_hash": prev}
        body["hash"] = _h(prev, {k: v for k, v in body.items() if k != "hash"})
        self.versions.append(body)
        self._save()
        return body

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"versions": self.versions}, ensure_ascii=False))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    @staticmethod
    def verify_chain(versions: list[dict]) -> bool:
        prev = GENESIS
        for v in versions:
            if v.get("previous_hash") != prev or _h(prev, {k: x for k, x in v.items() if k != "hash"}) != v.get("hash"):
                return False
            prev = v["hash"]
        return True

    def load(self) -> dict:
        """Devuelve {status: EMPTY|LOADED|RECOVERED|TAMPERED, payload}.
        RECOVERED => se restauró la última versión cuya cadena verifica; TAMPERED => línea base."""
        if not self.path or not self.path.exists():
            return {"status": "EMPTY", "payload": None}
        try:
            versions = json.loads(self.path.read_text(encoding="utf-8"))["versions"]
        except Exception:  # noqa: BLE001
            return {"status": "TAMPERED", "payload": None}
        if not versions:
            return {"status": "TAMPERED", "payload": None}
        if not self.verify_chain(versions):
            # Axioma 2 (Persistir): volver al ÚLTIMO estado verificado (prefijo válido de la cadena).
            k = 0
            while k < len(versions) and self.verify_chain(versions[: k + 1]):
                k += 1
            if k == 0:
                return {"status": "TAMPERED", "payload": None, "broken_at": 0}
            self.versions = versions[:k]
            self._save()  # se descarta la cola corrupta de forma atómica
            return {"status": "RECOVERED", "payload": versions[k - 1]["payload"], "version": versions[k - 1]["version"],
                    "broken_at": k, "discarded": len(versions) - k}
        self.versions = versions
        return {"status": "LOADED", "payload": versions[-1]["payload"], "version": versions[-1]["version"]}
