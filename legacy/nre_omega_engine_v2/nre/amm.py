"""L3 — AMM-CORE: plan de ejecución y aplicación de invariantes."""

from __future__ import annotations

from . import invariants


class AMMCore:

    @staticmethod
    def create_execution_plan(instruction: dict) -> dict:
        return {
            "objective": instruction["objective"],
            "intent_type": instruction["intent_type"],
            "action_class": instruction["action_class"],
            "constraints": instruction["constraints"],
            "stages": ["INTERPRETATION", "VALIDATION", "AUTHORIZATION", "EXECUTION",
                       "VERIFICATION", "AUDIT", "PERSISTENCE"],
            "output_contract": ["facts", "inferences", "unknowns", "proposed_solution"],
            "verification_required": True,
        }

    @staticmethod
    def enforce_invariants(record: dict, ids=None) -> dict:
        return invariants.enforce(record, ids)
