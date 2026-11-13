"""L4 — OMEGA_CONTEXT_ENGINE: el integrador.

Orquesta SIPE (L1), Semantic Firewall (L2), AMM-CORE (L3), Gateway (L5),
Verificación (L6), Persistencia (L7) y NEXUS mediante una máquina de
estados explícita. Cada ciclo termina en COMPLETED pasando siempre por
PERSISTING, incluso si fue REJECTED o HALT.
"""

from __future__ import annotations

import hashlib
import json
from typing import Callable

from . import firewall, sipe
from .amm import AMMCore
from .gateway import Executor, ExecutionTimeout, ModelGateway
from .learning import LearningController
from .nexus import AuthorizationPolicy, Nexus
from .storage import Storage
from .verification import VerificationPipeline

VERSION = "2.0.0"
AUTHOR = "Adrian Mendez Millan"


class States:
    RECEIVED = "RECEIVED"
    INTERPRETING = "INTERPRETING"
    VALIDATING = "VALIDATING"
    AWAITING_AUTH = "AWAITING_AUTH"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMMITTED = "COMMITTED"
    LEARNING = "LEARNING"
    REJECTED = "REJECTED"
    HALT = "HALT"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"


S = States

TRANSITIONS: dict[str, set[str]] = {
    S.RECEIVED: {S.INTERPRETING, S.HALT},
    S.INTERPRETING: {S.VALIDATING, S.REJECTED, S.HALT},
    S.VALIDATING: {S.AWAITING_AUTH, S.REJECTED, S.HALT},
    S.AWAITING_AUTH: {S.EXECUTING, S.REJECTED, S.HALT},
    S.EXECUTING: {S.VERIFYING, S.HALT},
    S.VERIFYING: {S.COMMITTED, S.REJECTED, S.HALT},
    S.COMMITTED: {S.LEARNING, S.HALT},
    S.LEARNING: {S.PERSISTING, S.HALT},
    S.REJECTED: {S.INTERPRETING, S.PERSISTING, S.HALT},
    S.HALT: {S.PERSISTING},
    S.PERSISTING: {S.COMPLETED},
    S.COMPLETED: set(),
}

# Rechazos que admiten reintento con reinterpretación (los de seguridad no).
RETRYABLE = {"AMBIGUOUS_INTENT", "REFERENCE_MISMATCH", "INVALID_OUTPUT_CONTRACT",
             "INVALID_RESULT", "INVARIANT_VIOLATION"}


class InvalidTransition(RuntimeError):
    pass


class CycleStateMachine:
    """Máquina de estados de un ciclo. Cada transición se audita (I05)."""

    def __init__(self, storage: Storage, cycle_id: str):
        self.storage = storage
        self.cycle_id = cycle_id
        self.state: str | None = None
        self.trace: list[str] = []
        self.audited = 0

    def enter(self, new_state: str, reason: str | None = None) -> None:
        if self.state is None:
            if new_state != S.RECEIVED:
                raise InvalidTransition(f"INVALID_TRANSITION: <start> -> {new_state}")
        elif new_state not in TRANSITIONS[self.state]:
            raise InvalidTransition(f"INVALID_TRANSITION: {self.state} -> {new_state}")
        previous, self.state = self.state, new_state
        self.trace.append(new_state)
        self.storage.audit({"event": "CYCLE_TRANSITION", "cycle_id": self.cycle_id,
                            "previous": previous, "current": new_state, "reason": reason})
        self.audited += 1


class OmegaContextEngine:
    """Motor integrador NRE–AMM–OMEGA (API pública: `process`, `reset`, `rollback_learning`)."""

    def __init__(self, runtime_dir="nre_runtime", provider=None, policy: AuthorizationPolicy | None = None,
                 verifiers=None, max_cycles: int = 100, max_reject_streak: int = 3,
                 max_retries: int = 2, timeout_s: float = 120.0,
                 retry_handler: Callable[[str, list[str]], str | None] | None = None):
        self.storage = Storage(runtime_dir)
        self.nexus = Nexus(policy, max_cycles, max_reject_streak, max_retries, timeout_s)
        self.executor = Executor(ModelGateway(provider), timeout_s)
        self.verification = VerificationPipeline(verifiers)
        self.learning = LearningController(self.storage)
        self.retry_handler = retry_handler
        self.state = self.storage.load_state({
            "status": "READY", "cycles": 0, "reject_streak": 0,
            "max_cycles": max_cycles, "max_reject_streak": max_reject_streak,
            "halt_reason": None, "last_cycle": None, "version": VERSION,
        })
        self.state["max_cycles"] = max_cycles
        self.state["max_reject_streak"] = max_reject_streak

    # ------------------------------------------------------------------
    def _save(self, reason):
        self.storage.save_state(self.state, reason)

    def _halt_engine(self, reason):
        self.state["status"] = "HALTED"
        self.state["halt_reason"] = reason
        self.storage.audit({"event": "ENGINE_HALTED", "reason": reason})

    def reset(self, authorized_by: str) -> None:
        """Reanuda un motor detenido. Requiere identificar a quien autoriza (auditado)."""
        if not authorized_by:
            raise ValueError("RESET_REQUIRES_AUTHORIZATION")
        self.state.update({"status": "READY", "reject_streak": 0, "cycles": 0, "halt_reason": None})
        self.storage.audit({"event": "ENGINE_RESET", "authorized_by": authorized_by})
        self._save("RESET")

    def rollback_learning(self, entry_id: str) -> bool:
        return self.learning.rollback(entry_id)

    # ------------------------------------------------------------------
    def process(self, raw_input, constraints=None, evidence=None, references=None) -> dict:
        nexus = self.nexus.govern()

        if self.state["status"] != "HALTED" and self.state["cycles"] >= self.state["max_cycles"]:
            self._halt_engine("MAX_CYCLES_REACHED")
            self._save("MAX_CYCLES_REACHED")
        if self.state["status"] == "HALTED":
            self.storage.audit({"event": "REQUEST_REFUSED", "reason": "ENGINE_HALTED",
                                "halt_reason": self.state["halt_reason"]})
            return {"system": "NRE-AMM-OMEGA", "version": VERSION, "outcome": "HALT",
                    "decision": "BLOCK", "status": None, "reasons": ["ENGINE_HALTED", self.state["halt_reason"]],
                    "trace": [], "invariants": {}, "engine_state": dict(self.state), "nexus": nexus}

        cycle_id = hashlib.sha256(f"{self.storage._seq}:{raw_input!r}".encode()).hexdigest()[:16]
        sm = CycleStateMachine(self.storage, cycle_id)
        rec = {"cycle_id": cycle_id, "reasons": [], "instruction": None, "firewall": None,
               "authorization": None, "plan": None, "result": None, "verification": None,
               "learning": {"written": False}, "retries": 0, "execution_requested": False,
               "invariants": {}}
        sm.enter(S.RECEIVED)
        try:
            self._run(sm, rec, raw_input, constraints, evidence, references)
        except Exception as error:  # todo error interno queda auditado y termina en HALT
            rec["reasons"].append(f"INTERNAL_ERROR: {type(error).__name__}: {error}")
            self.storage.audit({"event": "ERROR", "cycle_id": cycle_id, "error": str(error),
                                "type": type(error).__name__})
            if sm.state not in (S.HALT, S.PERSISTING, S.COMPLETED):
                sm.enter(S.HALT, "INTERNAL_ERROR")

        terminal = [st for st in sm.trace if st in (S.COMMITTED, S.REJECTED, S.HALT)]
        outcome = terminal[-1] if terminal else S.HALT
        rec["outcome"] = outcome
        if sm.state != S.PERSISTING:
            sm.enter(S.PERSISTING)

        # Contadores del motor (I07)
        self.state["cycles"] += 1
        self.state["reject_streak"] = 0 if outcome == "COMMITTED" else self.state["reject_streak"] + 1
        if self.state["reject_streak"] >= self.state["max_reject_streak"]:
            self._halt_engine("REJECTION_THRESHOLD")
        elif self.state["cycles"] >= self.state["max_cycles"]:
            self._halt_engine("MAX_CYCLES_REACHED")
        self.state["last_cycle"] = {"cycle_id": cycle_id, "outcome": outcome,
                                    "status": (rec["verification"] or {}).get("status")}

        result_hash = hashlib.sha256(json.dumps(rec["result"], sort_keys=True, default=str).encode()).hexdigest()
        self.storage.audit({
            "event": "CYCLE_PERSISTED", "cycle_id": cycle_id, "outcome": outcome,
            "intent_id": (rec["instruction"] or {}).get("intent_id"),
            "reasons": rec["reasons"], "trace": list(sm.trace),
            "firewall": rec["firewall"], "authorization": rec["authorization"],
            "verification_status": (rec["verification"] or {}).get("status"),
            "result_hash": result_hash, "retries": rec["retries"],
        })
        self._save(f"CYCLE_{outcome}")
        sm.enter(S.COMPLETED)

        final = dict(rec, trace=list(sm.trace), audited_transitions=sm.audited,
                     engine=dict(self.state), state_hash_on_disk=self.storage.state_hash_on_disk(),
                     last_audited_state_hash=self.storage.last_audited_state_hash())
        report = AMMCore.enforce_invariants(final)
        rec["invariants"]["final"] = report
        if not report["valid"]:
            self.storage.audit({"event": "INVARIANT_REPORT_FAILED", "cycle_id": cycle_id,
                                "failed": report["failed"]})

        status = (rec["verification"] or {}).get("status") if outcome == "COMMITTED" else None
        return {
            "system": "NRE-AMM-OMEGA", "version": VERSION, "author": AUTHOR,
            "cycle_id": cycle_id, "intent_id": (rec["instruction"] or {}).get("intent_id"),
            "outcome": outcome, "decision": "ALLOW" if outcome == "COMMITTED" else "BLOCK",
            "status": status, "reasons": rec["reasons"], "trace": list(sm.trace),
            "instruction": rec["instruction"], "firewall": rec["firewall"],
            "authorization": rec["authorization"], "plan": rec["plan"], "result": rec["result"],
            "verification": rec["verification"], "learning": rec["learning"],
            "retries": rec["retries"], "invariants": rec["invariants"],
            "engine_state": dict(self.state), "nexus": nexus,
        }

    # ------------------------------------------------------------------
    def _reject(self, sm, rec, reason) -> bool:
        """Entra en REJECTED. Devuelve True si se debe reintentar (reinterpretando)."""
        rec["reasons"].append(reason)
        sm.enter(S.REJECTED, reason)
        code = reason.split(":")[0]
        if code not in RETRYABLE or self.retry_handler is None:
            sm.enter(S.PERSISTING, "FINAL_REJECTION")
            return False
        if rec["retries"] >= self.nexus.max_retries:
            rec["reasons"].append("RETRY_LIMIT_REACHED")
            sm.enter(S.HALT, "RETRY_LIMIT_REACHED")
            return False
        return True

    def _run(self, sm, rec, raw_input, constraints, evidence, references):
        current_input = raw_input
        while True:
            verdict = self._attempt(sm, rec, current_input, constraints, evidence, references)
            if verdict is None:
                return
            # reintento autorizado: pedir aclaración y volver a INTERPRETING
            new_input = self.retry_handler(current_input, list(rec["reasons"]))
            if not new_input:
                sm.enter(S.PERSISTING, "RETRY_DECLINED")
                return
            rec["retries"] += 1
            self.storage.audit({"event": "RETRY_AUTHORIZED", "cycle_id": rec["cycle_id"],
                                "attempt": rec["retries"]})
            current_input = new_input

    def _attempt(self, sm, rec, raw_input, constraints, evidence, references):
        """Devuelve 'RETRY' si hay que reintentar, None si el ciclo ya terminó su ruta."""
        def reject(reason):
            return "RETRY" if self._reject(sm, rec, reason) else None

        rec["execution_requested"] = False
        rec["result"] = rec["verification"] = rec["authorization"] = rec["firewall"] = None

        # L1 — SIPE
        sm.enter(S.INTERPRETING)
        try:
            instruction = sipe.compile(raw_input, constraints, evidence, references)
        except ValueError as error:
            return reject(f"INTERPRETATION_FAILED:{error}")
        rec["instruction"] = instruction
        if instruction["ambiguity"]["ambiguous"]:
            return reject("AMBIGUOUS_INTENT:" + ",".join(instruction["ambiguity"]["reasons"]))

        # L2 — Semantic Firewall
        sm.enter(S.VALIDATING)
        fw = firewall.validate(instruction)
        rec["firewall"] = fw
        if not fw["allowed"]:
            detail = fw["errors"] + [v["category"] for v in fw["violations"]]
            return reject("FIREWALL_REJECTED:" + ",".join(detail))
        instruction["validated"] = True

        # NEXUS — autorización
        sm.enter(S.AWAITING_AUTH)
        auth = self.nexus.policy.decide(instruction)
        rec["authorization"] = auth
        if not auth["authorized"]:
            return reject(f"AUTHORIZATION_DENIED:{auth.get('reason')}")
        rec["execution_requested"] = True
        pre = AMMCore.enforce_invariants(dict(rec, trace=list(sm.trace)), ["I01", "I03", "I04"])
        rec["invariants"]["pre_execution"] = pre
        if not pre["valid"]:
            rec["reasons"].append("INVARIANT_VIOLATION:" + ",".join(pre["failed"]))
            sm.enter(S.HALT, "INVARIANT_VIOLATION")
            return None

        # L3/L5 — plan y ejecución
        sm.enter(S.EXECUTING)
        plan = AMMCore.create_execution_plan(instruction)
        rec["plan"] = plan
        try:
            result = self.executor.run(instruction, plan)
        except ExecutionTimeout as error:
            rec["reasons"].append(str(error))
            sm.enter(S.HALT, "EXECUTION_TIMEOUT")
            return None
        except Exception as error:
            rec["reasons"].append(f"EXECUTION_ERROR: {type(error).__name__}: {error}")
            sm.enter(S.HALT, "EXECUTION_ERROR")
            return None
        rec["result"] = result

        # L6 — verificación
        sm.enter(S.VERIFYING)
        verification = self.verification.run(instruction, result)
        rec["verification"] = verification
        if verification["status"] == "REJECTED":
            return reject(verification.get("reason", "INVALID_RESULT"))
        post = AMMCore.enforce_invariants(dict(rec, trace=list(sm.trace), outcome="COMMITTED"),
                                          ["I02", "I03", "I08", "I09"])
        rec["invariants"]["post_verification"] = post
        if not post["valid"]:
            return reject("INVARIANT_VIOLATION:" + ",".join(post["failed"]))

        sm.enter(S.COMMITTED, verification["status"])
        sm.enter(S.LEARNING)
        rec["learning"] = self.learning.process(instruction, result, verification)
        learn = AMMCore.enforce_invariants(rec, ["I06"])
        rec["invariants"]["learning"] = learn
        if not learn["valid"]:
            self.learning.rollback(rec["learning"]["entry_id"])
            rec["reasons"].append("INVARIANT_VIOLATION:I06")
            sm.enter(S.HALT, "INVARIANT_VIOLATION")
            return None
        sm.enter(S.PERSISTING)
        return None


# Alias con el nombre original del orquestador.
NRE = OmegaContextEngine
