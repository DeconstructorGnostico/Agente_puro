"""Nombres de componentes de la especificación de aceptación (fachadas finas sobre el núcleo).

| Nombre de la especificación | Implementación |
|---|---|
| ZeroTrustRoot              | L0 `core/root.py` (hash raíz, invariantes, check_cycle) |
| InputInspector             | L1+L2 `compile_instruction` + `core/firewall.py::validate` |
| ProvenanceEngine           | L4 `core/truth.py::TruthEngine` (procedencia, orígenes, revisores) |
| GnosticContradictionEngine | L3 `core/deconstructor.py` (negación, valores, evidencia en conflicto) |
| OmegaGuard                 | NEXUS `core/nexus.py` (autorización + límites por sesión) |
"""
from __future__ import annotations

from . import deconstructor, firewall, root
from .nexus import AuthorizationPolicy, SessionGuard
from .rules import RuleBase
from .truth import TruthEngine


class ZeroTrustRoot:
    invariants = root.INVARIANTS
    baseline = root.BASELINE_ROOT_HASH

    @staticmethod
    def hash() -> str:
        return root.root_hash()

    @classmethod
    def verify(cls) -> bool:
        return root.root_hash() == cls.baseline

    @staticmethod
    def check(record: dict) -> dict:
        return root.check_cycle(record)


class InputInspector:
    def __init__(self, ruleset: str = "bilingual"):
        self.config = firewall.FirewallConfig(ruleset)

    def inspect(self, text: str, external_data=None) -> dict:
        from .engine import compile_instruction
        instr = compile_instruction(deconstructor.normalize(text), "inspect", external_data)
        return firewall.validate(instr, self.config)


class ProvenanceEngine(TruthEngine):
    """Alias de TruthEngine: solo SUPPORTED con ≥2 ORÍGENES independientes revisados."""


class GnosticContradictionEngine:
    def __init__(self, rules: RuleBase | None = None, truth: TruthEngine | None = None):
        self.rules, self.truth = rules or RuleBase(), truth

    def detect(self, text: str) -> list[dict]:
        return deconstructor.deconstruct(text, self.rules, None, self.truth)["contradictions"]


class OmegaGuard:
    def __init__(self, policy: AuthorizationPolicy | None = None, sessions: SessionGuard | None = None):
        self.policy, self.sessions = policy or AuthorizationPolicy(), sessions or SessionGuard()

    def authorize(self, instruction: dict) -> dict:
        return self.policy.decide(instruction)

    def admit(self, session: str) -> dict:
        return self.sessions.check(session)
