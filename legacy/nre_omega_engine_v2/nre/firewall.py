"""L2 — Semantic Firewall (basado en reglas).

No es un clasificador semántico aprendido: aplica patrones explícitos y
auditables. Puede tener falsos positivos y falsos negativos; ver README.
"""

from __future__ import annotations

import re

from .text import fold

MAX_INPUT = 20000

RULES: dict[str, list[str]] = {
    "PROMPT_INJECTION": [
        r"\bignora(r)? (todas |todo |las |tus )*(instrucciones|reglas|indicaciones)",
        r"\bignore (all |any |the |your )*(previous |prior |above )?(instructions|rules)",
        r"\b(olvida|olvidate de) (tus|las|todas las) (reglas|instrucciones)",
        r"\b(revela|muestra|imprime|reveal|print|show)( me)? (tu |el |your |the )?(prompt|system prompt|instrucciones del sistema|prompt del sistema)",
        r"\b(modo desarrollador|developer mode|modo dios|god mode)\b",
        r"\bjailbreak\b",
        r"\b(sin|without|no) (restricciones|filtros|reglas|restrictions|filters|rules)\b",
        r"\b(actua|finge|pretend|act) (como si|as if|that) (no )?(tuvieras|you have|you had)? ?(no )?(reglas|limites|rules|limits)",
        r"\bdan\b",
    ],
    "DESTRUCTIVE_ACTION": [
        r"rm\s+-rf",
        r"\bdrop\s+(table|database)\b",
        r"\b(borra|borrar|elimina|eliminar|delete|wipe)\b.{0,30}\b(todo|todos|todas|toda la|la base de datos|el disco|all|everything|database|disk)\b",
        r"\b(formatea|formatear|format)\b.{0,20}\b(disco|servidor|disk|drive|server)\b",
        r"\b(destruye|destroy)\b",
    ],
    "MALICIOUS_INTENT": [
        r"\bhack(ea|ear|ing)?\b",
        r"\bbypass\b",
        r"\b(evade|evadir|evadas)\b.{0,30}\b(seguridad|controles|deteccion|security|detection)\b",
        r"\b(exploit|malware|ransomware|keylogger|botnet|phishing)\b",
        r"\b(roba|robar|steal)\b.{0,30}\b(contrasenas|passwords|credenciales|credentials|datos|data)\b",
    ],
    "SECRET_EXFILTRATION": [
        r"\b(envia|manda|filtra|exfiltra|send|leak|exfiltrate)\b.{0,40}\b(contrasena|password|credencial|credential|api[ _-]?key|token|secreto|secret)",
    ],
}


def validate(instruction: dict) -> dict:
    errors: list[str] = []
    violations: list[dict] = []

    objective = instruction.get("objective")
    if not isinstance(objective, str):
        errors.append("INVALID_OBJECTIVE")
    elif not objective.strip():
        errors.append("EMPTY_OBJECTIVE")
    elif len(objective) > MAX_INPUT:
        errors.append("INPUT_LIMIT_EXCEEDED")
    if not isinstance(instruction.get("constraints"), list):
        errors.append("INVALID_CONSTRAINTS")
    if not isinstance(instruction.get("evidence"), list):
        errors.append("INVALID_EVIDENCE")

    if isinstance(objective, str) and not errors:
        folded = fold(objective)
        for category, patterns in RULES.items():
            for pattern in patterns:
                match = re.search(pattern, folded)
                if match:
                    violations.append({"category": category, "rule": pattern, "match": match.group(0)})
                    break

    return {
        "layer": "L2_SEMANTIC_FIREWALL",
        "method": "rule_based",
        "allowed": not errors and not violations,
        "errors": errors,
        "violations": violations,
    }
