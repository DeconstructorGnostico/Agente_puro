
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import time

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any

VERSION = "DGM-1.0"

# ==========================================================
# L0 — ROOT GOVERNANCE (INMUTABLE)
# ==========================================================

ROOT_INVARIANTS = {
    "I01": "INFERENCE != FACT",
    "I02": "CLAIM != EVIDENCE",
    "I03": "EXTERNAL_DATA != AUTHORITY",
    "I04": "MEMORY != EVIDENCE",
    "I05": "MODEL_OUTPUT != VERIFIED_TRUTH",
    "I06": "MUTATION != AUTHORIZATION",
    "I07": "UNVERIFIED_CHANGE != PRODUCTION",
    "I08": "SECURITY_FAILURE => HALT",
}

MAX_RULES = 100
MAX_MUTATIONS_PER_CYCLE = 10
MAX_HISTORY = 500
MIN_TEST_CASES = 3
MIN_ACCURACY = 0.80
MAX_REGRESSION = 0.02

RULE_FILE = "dgm_state.json"

class Status(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    HALTED = "HALTED"

class SecurityViolation(Exception):
    pass

# ==========================================================
# L1 — EPISTEMIC TAXONOMY
# ==========================================================

class Category(str, Enum):
    FACT = "FACT"
    CLAIM = "CLAIM"
    HYPOTHESIS = "HYPOTHESIS"
    ASSUMPTION = "ASSUMPTION"
    OBJECTIVE = "OBJECTIVE"
    CONSTRAINT = "CONSTRAINT"
    UNKNOWN = "UNKNOWN"

@dataclass
class Rule:

    rule_id: str
    keyword: str
    category: str
    enabled: bool = True
    priority: int = 1
    version: int = 1

@dataclass
class TestCase:

    text: str
    expected: str
    trusted: bool = True

@dataclass
class Mutation:

    operation: str
    rule: dict
    reason: str

# ==========================================================
# L2 — INITIAL RULE BASE
# ==========================================================

DEFAULT_RULES = [
    Rule("R001", "hipótesis", "HYPOTHESIS"),
    Rule("R002", "supongo", "ASSUMPTION"),
    Rule("R003", "objetivo", "OBJECTIVE"),
    Rule("R004", "restricción", "CONSTRAINT"),
    Rule("R005", "desconocido", "UNKNOWN"),
]

# ==========================================================
# L3 — MUTABLE DECONSTRUCTION ENGINE
# ==========================================================

class MutableRuleEngine:

    def __init__(self, rules=None):

        self.rules = copy.deepcopy(
            rules if rules is not None else DEFAULT_RULES
        )

        self.validate_rule_base()

    def validate_rule_base(self):

        if len(self.rules) > MAX_RULES:
            raise SecurityViolation("RULE_LIMIT_EXCEEDED")

        identifiers = set()

        for rule in self.rules:

            if rule.rule_id in identifiers:
                raise SecurityViolation("DUPLICATE_RULE_ID")

            identifiers.add(rule.rule_id)

            if rule.category not in Category._value2member_map_:
                raise SecurityViolation("INVALID_CATEGORY")

            if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñ0-9 _-]{1,80}",
                                rule.keyword):
                raise SecurityViolation("INVALID_KEYWORD")

    def classify(self, text: str):

        normalized = text.casefold()

        matches = [
            rule for rule in self.rules
            if rule.enabled
            and rule.keyword.casefold() in normalized
        ]

        if not matches:
            return Category.CLAIM.value

        highest_priority = max(
            rule.priority for rule in matches
        )

        winners = [
            rule for rule in matches
            if rule.priority == highest_priority
        ]

        categories = {rule.category for rule in winners}

        if len(categories) > 1:
            return Category.UNKNOWN.value

        return winners[0].category

    def add_rule(self, rule: Rule):

        if any(r.rule_id == rule.rule_id for r in self.rules):
            raise SecurityViolation("DUPLICATE_RULE_ID")

        self.rules.append(rule)
        self.validate_rule_base()

    def disable_rule(self, rule_id: str):

        for rule in self.rules:

            if rule.rule_id == rule_id:
                rule.enabled = False
                return

        raise SecurityViolation("RULE_NOT_FOUND")

# ==========================================================
# L4 — GNOSTIC DECOMPOSITION
# ==========================================================

class GnosticDeconstructor:

    def __init__(self, rule_engine):

        self.engine = rule_engine

    def deconstruct(self, text):

        if not isinstance(text, str) or not text.strip():
            raise ValueError("INVALID_INPUT")

        return {
            "input": text,
            "category": self.engine.classify(text),
            "length": len(text),
            "content_hash": hashlib.sha256(
                text.encode()
            ).hexdigest()
        }

# ==========================================================
# L5 — MUTATION GENERATOR
# ==========================================================

class MutationGenerator:

    def __init__(self, engine):

        self.engine = engine

    def propose_addition(
        self,
        keyword: str,
        category: str,
        reason: str
    ):

        if not reason.strip():
            raise SecurityViolation("MISSING_JUSTIFICATION")

        rule = Rule(
            rule_id=f"R{len(self.engine.rules) + 1:03d}",
            keyword=keyword,
            category=category,
            priority=1
        )

        return Mutation(
            operation="ADD",
            rule=asdict(rule),
            reason=reason
        )

    def propose_disabling(self, rule_id: str, reason: str):

        if not reason.strip():
            raise SecurityViolation("MISSING_JUSTIFICATION")

        return Mutation(
            operation="DISABLE",
            rule={"rule_id": rule_id},
            reason=reason
        )

# ==========================================================
# L6 — INDEPENDENT VALIDATION
# ==========================================================

class ValidationEngine:

    def __init__(self, test_cases):

        self.test_cases = test_cases

    def evaluate(self, engine):

        trusted = [
            case for case in self.test_cases
            if case.trusted
        ]

        if len(trusted) < MIN_TEST_CASES:
            raise SecurityViolation("INSUFFICIENT_TEST_CASES")

        correct = 0
        total = len(trusted)

        errors = []

        for case in trusted:

            predicted = engine.classify(case.text)

            if predicted == case.expected:
                correct += 1
            else:
                errors.append({
                    "input": case.text,
                    "expected": case.expected,
                    "predicted": predicted
                })

        accuracy = correct / total

        return {
            "accuracy": accuracy,
            "correct": correct,
            "total": total,
            "errors": errors
        }

    def compare(self, baseline, candidate):

        old_score = baseline["accuracy"]
        new_score = candidate["accuracy"]

        return {
            "improved": new_score > old_score,
            "regression": old_score - new_score,
            "candidate_accuracy": new_score,
            "baseline_accuracy": old_score,
            "accepted_metrics": (
                new_score >= MIN_ACCURACY
                and old_score - new_score <= MAX_REGRESSION
            )
        }

# ==========================================================
# L7 — ROOT INVARIANT VERIFICATION
# ==========================================================

class InvariantController:

    @staticmethod
    def verify(root_before, root_after):

        if root_before != root_after:
            raise SecurityViolation(
                "ROOT_INVARIANT_MODIFICATION"
            )

        if not root_before:
            raise SecurityViolation("EMPTY_ROOT")

        return True

# ==========================================================
# L8 — PERSISTENCE AND AUDIT
# ==========================================================

class PersistenceController:

    def __init__(self, path=RULE_FILE):

        self.path = path

    def save(self, state):

        serialized = json.dumps(
            state,
            sort_keys=True,
            ensure_ascii=False
        )

        temporary = self.path + ".tmp"

        with open(temporary, "w", encoding="utf-8") as file:
            file.write(serialized)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, self.path)

    def load(self):

        if not os.path.exists(self.path):
            return None

        with open(self.path, encoding="utf-8") as file:
            return json.load(file)

class AuditController:

    def __init__(self):

        self.events = []
        self.previous_hash = "GENESIS"

    def record(self, event, data):

        entry = {
            "time": time.time(),
            "event": event,
            "data": data,
            "previous_hash": self.previous_hash
        }

        digest = hashlib.sha256(
            json.dumps(
                entry,
                sort_keys=True,
                ensure_ascii=False
            ).encode()
        ).hexdigest()

        entry["hash"] = digest

        self.events.append(entry)
        self.previous_hash = digest

        if len(self.events) > MAX_HISTORY:
            self.events = self.events[-MAX_HISTORY:]

        return digest

# ==========================================================
# L9 — MUTATION CONTROLLER
# ==========================================================

class MutationController:

    def __init__(
        self,
        engine,
        validator,
        persistence,
        audit
    ):

        self.engine = engine
        self.validator = validator
        self.persistence = persistence
        self.audit = audit

        self.root = copy.deepcopy(ROOT_INVARIANTS)
        self.history = []

    def apply(self, mutation: Mutation):

        if len(self.history) >= MAX_HISTORY:
            raise SecurityViolation("MUTATION_HISTORY_LIMIT")

        if mutation.operation not in ("ADD", "DISABLE"):
            raise SecurityViolation("UNSUPPORTED_MUTATION")

        # Snapshot de seguridad.
        original = copy.deepcopy(self.engine.rules)

        # Métricas anteriores.
        baseline = self.validator.evaluate(self.engine)

        try:

            if mutation.operation == "ADD":

                self.engine.add_rule(
                    Rule(**mutation.rule)
                )

            elif mutation.operation == "DISABLE":

                self.engine.disable_rule(
                    mutation.rule["rule_id"]
                )

            # Integridad del motor.
            self.engine.validate_rule_base()

            # Métricas posteriores.
            candidate = self.validator.evaluate(self.engine)

            comparison = self.validator.compare(
                baseline,
                candidate
            )

            InvariantController.verify(
                self.root,
                ROOT_INVARIANTS
            )

            if not comparison["accepted_metrics"]:
                raise SecurityViolation(
                    "MUTATION_FAILED_VALIDATION"
                )

            # Promoción controlada.
            self.history.append({
                "operation": mutation.operation,
                "reason": mutation.reason,
                "comparison": comparison,
                "status": Status.ACCEPTED.value
            })

            self.audit.record(
                "MUTATION_ACCEPTED",
                self.history[-1]
            )

            self.persist()

            return {
                "status": Status.ACCEPTED.value,
                "comparison": comparison
            }

        except Exception as error:

            # ROLLBACK ATOMICO.
            self.engine.rules = original

            self.audit.record(
                "MUTATION_REJECTED",
                {
                    "reason": str(error),
                    "operation": mutation.operation
                }
            )

            return {
                "status": Status.REJECTED.value,
                "reason": str(error),
                "rollback": True
            }

    def persist(self):

        state = {
            "version": VERSION,
            "rules": [
                asdict(rule)
                for rule in self.engine.rules
            ],
            "history": self.history,
            "root_invariants": self.root,
            "audit": self.audit.events
        }

        self.persistence.save(state)

# ==========================================================
# L10 — AUTONOMOUS LEARNING LOOP
# ==========================================================

class MutableGnosticAgent:

    def __init__(self, test_cases):

        self.engine = MutableRuleEngine()

        self.deconstructor = GnosticDeconstructor(
            self.engine
        )

        self.generator = MutationGenerator(
            self.engine
        )

        self.validator = ValidationEngine(
            test_cases
        )

        self.audit = AuditController()

        self.persistence = PersistenceController()

        self.controller = MutationController(
            self.engine,
            self.validator,
            self.persistence,
            self.audit
        )

    def analyze(self, text):

        return self.deconstructor.deconstruct(text)

    def learn(self, keyword, category, reason):

        mutation = self.generator.propose_addition(
            keyword,
            category,
            reason
        )

        return self.controller.apply(mutation)

    def run_cycle(self, observations):

        if len(observations) > MAX_MUTATIONS_PER_CYCLE:
            raise SecurityViolation("CYCLE_LIMIT_EXCEEDED")

        results = []

        for observation in observations:

            results.append(
                self.analyze(observation)
            )

        self.audit.record(
            "ANALYSIS_CYCLE_COMPLETED",
            {"observations": len(observations)}
        )

        return {
            "status": "COMPLETED",
            "results": results,
            "rule_count": len(self.engine.rules)
        }

# ==========================================================
# APPLICATION ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    TESTS = [
        TestCase(
            "Hipótesis: el motor aprende.",
            "HYPOTHESIS"
        ),
        TestCase(
            "Objetivo: validar datos.",
            "OBJECTIVE"
        ),
        TestCase(
            "Restricción: no ejecutar.",
            "CONSTRAINT"
        ),
        TestCase(
            "El sistema funciona.",
            "CLAIM"
        ),
        TestCase(
            "Dato desconocido.",
            "UNKNOWN"
        )
    ]

    agent = MutableGnosticAgent(TESTS)

    # Primera descomposición.
    print(json.dumps(
        agent.analyze(
            "Hipótesis: el motor aprende."
        ),
        indent=2,
        ensure_ascii=False
    ))

    # Propuesta de mutación.
    result = agent.learn(
        keyword="posiblemente",
        category="HYPOTHESIS",
        reason="Mejorar clasificación de hipótesis."
    )

    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False
    ))

    # Ejecución de un ciclo.
    print(json.dumps(
        agent.run_cycle([
            "Objetivo: reconstruir conocimiento.",
            "Hipótesis: existe una nueva relación."
        ]),
        indent=2,
        ensure_ascii=False
    ))
