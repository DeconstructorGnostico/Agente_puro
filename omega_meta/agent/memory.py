"""AMM-CORE — memoria del agente.

- VectorMemory: TF-IDF + coseno en Python puro (sin internet ni dependencias). Interfaz
  `add/search` para enchufar FAISS o Chroma si están instalados (no requeridos).
- KV: valores clave-valor.
- StrategyStats: puntuaciones del crítico por (dominio, herramienta) => aprendizaje
  incremental: el planificador prefiere lo que funcionó mejor antes.
- learn_fact: SOLO con evidencia verificada (MEMORY != EVIDENCE; de nexus_agent_v1).
Los logs estructurados van a la auditoría encadenada (L7).
"""
from __future__ import annotations

import json
import math
import threading
from collections import Counter, defaultdict
from pathlib import Path

from omega_meta.core.text import content_tokens


class VectorMemory:
    def __init__(self):
        self.docs: list[dict] = []
        self.df: Counter = Counter()

    def add(self, text: str, meta: dict) -> None:
        toks = Counter(content_tokens(text))
        self.docs.append({"text": text[:500], "meta": meta, "tf": dict(toks)})
        self.df.update(toks.keys())

    def _vec(self, tf: dict) -> dict:
        n = len(self.docs) + 1
        return {t: c * math.log((n + 1) / (self.df.get(t, 0) + 1)) for t, c in tf.items()}

    def search(self, text: str, k: int = 3, min_score: float = 0.05) -> list[dict]:
        q = self._vec(dict(Counter(content_tokens(text))))
        qn = math.sqrt(sum(v * v for v in q.values())) or 1.0
        scored = []
        for d in self.docs:
            v = self._vec(d["tf"])
            dot = sum(q[t] * v.get(t, 0.0) for t in q)
            vn = math.sqrt(sum(x * x for x in v.values())) or 1.0
            s = dot / (qn * vn)
            if s >= min_score:
                scored.append({"score": round(s, 3), "text": d["text"], **d["meta"]})
        return sorted(scored, key=lambda x: -x["score"])[:k]


class AMMCore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.vectors = VectorMemory()
        self.kv: dict = {}
        self.stats: dict = defaultdict(lambda: {"n": 0, "sum": 0.0})
        self.facts: dict = {}
        self._lock = threading.Lock()
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for d in data.get("docs", []):
                self.vectors.add(d["text"], d["meta"])
            self.kv = data.get("kv", {})
            for k, v in data.get("stats", {}).items():
                self.stats[k] = v
            self.facts = data.get("facts", {})

    # -- vectorial
    def store(self, text: str, meta: dict) -> None:
        with self._lock:
            self.vectors.add(text, meta)

    def search(self, text: str, k: int = 3) -> list[dict]:
        return self.vectors.search(text, k)

    # -- aprendizaje incremental por puntuación del crítico
    def record_score(self, domain: str, tool: str, score: float) -> None:
        with self._lock:
            s = self.stats[f"{domain}|{tool}"]
            s["n"] += 1
            s["sum"] += float(score)

    def mean_score(self, domain: str, tool: str) -> float | None:
        s = self.stats.get(f"{domain}|{tool}")
        return s["sum"] / s["n"] if s and s["n"] else None

    # -- hechos: solo con evidencia verificada
    def learn_fact(self, key: str, value, evidence: list[dict]) -> bool:
        if not evidence or not all(e.get("verified") for e in evidence):
            raise PermissionError("MEMORY_WITHOUT_VERIFIED_EVIDENCE")
        with self._lock:
            self.facts[key] = {"value": value, "evidence": [e["id"] for e in evidence]}
        return True

    def save(self) -> None:
        if not self.path:
            return
        with self._lock:
            data = {"docs": [{"text": d["text"], "meta": d["meta"]} for d in self.vectors.docs],
                    "kv": self.kv, "stats": dict(self.stats), "facts": self.facts}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
