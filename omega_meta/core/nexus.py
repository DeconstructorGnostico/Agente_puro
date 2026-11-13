"""NEXUS — política de autorización (Authorizer) y límites por sesión.

- Petición de solo lectura: AUTO.
- Petición con efectos (enviar, comprar, publicar, borrar, ejecutar...): PENDING_AUTHORIZATION.
  Ya no cuenta como "bloqueo por daño": queda en espera de aprobación humana.
- Herramientas: lista blanca + permiso por herramienta (TOOL_AVAILABILITY != EXECUTION_PERMISSION).
- Límites por sesión con enfriamiento (no hay apagado permanente; defecto de omega_brain corregido).
"""
from __future__ import annotations

import re
import threading
import time
from typing import Callable

from .text import fold

SIDE_EFFECT_PATTERNS = [
    r"\b(envia|enviar|envie|manda|mandar|send|email|e-mail)\b",
    r"\b(publica|publicar|postea|postear|tuitea|tuitear|tweet|post (it|this|on))\b",
    r"\b(borra|borrar|elimina|eliminar|delete|remove) (el|la|los|las|mi|mis|the|my|this|these)? ?(archivo|archivos|carpeta|cuenta|correo|file|files|folder|account|repo|repositorio|base de datos|database)",
    r"\b(ejecuta|ejecutar|corre el|run the|execute)\b.{0,20}\b(comando|script|programa|command|program|en el servidor|on the server)",
    r"\b(despliega|desplegar|deploy)\b",
    r"\b(paga|pagar|compra|comprar|pay|buy|purchase|ordena|ordenar|order)\b",
    r"\b(transfiere|transferir|transfer|deposita|depositar)\b",
    r"\b(instala|instalar|install)\b",
    r"\b(reserva|reservar|book|agenda|agendar|schedule)\b.{0,20}\b(vuelo|hotel|mesa|cita|flight|table|appointment|meeting|reunion)",
]


def side_effects(text: str) -> list[str]:
    t = fold(text)
    return [p for p in SIDE_EFFECT_PATTERNS if re.search(p, t)]


class AuthorizationPolicy:
    def __init__(self, authorize_side_effects: bool = False,
                 callback: Callable[[dict], bool] | None = None,
                 tool_permissions: dict[str, bool] | None = None):
        self.authorize_side_effects = authorize_side_effects
        self.callback = callback
        self.tool_permissions = dict(tool_permissions or {})

    def decide(self, instruction: dict) -> dict:
        base = {"decided_by": "NEXUS", "action_class": instruction["action_class"]}
        if instruction["action_class"] == "read_only":
            return {**base, "authorized": True, "mode": "READ_ONLY_AUTO"}
        if self.callback is not None:
            ok = bool(self.callback(instruction))
            return {**base, "authorized": ok, "mode": "CALLBACK", "reason": None if ok else "DENIED_BY_CALLBACK"}
        if self.authorize_side_effects:
            return {**base, "authorized": True, "mode": "EXPLICIT_FLAG"}
        return {**base, "authorized": False, "mode": "PENDING_AUTHORIZATION",
                "reason": "SIDE_EFFECT_REQUIRES_HUMAN_APPROVAL"}

    def permit_tool(self, name: str, spec, request_auth: dict) -> bool:
        """Permiso por herramienta. Las herramientas con efectos necesitan autorización
        explícita de la petición Y permiso propio de la herramienta."""
        if not spec.side_effect:
            return True
        return bool(request_auth.get("authorized") and request_auth.get("mode") in {"EXPLICIT_FLAG", "CALLBACK", "HUMAN"}
                    and self.tool_permissions.get(name))


class SessionGuard:
    """Interruptor por sesión: N rechazos en una ventana => enfriamiento temporal.
    Afecta solo a esa sesión; se rearma solo al terminar el enfriamiento o con reset()."""

    def __init__(self, max_rejections: int = 5, window_s: float = 300, cooldown_s: float = 60,
                 clock: Callable[[], float] = time.monotonic):
        self.max_rejections, self.window_s, self.cooldown_s = max_rejections, window_s, cooldown_s
        self.clock = clock
        self._events: dict[str, list[float]] = {}
        self._cool: dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, session: str) -> dict:
        now = self.clock()
        with self._lock:
            until = self._cool.get(session)
            if until and now < until:
                return {"allowed": False, "reason": "SESSION_COOLDOWN", "retry_after_s": round(until - now, 1)}
            if until:
                self._cool.pop(session, None)
                self._events.pop(session, None)
            return {"allowed": True}

    def record(self, session: str, rejected: bool) -> None:
        now = self.clock()
        with self._lock:
            ev = [t for t in self._events.get(session, []) if now - t <= self.window_s]
            if rejected:
                ev.append(now)
            self._events[session] = ev
            if len(ev) >= self.max_rejections:
                self._cool[session] = now + self.cooldown_s

    def reset(self, session: str) -> None:
        with self._lock:
            self._events.pop(session, None)
            self._cool.pop(session, None)
