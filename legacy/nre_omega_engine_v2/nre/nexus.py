"""NEXUS — plano de control transversal: política de autorización y límites."""

from __future__ import annotations

from typing import Callable

from . import invariants


class AuthorizationPolicy:
    """Decide si una instrucción validada puede ejecutarse.

    - Acciones de solo lectura (preguntas, análisis): autorizadas automáticamente.
    - Acciones con efectos (enviar, borrar, publicar, pagar, ejecutar...):
      DENEGADAS por defecto. Se autorizan solo con `authorize_side_effects=True`
      (p. ej. la bandera --authorize del CLI) o si `callback(instruction)` devuelve True.
    """

    def __init__(self, authorize_side_effects: bool = False,
                 callback: Callable[[dict], bool] | None = None):
        self.authorize_side_effects = authorize_side_effects
        self.callback = callback

    def decide(self, instruction: dict) -> dict:
        action_class = instruction.get("action_class")
        if action_class == "read_only":
            return {"authorized": True, "mode": "READ_ONLY_AUTO", "action_class": action_class}
        if self.callback is not None:
            granted = bool(self.callback(instruction))
            return {"authorized": granted, "mode": "CALLBACK", "action_class": action_class,
                    "reason": None if granted else "DENIED_BY_CALLBACK"}
        if self.authorize_side_effects:
            return {"authorized": True, "mode": "EXPLICIT_FLAG", "action_class": action_class}
        return {"authorized": False, "mode": "DEFAULT_DENY", "action_class": action_class,
                "reason": "SIDE_EFFECT_REQUIRES_AUTHORIZATION"}


class Nexus:

    def __init__(self, policy: AuthorizationPolicy | None = None, max_cycles: int = 100,
                 max_reject_streak: int = 3, max_retries: int = 2, timeout_s: float = 120.0):
        self.policy = policy or AuthorizationPolicy()
        self.max_cycles = max_cycles
        self.max_reject_streak = max_reject_streak
        self.max_retries = max_retries
        self.timeout_s = timeout_s

    def govern(self) -> dict:
        return {
            "control_plane": "NEXUS",
            "invariant_fingerprint": invariants.fingerprint(),
            "execution_policy": {
                "validation_required": True,
                "authorization": "read_only=auto, side_effect=deny_by_default",
                "verification_required": True,
                "audit_required": True,
                "unverified_learning": False,
                "max_cycles": self.max_cycles,
                "max_reject_streak": self.max_reject_streak,
                "max_retries": self.max_retries,
                "timeout_s": self.timeout_s,
            },
        }
