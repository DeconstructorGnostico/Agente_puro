"""L1 — SIPE: Semantic Intention Processing Engine.

Convierte una petición en lenguaje libre en una instrucción formal
(objetivo, tipo de intención, clase de acción, restricciones, evidencia,
referencias y diagnóstico de ambigüedad). Basado en reglas.
"""

from __future__ import annotations

import re
import uuid
from typing import Iterable

from .text import fold, tokens

SCHEMA_VERSION = "nre.instruction/2"

# Verbos que implican efectos fuera del modelo (requieren autorización).
SIDE_EFFECT_PATTERNS = [
    r"\b(envia|enviar|manda|mandar|send|email)\b",
    r"\b(publica|publicar|postea|postear|post|tuitea|tweet)\b",
    r"\b(borra|borrar|elimina|eliminar|delete|remove)\b",
    r"\b(ejecuta|ejecutar|corre el|run the|execute)\b",
    r"\b(despliega|desplegar|deploy)\b",
    r"\b(paga|pagar|compra|comprar|pay|buy|purchase)\b",
    r"\b(transfiere|transferir|transfer)\b",
    r"\b(instala|instalar|install)\b",
    r"\b(modifica|modificar|actualiza la base|escribe en|write to|overwrite)\b",
]

QUESTION_HINTS = r"(\?|^(que|como|cual|cuales|cuando|donde|quien|por que|cuanto|what|how|which|when|where|who|why)\b)"

VAGUE_WORDS = {
    "hazlo", "haz", "eso", "esto", "aquello", "arregla", "arreglalo", "lo", "la",
    "de", "siempre", "mismo", "igual", "cosa", "continua", "sigue", "do", "it",
    "fix", "that", "this", "same", "thing", "again", "otra", "vez", "ya", "ahora",
    "por", "favor", "please", "now", "el", "lo", "que", "dije",
}

CONSTRAINT_PATTERNS = [
    r"\b(sin [^,.;]+)",
    r"\b(solo [^,.;]+)",
    r"\b(maximo [^,.;]+)",
    r"\b(en menos de [^,.;]+)",
    r"\b(without [^,.;]+)",
    r"\b(only [^,.;]+)",
]

MIN_WORDS = 3


def _evidence(items: Iterable | None) -> list[dict]:
    out = []
    for item in items or []:
        if isinstance(item, str):
            out.append({"source": "caller", "text": item})
        elif isinstance(item, dict) and "text" in item:
            out.append({"source": item.get("source", "caller"), "text": str(item["text"])})
        else:
            raise ValueError("INVALID_EVIDENCE_ITEM")
    return out


def detect_ambiguity(normalized: str) -> list[str]:
    reasons = []
    words = tokens(normalized)
    if len(words) < MIN_WORDS:
        reasons.append("AMBIGUOUS_TOO_SHORT")
    if words and all(w in VAGUE_WORDS for w in words):
        reasons.append("AMBIGUOUS_VAGUE_REFERENCE")
    return reasons


def compile(raw_input, constraints=None, evidence=None, references=None) -> dict:
    if not isinstance(raw_input, str):
        raise ValueError("INVALID_INPUT_TYPE")
    normalized = " ".join(raw_input.split())
    if not normalized:
        raise ValueError("EMPTY_INPUT")

    folded = fold(normalized)
    side_effects = [p for p in SIDE_EFFECT_PATTERNS if re.search(p, folded)]
    is_question = bool(re.search(QUESTION_HINTS, folded))

    extracted = []
    for pattern in CONSTRAINT_PATTERNS:
        extracted += [m.strip() for m in re.findall(pattern, folded)]

    if side_effects:
        intent_type = "action"
    elif is_question:
        intent_type = "question"
    else:
        intent_type = "analysis"

    ambiguity = detect_ambiguity(normalized)

    return {
        "schema_version": SCHEMA_VERSION,
        "intent_id": str(uuid.uuid4()),
        "raw_input": raw_input,
        "normalized_input": normalized,
        "objective": normalized,
        "intent_type": intent_type,
        "action_class": "side_effect" if side_effects else "read_only",
        "side_effect_signals": side_effects,
        "constraints": list(constraints or []) + extracted,
        "evidence": _evidence(evidence),
        "references": [str(r) for r in (references or [])],
        "ambiguity": {"ambiguous": bool(ambiguity), "reasons": ambiguity},
        # I01: la entrada nunca nace verificada; solo el firewall la marca.
        "validated": False,
    }
