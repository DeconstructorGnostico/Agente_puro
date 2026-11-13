"""L4/L7 — Gnostic Truth Engine integrado:  T(x) = V(E(D(N(x)))).

Cada afirmación recibe uno de 4 estados: SUPPORTED / REFUTED / CONTRADICTED / UNDETERMINED.
Solo SUPPORTED puede tratarse como FACT.

Correcciones sobre pure.py:
1. La revisión ya no es autodeclarada: el revisor debe ser un verificador REGISTRADO,
   distinto de quien envía la evidencia y del autor de la afirmación. El modelo/agente
   nunca puede ser fuente ni revisor (MODEL_OUTPUT != VERIFIED_TRUTH). Cada fuente necesita
   procedencia (url, sha256 o id de documento).
2. Una refutación creíble (revisada, confiabilidad >= 0.5) frente a apoyo suficiente da
   CONTRADICTED; ya no se ignora.
3. Los parámetros aprendidos (min_sources, review) se LEEN de la base de reglas mutable,
   con guardia: min_sources >= 2 y la revisión independiente no se puede apagar.
4. El estado se carga al iniciar (ver persistence.VersionedState).
Multimodelo: el acuerdo de modelos solo cuenta como corroboración de un chequeo
independiente ya existente; nunca como evidencia por sí mismo.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .text import fold

FORBIDDEN_ACTORS = {"model", "modelo", "agent", "agente", "omega", "system", "sistema", "team", "equipo",
                    "self", "yo", "assistant", "llm", "executor", "user_input"}
PROVENANCE_RE = re.compile(r"^(https?://\S+|sha256:[0-9a-f]{64}|doc:[\w.\-/:]{3,}|isbn:[\d\-xX]{10,17}|doi:10\.\S+)$")
MAX_EVIDENCE_PER_CLAIM = 20


def origin_key(provenance: str) -> str:
    """Independencia NO autodeclarada: dos evidencias con el mismo host (URL) o el mismo
    documento (sha256/doc/doi/isbn) son el MISMO origen, aunque declaren source_id distintos."""
    m = re.match(r"^https?://([^/]+)", provenance or "")
    if m:
        host = m.group(1).lower().split("@")[-1].split(":")[0]
        return "host:" + (host[4:] if host.startswith("www.") else host)
    return provenance


TRUTH_DEFAULTS = {"min_sources": 2, "require_independent_review": True, "credible_reliability": 0.5}


class TruthError(Exception):
    pass


def guard_truth_params(p: dict) -> bool:
    """Guardia de mutación (de pure.py): nunca menos de 2 fuentes, revisión siempre obligatoria."""
    return (int(p.get("min_sources", 0)) >= 2 and p.get("require_independent_review") is True
            and 0.5 <= float(p.get("credible_reliability", 0)) <= 1.0)


@dataclass
class EvidenceItem:
    id: str
    claim: str
    statement: str
    source_id: str
    provenance: str
    relation: str  # SUPPORTS | REFUTES
    method: str
    submitted_by: str
    reviewed_by: str = ""
    reliability: float = 0.7


class TruthEngine:
    def __init__(self, params: dict | None = None):
        self.verifiers: dict[str, dict] = {}
        self.evidence: list[EvidenceItem] = []
        self.params = dict(params or TRUTH_DEFAULTS)
        if not guard_truth_params(self.params):
            raise TruthError("TRUTH_PARAMS_VIOLATE_GUARD")

    # -- registro de verificadores independientes
    def register_verifier(self, verifier_id: str, organization: str) -> None:
        if fold(verifier_id) in FORBIDDEN_ACTORS or not verifier_id.strip():
            raise TruthError("VERIFIER_NOT_ALLOWED")
        self.verifiers[verifier_id] = {"id": verifier_id, "organization": organization}

    def add_evidence(self, claim: str, statement: str, source_id: str, provenance: str, relation: str,
                     method: str, submitted_by: str, reviewed_by: str = "", reliability: float = 0.7,
                     claim_author: str = "user", document: str | None = None) -> EvidenceItem:
        if relation not in {"SUPPORTS", "REFUTES"}:
            raise TruthError("INVALID_RELATION")
        if not all([claim, statement, source_id, method, submitted_by]):
            raise TruthError("INCOMPLETE_EVIDENCE")
        if fold(source_id) in FORBIDDEN_ACTORS or fold(submitted_by) in FORBIDDEN_ACTORS:
            raise TruthError("MODEL_OR_AGENT_CANNOT_BE_SOURCE")
        if not PROVENANCE_RE.match(provenance or ""):
            raise TruthError("MISSING_PROVENANCE")
        if document is not None:
            import hashlib
            if not provenance.startswith("sha256:"):
                raise TruthError("DOCUMENT_WITHOUT_HASH")
            if hashlib.sha256(document.encode("utf-8")).hexdigest() != provenance[7:]:
                raise TruthError("WRONG_DOCUMENT_HASH")
        if sum(1 for e in self.evidence if self._matches(claim, e)) >= MAX_EVIDENCE_PER_CLAIM:
            raise TruthError("EVIDENCE_LIMIT_EXCEEDED")
        if reviewed_by:
            if reviewed_by not in self.verifiers:
                raise TruthError("REVIEWER_NOT_REGISTERED")
            if reviewed_by in {submitted_by, claim_author}:
                raise TruthError("REVIEWER_NOT_INDEPENDENT")
        if not 0.0 <= float(reliability) <= 1.0:
            raise TruthError("INVALID_RELIABILITY")
        item = EvidenceItem(f"EV{len(self.evidence) + 1}", claim, statement, source_id, provenance, relation,
                            method, submitted_by, reviewed_by, float(reliability))
        self.evidence.append(item)
        return item

    def _matches(self, claim: str, item: EvidenceItem) -> bool:
        a, b = set(re.findall(r"[a-z0-9]+", fold(claim))), set(re.findall(r"[a-z0-9]+", fold(item.claim)))
        return bool(a) and len(a & b) / len(a | b) >= 0.8

    def assess(self, claim: str, model_agreement: dict | None = None) -> dict:
        p = self.params
        items = [e for e in self.evidence if self._matches(claim, e)]
        reviewed = [e for e in items if e.reviewed_by] if p["require_independent_review"] else items
        # se cuentan ORÍGENES (host/documento), no etiquetas de fuente declaradas
        sup = {origin_key(e.provenance) for e in reviewed if e.relation == "SUPPORTS"}
        ref_cred = {origin_key(e.provenance) for e in reviewed
                    if e.relation == "REFUTES" and e.reliability >= p["credible_reliability"]}
        m = p["min_sources"]
        if len(sup) >= m and ref_cred:
            state = "CONTRADICTED"        # refutación creíble frente a apoyo suficiente
        elif len(sup) >= m:
            state = "SUPPORTED"
        elif ref_cred and sup:
            state = "CONTRADICTED"
        elif len(ref_cred) >= m:
            state = "REFUTED"
        else:
            state = "UNDETERMINED"
        corroboration = None
        if model_agreement is not None:
            # Solo corrobora si YA existe un chequeo independiente; nunca suma fuentes.
            corroboration = {"models": model_agreement, "counted_as_evidence": False,
                             "applies": bool(sup or ref_cred)}
        return {"claim": claim, "state": state, "supporting_sources": len(sup),
                "credible_refuting_sources": len(ref_cred), "evidence_ids": [e.id for e in items],
                "reviewed_evidence": len(reviewed), "criteria": dict(p), "corroboration": corroboration}

    def export(self) -> dict:
        return {"verifiers": self.verifiers, "evidence": [asdict(e) for e in self.evidence], "params": self.params}

    @classmethod
    def from_export(cls, data: dict) -> "TruthEngine":
        t = cls(data.get("params"))
        t.verifiers = dict(data.get("verifiers", {}))
        t.evidence = [EvidenceItem(**e) for e in data.get("evidence", [])]
        return t
