"""MUTABLE RULE ENGINE — la ÚNICA parte del sistema que puede cambiar.

Reglas declarativas (palabra clave validada por regex + categoría + prioridad):
- epistemológicas: clasifican proposiciones (OBJECTIVE, HYPOTHESIS, ...);
- de firewall aprendidas: `FIREWALL_BLOCK:<CATEGORIA>`, solo AGREGAN bloqueos;
- heurísticas del planificador: `strategy_priors` (pesos por herramienta).

Corrección del bug crítico de dgm.py: ninguna regla puede tener categoría FACT ni una
categoría protegida, y no existe operación para desactivar reglas de seguridad.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field

from . import root
from .truth import TRUTH_DEFAULTS, guard_truth_params
from .text import fold

MAX_RULES = 100
KEYWORD_RE = re.compile(r"[a-z0-9áéíóúüñ _'\-]{2,60}", re.IGNORECASE)
FIREWALL_PREFIX = "FIREWALL_BLOCK:"


class RuleViolation(Exception):
    pass


@dataclass
class Rule:
    rule_id: str
    keyword: str
    category: str
    priority: int = 1
    enabled: bool = True
    origin: str = "baseline"  # baseline | learned
    version: int = 1


# Base inicial (incluye las 5 reglas de dgm.py y el clasificador del Deconstructor).
BASELINE = [
    Rule("R001", "hipótesis", "HYPOTHESIS"), Rule("R002", "supongo", "ASSUMPTION"),
    Rule("R003", "objetivo", "OBJECTIVE", priority=2), Rule("R004", "restricción", "CONSTRAINT"),
    Rule("R005", "desconocido", "UNKNOWN"), Rule("R006", "suponiendo que", "HYPOTHESIS"),
    Rule("R007", "podría ser", "HYPOTHESIS"), Rule("R008", "posiblemente", "HYPOTHESIS"),
    Rule("R009", "suponemos", "ASSUMPTION"), Rule("R010", "asumimos", "ASSUMPTION"),
    Rule("R011", "se presupone", "ASSUMPTION"), Rule("R012", "meta", "OBJECTIVE"),
    Rule("R013", "propósito", "OBJECTIVE"), Rule("R014", "quiero", "OBJECTIVE"),
    Rule("R015", "necesito", "OBJECTIVE"), Rule("R016", "límite", "CONSTRAINT"),
    Rule("R017", "debe cumplirse", "CONSTRAINT"), Rule("R018", "prohibido", "CONSTRAINT"),
    Rule("R019", "no sabemos", "UNKNOWN"), Rule("R020", "se desconoce", "UNKNOWN"),
    Rule("R021", "hypothesis", "HYPOTHESIS"), Rule("R022", "goal", "OBJECTIVE"),
    Rule("R023", "constraint", "CONSTRAINT"), Rule("R024", "unknown", "UNKNOWN"),
    Rule("R025", "presupuesto", "CONSTRAINT"), Rule("R026", "latencia", "CONSTRAINT"),
]
BASELINE_PRIORS = {"council_full": 1.0, "council_lite": 1.0, "single_agent": 1.0}


def _allowed_category(cat: str) -> bool:
    if cat in root.MUTABLE_EPISTEMIC:
        return True
    if cat.startswith(FIREWALL_PREFIX):
        return cat[len(FIREWALL_PREFIX):] in root.PROTECTED_CATEGORIES - {"FACT"}
    return False


@dataclass
class RuleBase:
    rules: list[Rule] = field(default_factory=lambda: copy.deepcopy(BASELINE))
    strategy_priors: dict = field(default_factory=lambda: dict(BASELINE_PRIORS))
    version: int = 1
    truth_params: dict = field(default_factory=lambda: dict(TRUTH_DEFAULTS))

    def validate(self) -> None:
        if len(self.rules) > MAX_RULES:
            raise RuleViolation("RULE_LIMIT_EXCEEDED")
        ids = set()
        for r in self.rules:
            if r.rule_id in ids:
                raise RuleViolation("DUPLICATE_RULE_ID")
            ids.add(r.rule_id)
            if r.category == "FACT" or not _allowed_category(r.category):
                raise RuleViolation(f"FORBIDDEN_CATEGORY:{r.category}")
            if not KEYWORD_RE.fullmatch(r.keyword):
                raise RuleViolation("INVALID_KEYWORD")
            if r.category.startswith(FIREWALL_PREFIX) and not r.enabled:
                raise RuleViolation("SAFETY_RULE_CANNOT_BE_DISABLED")
        if not guard_truth_params(self.truth_params):
            raise RuleViolation("TRUTH_PARAMS_VIOLATE_GUARD")
        for k, v in self.strategy_priors.items():
            if not (0.5 <= float(v) <= 2.0):
                raise RuleViolation("PRIOR_OUT_OF_RANGE")

    # -- clasificación epistemológica (prioridad; empate de categorías => UNKNOWN)
    def classify(self, text: str) -> str:
        t = fold(text)
        hits = [r for r in self.rules if r.enabled and not r.category.startswith(FIREWALL_PREFIX)
                and re.search(r"(?<![a-z0-9])" + re.escape(fold(r.keyword)) + r"(?![a-z0-9])", t)]
        if not hits:
            return "CLAIM"  # una afirmación sin evidencia NUNCA es FACT
        top = max(r.priority for r in hits)
        cats = {r.category for r in hits if r.priority == top}
        return cats.pop() if len(cats) == 1 else "UNKNOWN"

    def learned_firewall(self) -> list[tuple[str, str]]:
        return [(r.category[len(FIREWALL_PREFIX):], r.keyword) for r in self.rules
                if r.enabled and r.category.startswith(FIREWALL_PREFIX)]

    def next_id(self) -> str:
        return f"R{max(int(r.rule_id[1:]) for r in self.rules) + 1:03d}"

    def snapshot(self) -> dict:
        return {"rules": [asdict(r) for r in self.rules], "strategy_priors": dict(self.strategy_priors),
                "version": self.version, "truth_params": dict(self.truth_params)}

    @classmethod
    def from_snapshot(cls, snap: dict) -> "RuleBase":
        rb = cls([Rule(**r) for r in snap["rules"]], dict(snap["strategy_priors"]), snap.get("version", 1),
                 dict(snap.get("truth_params") or TRUTH_DEFAULTS))
        rb.validate()
        return rb

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.snapshot(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
