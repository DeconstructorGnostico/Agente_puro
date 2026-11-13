"""L7 — Auditoría encadenada con SHA-256 (audit.jsonl).

Cada registro guarda `previous_hash` y `hash = sha256(previous_hash + json canónico)`.
Cambiar, borrar o reordenar una línea rompe la cadena y `verify_audit` lo detecta.
Detecta manipulación; NO es almacenamiento inmutable (quien controla el disco puede
reescribir toda la cadena). El último hash se mantiene en memoria: no se relee el
archivo completo en cada escritura (defecto de omega_brain.py corregido).
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def _canonical(record: dict) -> str:
    return json.dumps(record, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def _digest(previous_hash: str, body: dict) -> str:
    return hashlib.sha256((previous_hash + _canonical(body)).encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self.memory: list[dict] = []  # si path es None, se audita en memoria
        self.seq = 0
        self.last_hash = GENESIS
        self.tampered: dict | None = None   # registro manipulado => escrituras bloqueadas
        self.blocked_writes = 0
        self._fp = None
        if self.path and self.path.exists():
            # Integridad ENTRE corridas: al iniciar se verifica la cadena completa.
            v = verify_audit(self.path)
            if not v["valid"]:
                self.tampered = {"reason": v["reason"], "broken_at": v["broken_at"], "detected": "startup"}
            last = None
            with self.path.open("rb") as fh:
                for line in fh:
                    if line.strip():
                        last = line
            if last and not self.tampered:
                rec = json.loads(last)
                self.seq, self.last_hash = rec["seq"], rec["hash"]
            self._fp = self._fingerprint()

    def _fingerprint(self):
        st = self.path.stat()
        return (st.st_size, st.st_mtime_ns)

    def intact(self) -> bool:
        """Comprobación barata en cada petición: si el archivo cambió fuera de este proceso
        (tamaño o mtime), se verifica la cadena completa y que termine en nuestro último hash."""
        if self.tampered:
            return False
        if not self.path:
            return True
        if not self.path.exists():
            if self.seq:
                self.tampered = {"reason": "AUDIT_LOG_DELETED", "broken_at": 0, "detected": "runtime"}
                return False
            return True
        if self._fp is not None and self._fingerprint() == self._fp:
            return True
        v = verify_audit(self.path)
        ents = self.entries()
        if not v["valid"] or (ents and ents[-1].get("hash") != self.last_hash) or (not ents and self.seq):
            self.tampered = {"reason": v["reason"] or "UNEXPECTED_EXTERNAL_WRITE", "broken_at": v["broken_at"],
                             "detected": "runtime"}
            return False
        self._fp = self._fingerprint()
        return True

    def record(self, event: str, **payload) -> dict:
        with self._lock:
            if self.path and not self.intact():
                self.blocked_writes += 1  # nunca se escribe sobre un registro manipulado
                return {"blocked": True, "event": event, "reason": "AUDIT_LOG_TAMPERED"}
            self.seq += 1
            body = {"seq": self.seq, "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": event, "previous_hash": self.last_hash, **payload}
            body["hash"] = _digest(self.last_hash, body)
            self.last_hash = body["hash"]
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(body, ensure_ascii=False, default=str) + "\n")
                    fh.flush()
                self._fp = self._fingerprint()
            else:
                self.memory.append(body)
            return body

    def entries(self) -> list[dict]:
        if not self.path:
            return list(self.memory)
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]


def verify_audit(source: AuditLog | str | Path) -> dict:
    """Recalcula la cadena completa. Devuelve {valid, entries, broken_at, reason}."""
    if isinstance(source, AuditLog):
        entries = source.entries()
    else:
        p = Path(source)
        entries = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []
    previous = GENESIS
    for i, rec in enumerate(entries):
        body = {k: v for k, v in rec.items() if k != "hash"}
        if rec.get("previous_hash") != previous:
            return {"valid": False, "entries": len(entries), "broken_at": i, "reason": "PREVIOUS_HASH_MISMATCH"}
        if _digest(previous, body) != rec.get("hash"):
            return {"valid": False, "entries": len(entries), "broken_at": i, "reason": "HASH_MISMATCH"}
        previous = rec["hash"]
    return {"valid": True, "entries": len(entries), "broken_at": None, "reason": None}
