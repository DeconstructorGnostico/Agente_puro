"""L6 — Validación estructural + verificación externa enchufable.

`StructuralValidation` solo revisa el contrato de salida (antes llamada
"verificación independiente"). La verificación real contra algo externo
la hacen los verificadores enchufables, que comparan la respuesta con
referencias o evidencia que aporta quien llama, NO el modelo.
"""

from __future__ import annotations

from typing import Protocol

from .text import fold, tokens

REQUIRED = ("facts", "inferences", "unknowns", "proposed_solution")


class StructuralValidation:

    @staticmethod
    def run(result) -> dict:
        if not isinstance(result, dict):
            return {"valid": False, "reason": "INVALID_RESULT"}
        missing = [k for k in REQUIRED if k not in result]
        if missing:
            return {"valid": False, "reason": "INVALID_OUTPUT_CONTRACT", "missing": missing}
        for field in ("facts", "inferences", "unknowns"):
            if not isinstance(result[field], list):
                return {"valid": False, "reason": f"INVALID_{field.upper()}"}
        if not isinstance(result["proposed_solution"], str):
            return {"valid": False, "reason": "INVALID_PROPOSED_SOLUTION"}
        return {"valid": True}


class ExternalVerifier(Protocol):
    name: str

    def verify(self, instruction: dict, result: dict) -> dict | None:
        """Devuelve None si no aplica; si aplica, dict con `status`."""


class ReferenceVerifier:
    """Compara la respuesta con respuestas de referencia aportadas por quien llama."""

    name = "reference_match"

    def verify(self, instruction, result):
        refs = instruction.get("references") or []
        if not refs:
            return None
        answer = f" {' '.join(tokens(result['proposed_solution']))} "
        for ref in refs:
            ref_t = " ".join(tokens(ref))
            if ref_t and f" {ref_t} " in answer:
                return {"status": "VERIFIED", "matched_reference": ref}
        return {"status": "REJECTED", "reason": "REFERENCE_MISMATCH", "references": refs}


class EvidenceVerifier:
    """Cada `fact` debe estar respaldado por un texto de evidencia (solapamiento de tokens)."""

    name = "evidence_overlap"

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold

    def _supported(self, fact, evidence):
        ft = set(tokens(fact))
        if not ft:
            return False
        for item in evidence:
            et = set(tokens(item["text"]))
            if len(ft & et) / len(ft) >= self.threshold:
                return True
        return False

    def verify(self, instruction, result):
        evidence = instruction.get("evidence") or []
        facts = [str(f) for f in result.get("facts", [])]
        if not evidence or not facts:
            return None
        supported = [f for f in facts if self._supported(f, evidence)]
        if len(supported) == len(facts):
            status = "VERIFIED"
        elif supported:
            status = "PARTIALLY_VERIFIED"
        else:
            status = "UNVERIFIED"
        return {"status": status, "supported_facts": supported,
                "unsupported_facts": [f for f in facts if f not in supported]}


class VerificationPipeline:

    def __init__(self, verifiers=None):
        self.verifiers = list(verifiers) if verifiers is not None else [ReferenceVerifier(), EvidenceVerifier()]

    def run(self, instruction: dict, result) -> dict:
        structural = StructuralValidation.run(result)
        if not structural["valid"]:
            return {"status": "REJECTED", "reason": structural["reason"], "structural": structural,
                    "external_check": False, "verifier": None, "evidence_sources": []}
        sources = sorted({e["source"] for e in instruction.get("evidence", [])})
        for verifier in self.verifiers:
            outcome = verifier.verify(instruction, result)
            if outcome is not None:
                return {**outcome, "structural": structural, "external_check": True,
                        "verifier": verifier.name, "evidence_sources": sources}
        return {"status": "UNVERIFIED", "structural": structural, "external_check": False,
                "verifier": None, "evidence_sources": sources,
                "limitations": ["Sin referencias ni evidencia externa: la salida del modelo no es prueba de la realidad."]}
