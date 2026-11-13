
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid

from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any

# ============================================================
# NRE — GNOSTIC TRUTH ENGINE
# ============================================================

VERSION = "NRE-AMM-OMEGA-GTE-1.0"

STATE_FILE = Path("truth_engine_state.json")

MAX_CLAIMS = 10000
MAX_EVIDENCE = 50000
MAX_CYCLES = 100
MIN_INDEPENDENT_SOURCES = 2

ROOT_INVARIANTS = {
    "I01": "INFERENCE != FACT",
    "I02": "CLAIM != EVIDENCE",
    "I03": "MODEL_OUTPUT != VERIFIED_TRUTH",
    "I04": "RESPONSE != REALITY",
    "I05": "EXTERNAL_CONTEXT != AUTHORITY",
    "I06": "MEMORY != EVIDENCE",
    "I07": "CORRELATION != CAUSATION",
    "I08": "ABSENCE_OF_EVIDENCE != EVIDENCE_OF_ABSENCE",
    "I09": "CONTRADICTION => INVESTIGATION",
    "I10": "UNCERTAINTY != FALSEHOOD",
    "I11": "MUTATION != AUTHORIZATION",
    "I12": "UNVERIFIED_RESULT != ACCEPTED_RESULT",
    "I13": "SECURITY_FAILURE => HALT",
    "I14": "EVERY_VERDICT_REQUIRES_TRACEABILITY"
}

class TruthState(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    CONTRADICTED = "CONTRADICTED"
    UNDETERMINED = "UNDETERMINED"

class EpistemicType(str, Enum):
    FACT = "FACT"
    CLAIM = "CLAIM"
    HYPOTHESIS = "HYPOTHESIS"
    ASSUMPTION = "ASSUMPTION"
    OBJECTIVE = "OBJECTIVE"
    CONSTRAINT = "CONSTRAINT"
    UNKNOWN = "UNKNOWN"

class EngineState(str, Enum):
    IDLE = "IDLE"
    PARSING = "PARSING"
    DECONSTRUCTING = "DECONSTRUCTING"
    VERIFYING = "VERIFYING"
    REASONING = "REASONING"
    LEARNING = "LEARNING"
    COMPLETED = "COMPLETED"
    HALTED = "HALTED"

class SecurityError(Exception):
    pass

# ============================================================
# L0 — UNIVERSAL STRUCTURAL INVARIANT
# ============================================================

class RootKernel:

    def __init__(self):
        self._invariants = dict(ROOT_INVARIANTS)

    @property
    def invariants(self):
        return dict(self._invariants)

    def verify(self, candidate):

        if candidate != self._invariants:
            raise SecurityError("ROOT_INVARIANT_COMPROMISED")

        return True

    def authorize(self, operation):

        protected = {
            "modify_root",
            "disable_verification",
            "override_evidence",
            "rewrite_audit"
        }

        if operation in protected:
            raise SecurityError("PROTECTED_OPERATION")

        return True

# ============================================================
# L1 — SIPE / CONTEXT COMPILER
# ============================================================

@dataclass
class Claim:

    id: str
    statement: str
    epistemic_type: str
    domain: str
    created_at: float

class SIPE:

    @staticmethod
    def normalize(text):

        if not isinstance(text, str):
            raise SecurityError("INVALID_INPUT_TYPE")

        text = re.sub(r"\s+", " ", text.strip())

        if not text:
            raise SecurityError("EMPTY_INPUT")

        if len(text) > 100000:
            raise SecurityError("INPUT_TOO_LARGE")

        return text

    @staticmethod
    def classify(text):

        patterns = {
            EpistemicType.HYPOTHESIS: r"\b(hipótesis|supongamos|podría)\b",
            EpistemicType.ASSUMPTION: r"\b(asumimos|supuesto|presuponemos)\b",
            EpistemicType.OBJECTIVE: r"\b(objetivo|finalidad|propósito)\b",
            EpistemicType.CONSTRAINT: r"\b(restricción|límite|prohibido)\b",
            EpistemicType.UNKNOWN: r"\b(desconocido|no sabemos|incierto)\b"
        }

        matches = [
            kind for kind, pattern in patterns.items()
            if re.search(pattern, text, re.I)
        ]

        if len(matches) == 1:
            return matches[0].value

        if len(matches) > 1:
            return EpistemicType.UNKNOWN.value

        return EpistemicType.CLAIM.value

    def compile(self, text, domain="GENERAL"):

        normalized = self.normalize(text)

        return Claim(
            id=uuid.uuid4().hex,
            statement=normalized,
            epistemic_type=self.classify(normalized),
            domain=domain,
            created_at=time.time()
        )

# ============================================================
# L2 — SEMANTIC FIREWALL
# ============================================================

class SemanticFirewall:

    PATTERNS = [
        r"ignore previous instructions",
        r"reveal system prompt",
        r"disable safety",
        r"override system policy",
        r"ignora las instrucciones anteriores",
        r"revela el prompt del sistema",
        r"desactiva las restricciones"
    ]

    def inspect(self, content):

        normalized = content.casefold()

        detected = [
            pattern for pattern in self.PATTERNS
            if re.search(pattern, normalized)
        ]

        return {
            "suspicious": bool(detected),
            "patterns": detected,
            "authority": "UNTRUSTED"
        }

# ============================================================
# L3 — GNOSTIC DECONSTRUCTOR
# ============================================================

@dataclass
class Evidence:

    id: str
    claim_id: str
    statement: str
    source_id: str
    source_description: str
    relation: str
    method: str
    independently_reviewed: bool
    reviewed_by: str
    timestamp: float

class EvidenceEngine:

    VALID_RELATIONS = {"SUPPORTS", "REFUTES"}

    def __init__(self):

        self.records = {}

    def register(
        self,
        claim_id,
        statement,
        source_id,
        source_description,
        relation,
        method,
        independently_reviewed=False,
        reviewed_by=""
    ):

        if relation not in self.VALID_RELATIONS:
            raise SecurityError("INVALID_EVIDENCE_RELATION")

        if not all([
            claim_id,
            statement,
            source_id,
            source_description,
            method
        ]):
            raise SecurityError("INCOMPLETE_EVIDENCE")

        if independently_reviewed and not reviewed_by:
            raise SecurityError("MISSING_REVIEWER")

        evidence = Evidence(
            id=uuid.uuid4().hex,
            claim_id=claim_id,
            statement=statement,
            source_id=source_id,
            source_description=source_description,
            relation=relation,
            method=method,
            independently_reviewed=independently_reviewed,
            reviewed_by=reviewed_by,
            timestamp=time.time()
        )

        self.records[evidence.id] = evidence

        return evidence

    def for_claim(self, claim_id):

        return [
            item for item in self.records.values()
            if item.claim_id == claim_id
        ]

# ============================================================
# L4 — INDEPENDENT VERIFICATION
# ============================================================

class IndependentVerifier:

    def __init__(self, evidence_engine):

        self.evidence_engine = evidence_engine

    def verify(self, claim_id):

        evidence = self.evidence_engine.for_claim(claim_id)

        reviewed = [
            item for item in evidence
            if item.independently_reviewed
        ]

        supports = [
            item for item in reviewed
            if item.relation == "SUPPORTS"
        ]

        refutes = [
            item for item in reviewed
            if item.relation == "REFUTES"
        ]

        support_sources = {
            item.source_id for item in supports
        }

        refute_sources = {
            item.source_id for item in refutes
        }

        support_count = len(support_sources)
        refute_count = len(refute_sources)

        # No se permite que múltiples registros
        # de una misma fuente simulen independencia.

        if (
            support_count >= MIN_INDEPENDENT_SOURCES
            and refute_count >= MIN_INDEPENDENT_SOURCES
        ):
            state = TruthState.CONTRADICTED

        elif support_count >= MIN_INDEPENDENT_SOURCES:
            state = TruthState.SUPPORTED

        elif refute_count >= MIN_INDEPENDENT_SOURCES:
            state = TruthState.REFUTED

        else:
            state = TruthState.UNDETERMINED

        return {
            "claim_id": claim_id,
            "state": state.value,
            "supporting_sources": support_count,
            "refuting_sources": refute_count,
            "evidence_count": len(evidence),
            "reviewed_evidence_count": len(reviewed),
            "evidence_ids": [item.id for item in evidence],
            "criteria": {
                "minimum_independent_sources":
                    MIN_INDEPENDENT_SOURCES,
                "independent_review_required": True
            }
        }

# ============================================================
# L5 — OMEGA REASONING ENGINE
# ============================================================

class OmegaReasoningEngine:

    def reconstruct(self, claim, verification):

        state = verification["state"]

        conclusions = {
            TruthState.SUPPORTED.value:
                "Supported under the registered evidence criteria.",
            TruthState.REFUTED.value:
                "Refuted under the registered evidence criteria.",
            TruthState.CONTRADICTED.value:
                "Conflicting independently reviewed evidence exists.",
            TruthState.UNDETERMINED.value:
                "Insufficient independent evidence for a verdict."
        }

        return {
            "claim": claim.statement,
            "epistemic_type": claim.epistemic_type,
            "domain": claim.domain,
            "truth_state": state,
            "conclusion": conclusions[state],
            "evidence_ids": verification["evidence_ids"],
            "limitations": [
                "Verdict depends on source quality.",
                "Source independence must be established.",
                "Evidence may be incomplete or outdated.",
                "This is not proof of absolute truth."
            ]
        }

# ============================================================
# L6 — MUTABLE GNOSTIC CONTROLLER
# ============================================================

class MutableLearningController:

    def __init__(self):

        self.rules = {
            "minimum_sources": MIN_INDEPENDENT_SOURCES,
            "require_independent_review": True
        }

        self.history = []

    def propose(self, key, value, reason):

        if key not in self.rules:
            raise SecurityError("UNKNOWN_MUTABLE_PARAMETER")

        if not reason.strip():
            raise SecurityError("MISSING_MUTATION_REASON")

        return {
            "key": key,
            "old_value": self.rules[key],
            "new_value": value,
            "reason": reason,
            "status": "CANDIDATE"
        }

    def apply(self, proposal, validator):

        candidate = dict(self.rules)

        candidate[proposal["key"]] = proposal["new_value"]

        if not validator(candidate):
            proposal["status"] = "REJECTED"
            return proposal

        proposal["status"] = "ACCEPTED"

        self.rules = candidate
        self.history.append(dict(proposal))

        return proposal

    def validate_policy(self, candidate):

        if candidate["minimum_sources"] < 2:
            return False

        if candidate["require_independent_review"] is not True:
            return False

        return True

# ============================================================
# L7 — AUDIT AND PERSISTENCE
# ============================================================

class AuditEngine:

    def __init__(self):

        self.events = []
        self.previous_hash = "GENESIS"

    def record(self, event, payload):

        entry = {
            "timestamp": time.time(),
            "event": event,
            "payload": payload,
            "previous_hash": self.previous_hash
        }

        serialized = json.dumps(
            entry,
            sort_keys=True,
            ensure_ascii=False,
            default=str
        )

        digest = hashlib.sha256(
            serialized.encode()
        ).hexdigest()

        entry["hash"] = digest

        self.events.append(entry)
        self.previous_hash = digest

        return digest

    def verify(self):

        previous = "GENESIS"

        for entry in self.events:

            content = {
                key: value
                for key, value in entry.items()
                if key != "hash"
            }

            serialized = json.dumps(
                content,
                sort_keys=True,
                ensure_ascii=False,
                default=str
            )

            digest = hashlib.sha256(
                serialized.encode()
            ).hexdigest()

            if entry["previous_hash"] != previous:
                return False

            if entry["hash"] != digest:
                return False

            previous = digest

        return True

class StateManager:

    def __init__(self, path=STATE_FILE):

        self.path = Path(path)

    def save(self, state):

        serialized = json.dumps(
            state,
            sort_keys=True,
            ensure_ascii=False,
            indent=2
        )

        temporary = self.path.with_suffix(".tmp")

        with open(temporary, "w", encoding="utf-8") as file:
            file.write(serialized)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, self.path)

    def load(self):

        if not self.path.exists():
            return None

        with open(self.path, encoding="utf-8") as file:
            return json.load(file)

# ============================================================
# NEXUS — TRANSVERSAL GOVERNANCE
# ============================================================

class NexusControlPlane:

    def __init__(self):

        self.root = RootKernel()
        self.firewall = SemanticFirewall()
        self.audit = AuditEngine()
        self.state_manager = StateManager()

        self.sipe = SIPE()
        self.evidence = EvidenceEngine()

        self.verifier = IndependentVerifier(
            self.evidence
        )

        self.omega = OmegaReasoningEngine()
        self.learning = MutableLearningController()

        self.claims = {}
        self.cycles = 0
        self.state = EngineState.IDLE

    def add_claim(self, statement, domain="GENERAL"):

        self.root.verify(ROOT_INVARIANTS)

        inspection = self.firewall.inspect(statement)

        if inspection["suspicious"]:
            raise SecurityError("SUSPICIOUS_INPUT_REQUIRES_REVIEW")

        claim = self.sipe.compile(statement, domain)

        if len(self.claims) >= MAX_CLAIMS:
            raise SecurityError("CLAIM_LIMIT_EXCEEDED")

        self.claims[claim.id] = claim

        self.audit.record(
            "CLAIM_REGISTERED",
            asdict(claim)
        )

        return claim.id

    def add_evidence(self, **kwargs):

        if len(self.evidence.records) >= MAX_EVIDENCE:
            raise SecurityError("EVIDENCE_LIMIT_EXCEEDED")

        claim_id = kwargs.get("claim_id")

        if claim_id not in self.claims:
            raise SecurityError("UNKNOWN_CLAIM")

        evidence = self.evidence.register(**kwargs)

        self.audit.record(
            "EVIDENCE_REGISTERED",
            asdict(evidence)
        )

        return evidence.id

    def evaluate(self, claim_id):

        if claim_id not in self.claims:
            raise SecurityError("UNKNOWN_CLAIM")

        if self.cycles >= MAX_CYCLES:
            self.state = EngineState.HALTED
            raise SecurityError("MAX_CYCLES_REACHED")

        self.root.verify(ROOT_INVARIANTS)

        self.state = EngineState.VERIFYING

        claim = self.claims[claim_id]

        verification = self.verifier.verify(claim_id)

        self.state = EngineState.REASONING

        reconstruction = self.omega.reconstruct(
            claim,
            verification
        )

        self.cycles += 1

        result = {
            "engine": VERSION,
            "claim_id": claim_id,
            "truth_assessment": reconstruction,
            "verification": verification,
            "cycle": self.cycles
        }

        self.audit.record(
            "TRUTH_ASSESSMENT",
            result
        )

        self.state = EngineState.COMPLETED

        self.persist()

        return result

    def persist(self):

        if not self.audit.verify():
            self.state = EngineState.HALTED
            raise SecurityError("AUDIT_INTEGRITY_FAILURE")

        state = {
            "version": VERSION,
            "invariants": self.root.invariants,
            "claims": {
                key: asdict(value)
                for key, value in self.claims.items()
            },
            "evidence": {
                key: asdict(value)
                for key, value in self.evidence.records.items()
            },
            "learning": {
                "rules": self.learning.rules,
                "history": self.learning.history
            },
            "audit": self.audit.events,
            "cycles": self.cycles
        }

        self.state_manager.save(state)

# ============================================================
# APPLICATION INTERFACE
# ============================================================

def main():

    engine = NexusControlPlane()

    # Register a proposition.
    claim_id = engine.add_claim(
        "El agua pura hierve aproximadamente a 100 grados Celsius "
        "a una presión de una atmósfera.",
        domain="PHYSICS"
    )

    # Register independently reviewed sources.
    engine.add_evidence(
        claim_id=claim_id,
        statement="Reference source supports the proposition.",
        source_id="SOURCE_A",
        source_description="Independent reference A",
        relation="SUPPORTS",
        method="DOCUMENT_REVIEW",
        independently_reviewed=True,
        reviewed_by="REVIEWER_A"
    )

    engine.add_evidence(
        claim_id=claim_id,
        statement="Second reference supports the proposition.",
        source_id="SOURCE_B",
        source_description="Independent reference B",
        relation="SUPPORTS",
        method="DOCUMENT_REVIEW",
        independently_reviewed=True,
        reviewed_by="REVIEWER_B"
    )

    # Evaluate.
    result = engine.evaluate(claim_id)

    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False
    ))

if __name__ == "__main__":
    main()
