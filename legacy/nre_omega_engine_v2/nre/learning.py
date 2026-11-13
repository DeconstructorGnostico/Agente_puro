"""Controlador de aprendizaje selectivo: solo resultados VERIFIED, reversible."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .storage import Storage


class LearningController:

    def __init__(self, storage: Storage):
        self.storage = storage

    def process(self, instruction: dict, result: dict, verification: dict) -> dict:
        if verification.get("status") != "VERIFIED":
            self.storage.audit({"event": "LEARNING_SKIPPED", "intent_id": instruction["intent_id"],
                                "status": verification.get("status")})
            return {"written": False, "reason": "ONLY_VERIFIED_RESULTS_ARE_LEARNED"}
        entry = {
            "entry_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "intent_id": instruction["intent_id"],
            "objective": instruction["objective"],
            "answer": result["proposed_solution"],
            "verifier": verification.get("verifier"),
        }
        memory = self.storage.load_memory()
        memory.append(entry)
        self.storage.save_memory(memory)
        self.storage.audit({"event": "LEARNING_WRITTEN", "entry_id": entry["entry_id"],
                            "intent_id": instruction["intent_id"]})
        return {"written": True, "entry_id": entry["entry_id"]}

    def rollback(self, entry_id: str) -> bool:
        memory = self.storage.load_memory()
        kept = [m for m in memory if m["entry_id"] != entry_id]
        if len(kept) == len(memory):
            return False
        self.storage.save_memory(kept)
        self.storage.audit({"event": "LEARNING_ROLLBACK", "entry_id": entry_id})
        return True

    def entries(self) -> list[dict]:
        return self.storage.load_memory()
