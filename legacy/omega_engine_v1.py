
"""
NRE–AMM–OMEGA_CONTEXT_ENGINE
Version: 1.0.0
Architecture: L0-L7 + NEXUS Control Plane
Runtime: Python 3.11+
Dependencies: Python standard library

Execution:
    python omega_engine.py "Analizar una tarea"

With Ollama:
    OMEGA_PROVIDER=ollama python omega_engine.py "Analizar una tarea"

This is an executable reference implementation.
It does not claim production-grade model verification.
"""

from __future__ import annotations

import os
import json
import uuid
import hashlib
import urllib.request
import urllib.error

from pathlib import Path
from datetime import datetime, timezone
from typing import Any

# ============================================================
# L0 — INVARIANT UNIVERSAL ESTRUCTURAL
# ============================================================

class Invariants:

    SEED = 2412598653108

    RULES = {
        "I01": "INPUT != VERIFIED_INPUT",
        "I02": "INFERENCE != FACT",
        "I03": "CONTEXT != EVIDENCE",
        "I04": "EXECUTION REQUIRES VALIDATION",
        "I05": "STATE CHANGES REQUIRE AUDIT",
        "I06": "LEARNING REQUIRES ACCEPTANCE",
        "I07": "ERROR_THRESHOLD => HALT",
        "I08": "RESPONSE != REALITY",
        "I09": "UNVERIFIED != VERIFIED",
        "I10": "NO SILENT STATE MUTATION"
    }

    @classmethod
    def fingerprint(cls):
        payload = json.dumps(
            cls.RULES,
            sort_keys=True
        )
        return hashlib.sha256(
            f"{cls.SEED}:{payload}".encode()
        ).hexdigest()

# ============================================================
# L7 — PERSISTENCE
# ============================================================

class Storage:

    ROOT = Path("nre_runtime")
    STATE = ROOT / "omega_state.json"
    AUDIT = ROOT / "omega_history.jsonl"
    MEMORY = ROOT / "validated_memory.json"

    @classmethod
    def initialize(cls):
        cls.ROOT.mkdir(exist_ok=True)

        if not cls.STATE.exists():
            cls.save_state({
                "status": "READY",
                "cycles": 0,
                "reject_streak": 0,
                "max_cycles": 10,
                "memory": [],
                "version": "1.0.0"
            })

        if not cls.MEMORY.exists():
            cls.write_json(cls.MEMORY, [])

    @staticmethod
    def write_json(path, data):
        temporary = path.with_suffix(".tmp")

        temporary.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        temporary.replace(path)

    @classmethod
    def save_state(cls, state):
        cls.write_json(cls.STATE, state)

    @classmethod
    def load_state(cls):
        return json.loads(
            cls.STATE.read_text(encoding="utf-8")
        )

    @classmethod
    def audit(cls, event):
        event["timestamp"] = datetime.now(
            timezone.utc
        ).isoformat()

        with cls.AUDIT.open(
            "a",
            encoding="utf-8"
        ) as file:
            file.write(
                json.dumps(
                    event,
                    ensure_ascii=False
                ) + "\n"
            )

    @classmethod
    def load_memory(cls):
        return json.loads(
            cls.MEMORY.read_text(encoding="utf-8")
        )

    @classmethod
    def save_memory(cls, memory):
        cls.write_json(cls.MEMORY, memory)

# ============================================================
# L1 — SIPE: SEMANTIC INTENTION PROCESSING ENGINE
# ============================================================

class SIPE:

    @staticmethod
    def compile(raw_input):

        if not isinstance(raw_input, str):
            raise ValueError("INVALID_INPUT_TYPE")

        normalized = " ".join(raw_input.split())

        if not normalized:
            raise ValueError("EMPTY_INPUT")

        return {
            "intent_id": str(uuid.uuid4()),
            "raw_input": raw_input,
            "normalized_input": normalized,
            "objective": normalized,
            "constraints": [],
            "variables": [],
            "classification": "PENDING",
            "evidence": []
        }

# ============================================================
# L2 — SEMANTIC FIREWALL
# ============================================================

class SemanticFirewall:

    MAX_INPUT = 20000

    @classmethod
    def validate(cls, context):

        errors = []

        objective = context.get("objective")

        if not isinstance(objective, str):
            errors.append("INVALID_OBJECTIVE")

        elif not objective.strip():
            errors.append("EMPTY_OBJECTIVE")

        elif len(objective) > cls.MAX_INPUT:
            errors.append("INPUT_LIMIT_EXCEEDED")

        if not isinstance(
            context.get("constraints"), list
        ):
            errors.append("INVALID_CONSTRAINTS")

        if not isinstance(
            context.get("evidence"), list
        ):
            errors.append("INVALID_EVIDENCE")

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

# ============================================================
# L3 — AMM CORE
# ============================================================

class AMMCore:

    @staticmethod
    def create_execution_plan(context):

        return {
            "objective": context["objective"],
            "stages": [
                "INTERPRETATION",
                "VALIDATION",
                "EXECUTION",
                "VERIFICATION",
                "AUDIT",
                "PERSISTENCE"
            ],
            "execution_allowed": True,
            "verification_required": True
        }

    @staticmethod
    def enforce_invariants():

        return {
            "fingerprint": Invariants.fingerprint(),
            "rules": Invariants.RULES,
            "valid": True
        }

# ============================================================
# L4 — OMEGA EXECUTION ENGINE
# ============================================================

class OmegaEngine:

    def __init__(self):
        Storage.initialize()
        self.state = Storage.load_state()

    def transition(self, new_status):

        allowed = {
            "READY": ["PROCESSING", "HALTED"],
            "PROCESSING": [
                "VERIFYING", "HALTED"
            ],
            "VERIFYING": [
                "VERIFIED",
                "PARTIALLY_VERIFIED",
                "UNVERIFIED",
                "REJECTED",
                "HALTED"
            ],
            "VERIFIED": ["READY"],
            "PARTIALLY_VERIFIED": ["READY"],
            "UNVERIFIED": ["READY"],
            "REJECTED": ["READY", "HALTED"],
            "HALTED": []
        }

        current = self.state["status"]

        if new_status not in allowed.get(current, []):
            raise RuntimeError(
                f"INVALID_TRANSITION: {current} -> {new_status}"
            )

        self.state["status"] = new_status

        Storage.audit({
            "event": "STATE_TRANSITION",
            "previous": current,
            "current": new_status
        })

        Storage.save_state(self.state)

    def halt(self, reason):

        self.state["status"] = "HALTED"

        Storage.audit({
            "event": "HALT",
            "reason": reason
        })

        Storage.save_state(self.state)

    def execute_cycle(self, context, executor):

        if self.state["status"] == "HALTED":
            raise RuntimeError("ENGINE_HALTED")

        if self.state["cycles"] >= self.state["max_cycles"]:
            self.halt("MAX_CYCLES_REACHED")
            raise RuntimeError("MAX_CYCLES_REACHED")

        self.transition("PROCESSING")

        try:
            plan = AMMCore.create_execution_plan(
                context
            )

            result = executor.run(context, plan)

            self.transition("VERIFYING")

            verification = IndependentVerification.run(
                result
            )

            if verification["status"] == "REJECTED":
                self.state["reject_streak"] += 1

            else:
                self.state["reject_streak"] = 0

            if self.state["reject_streak"] >= 3:
                self.halt("REJECTION_THRESHOLD")
                raise RuntimeError("REJECTION_THRESHOLD")

            self.state["cycles"] += 1

            final_status = verification["status"]

            self.transition(final_status)

            LearningController.process(
                result,
                verification
            )

            Storage.audit({
                "event": "EXECUTION_COMPLETE",
                "intent_id": context["intent_id"],
                "verification": verification,
                "result_hash": hashlib.sha256(
                    json.dumps(
                        result,
                        sort_keys=True
                    ).encode()
                ).hexdigest()
            })

            Storage.save_state(self.state)

            return {
                "plan": plan,
                "result": result,
                "verification": verification
            }

        except Exception as error:

            if self.state["status"] not in [
                "HALTED",
                "READY"
            ]:
                self.halt(str(error))

            raise

# ============================================================
# L5 — MULTIMODEL GATEWAY
# ============================================================

class ModelGateway:

    def __init__(self):

        self.provider = os.getenv(
            "OMEGA_PROVIDER", "mock"
        )

        self.model = os.getenv(
            "OMEGA_MODEL", "llama3.2"
        )

        self.endpoint = os.getenv(
            "OLLAMA_ENDPOINT",
            "http://localhost:11434/api/chat"
        )

    def generate(self, context, plan):

        prompt = {
            "role": "user",
            "content": json.dumps({
                "objective": context["objective"],
                "constraints": context["constraints"],
                "execution_plan": plan,
                "output_requirements": {
                    "facts": [],
                    "inferences": [],
                    "unknowns": [],
                    "proposed_solution": ""
                }
            }, ensure_ascii=False)
        }

        if self.provider == "mock":

            return {
                "provider": "mock",
                "facts": [],
                "inferences": [
                    "No model inference was executed."
                ],
                "unknowns": [
                    "External evidence is unavailable."
                ],
                "proposed_solution": (
                    "Connect a model provider to process "
                    "the objective."
                )
            }

        if self.provider != "ollama":
            raise ValueError("UNSUPPORTED_PROVIDER")

        payload = json.dumps({
            "model": self.model,
            "messages": [prompt],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1
            }
        }).encode("utf-8")

        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(
            request,
            timeout=120
        ) as response:

            data = json.loads(response.read())

        content = json.loads(
            data["message"]["content"]
        )

        return {
            "provider": self.provider,
            "model": self.model,
            **content
        }

class Executor:

    def __init__(self):
        self.gateway = ModelGateway()

    def run(self, context, plan):

        return self.gateway.generate(
            context,
            plan
        )

# ============================================================
# L6 — EVIDENCE ENGINE + INDEPENDENT VERIFICATION
# ============================================================

class EvidenceEngine:

    @staticmethod
    def inspect(result):

        evidence = result.get("evidence", [])

        if not isinstance(evidence, list):
            return {
                "valid": False,
                "count": 0
            }

        return {
            "valid": True,
            "count": len(evidence),
            "items": evidence
        }

class IndependentVerification:

    @staticmethod
    def run(result):

        if not isinstance(result, dict):
            return {
                "status": "REJECTED",
                "reason": "INVALID_RESULT"
            }

        required = [
            "facts",
            "inferences",
            "unknowns",
            "proposed_solution"
        ]

        if not all(key in result for key in required):
            return {
                "status": "REJECTED",
                "reason": "INVALID_OUTPUT_CONTRACT"
            }

        for field in ["facts", "inferences", "unknowns"]:

            if not isinstance(result[field], list):
                return {
                    "status": "REJECTED",
                    "reason": f"INVALID_{field.upper()}"
                }

        evidence = EvidenceEngine.inspect(result)

        if not evidence["valid"]:
            return {
                "status": "REJECTED",
                "reason": "INVALID_EVIDENCE"
            }

        if evidence["count"] == 0:
            status = "UNVERIFIED"
        else:
            # Evidence presence is not proof of truth.
            status = "PARTIALLY_VERIFIED"

        return {
            "status": status,
            "evidence_count": evidence["count"],
            "independent_external_check": False,
            "limitations": [
                "Evidence authenticity requires validation.",
                "Model output is not proof of reality.",
                "No external source verification performed."
            ]
        }

# ============================================================
# LEARNING CONTROLLER
# ============================================================

class LearningController:

    @staticmethod
    def process(result, verification):

        # Never learn from rejected or unverified outputs.

        if verification["status"] != "VERIFIED":
            return False

        memory = Storage.load_memory()

        memory.append({
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "result": result,
            "verification": verification["status"]
        })

        Storage.save_memory(memory)

        Storage.audit({
            "event": "SELECTIVE_LEARNING",
            "accepted": True
        })

        return True

# ============================================================
# NEXUS — TRANSVERSAL CONTROL PLANE
# ============================================================

class Nexus:

    @staticmethod
    def govern():

        invariants = AMMCore.enforce_invariants()

        if not invariants["valid"]:
            raise RuntimeError("INVARIANT_FAILURE")

        return {
            "control_plane": "NEXUS",
            "authorized": True,
            "invariant_fingerprint": (
                invariants["fingerprint"]
            ),
            "execution_policy": {
                "validation_required": True,
                "verification_required": True,
                "audit_required": True,
                "unverified_learning": False,
                "max_cycles": 10,
                "max_reject_streak": 3
            }
        }

# ============================================================
# NRE — UNIFIED ORCHESTRATOR
# ============================================================

class NRE:

    def __init__(self):

        self.omega = OmegaEngine()
        self.executor = Executor()

    def process(self, raw_input):

        nexus = Nexus.govern()

        context = SIPE.compile(raw_input)

        validation = SemanticFirewall.validate(
            context
        )

        if not validation["valid"]:
            raise ValueError({
                "error": "SEMANTIC_VALIDATION_FAILED",
                "details": validation["errors"]
            })

        Storage.audit({
            "event": "INPUT_ACCEPTED",
            "intent_id": context["intent_id"],
            "nexus": nexus
        })

        execution = self.omega.execute_cycle(
            context,
            self.executor
        )

        response = {
            "system": "NRE-AMM-OMEGA",
            "version": "1.0.0",
            "intent_id": context["intent_id"],
            "status": execution["verification"]["status"],
            "nexus": nexus,
            "context": context,
            "execution": execution,
            "system_state": self.omega.state,
            "invariants": Invariants.RULES
        }

        return response

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "MISSING_OBJECTIVE",
            "usage": "python omega_engine.py \"objective\""
        }, indent=2))
        sys.exit(1)

    try:

        engine = NRE()

        output = engine.process(
            " ".join(sys.argv[1:])
        )

        print(json.dumps(
            output,
            indent=2,
            ensure_ascii=False
        ))

    except Exception as error:

        print(json.dumps({
            "system": "NRE-AMM-OMEGA",
            "status": "ERROR",
            "error": str(error)
        }, indent=2, ensure_ascii=False))

        sys.exit(1)
