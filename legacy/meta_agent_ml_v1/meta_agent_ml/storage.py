"""Persistencia: último estado en JSON y historial que se anexa en JSONL."""

from __future__ import annotations

import json
from pathlib import Path

from meta_agent_ml.models import PipelineResult


class StateStore:
    """Conserva el último estado y anexa cada corrida al historial. No borra el pasado."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data_dir / "state.json"
        self.history_path = self.data_dir / "history.jsonl"

    def save(self, result: PipelineResult) -> None:
        payload = result.model_dump(mode="json")
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        self.state_path.write_text(text + "\n", encoding="utf-8")
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def load_last(self) -> PipelineResult | None:
        if not self.state_path.exists():
            return None
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        return PipelineResult.model_validate(data)

    def load_history(self) -> list[PipelineResult]:
        if not self.history_path.exists():
            return []
        items: list[PipelineResult] = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            items.append(PipelineResult.model_validate(json.loads(line)))
        return items

    def history_length(self) -> int:
        if not self.history_path.exists():
            return 0
        return sum(1 for line in self.history_path.read_text(encoding="utf-8").splitlines() if line.strip())
