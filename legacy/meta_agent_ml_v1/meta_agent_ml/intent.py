"""CAPA 0 — Análisis de intención: objetivo, variables, restricciones, recursos y métricas."""

from __future__ import annotations

import re

from meta_agent_ml.knowledge import (
    CONSTRAINT_PATTERNS,
    DOMAIN_KEYWORDS,
    FEATURE_TERMS,
    METRIC_TERMS,
    RESOURCE_PATTERNS,
    DOMAINS,
)
from meta_agent_ml.models import Intent
from meta_agent_ml.text import contains_any, first_sentence, fold, tokenize


_OBJECTIVE_RE = re.compile(
    r"(?:"
    r"quiero|necesito|busco|debemos|se requiere|el objetivo(?:\s+es)?|"
    r"objetivo\s*:"
    r")\s+(.{8,240})",
    re.IGNORECASE,
)

_USING_RE = re.compile(
    r"(?:usando|utilizando|a partir de|con variables|con features|"
    r"con columnas|con datos de|features(?:\s+de)?|variables(?:\s+de)?)\s+"
    r"(.{6,200}?)(?:\.|;|,?\s+(?:en tiempo real|cumpliendo|con un presupuesto|con presupuesto|con una latencia|con latencia|desplegado|con alta )| con un | con una | pero | y un presupuesto| y latencia|$)",
    re.IGNORECASE,
)


def detect_domain(text: str) -> tuple[str, str]:
    folded = fold(text)
    for domain_id, label, keywords in DOMAIN_KEYWORDS:
        for kw in keywords:
            if fold(kw) in folded:
                return domain_id, label
    return "general", "problema general de ML"


def extract_objective(text: str) -> str:
    match = _OBJECTIVE_RE.search(text.strip())
    raw = match.group(1).strip() if match else first_sentence(text) or text.strip()
    raw = re.split(
        r",?\s+(?:usando|utilizando|a partir de|con un presupuesto|con presupuesto|"
        r"con latencia|con una latencia|en tiempo real|cumpliendo|desplegado|con alta )",
        raw,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return raw.strip().rstrip(".,;:")


def _looks_like_constraint(phrase: str) -> bool:
    folded = fold(phrase)
    forbidden = (
        "tiempo real", "privacidad", "presupuesto", "latencia", "hipaa",
        "on-premise", "on premise", "cumpliendo", "gdpr",
    )
    return any(item in folded for item in forbidden)


def extract_variables(text: str) -> list[str]:
    found: list[str] = []
    match = _USING_RE.search(text)
    if match:
        chunk = match.group(1)
        # Cut a trailing constraint tail if the terminator did not fire
        chunk = re.split(
            r",?\s+(?:en tiempo real|cumpliendo|con un presupuesto|con presupuesto|"
            r"con latencia|desplegado|con alta )",
            chunk,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        parts = re.split(r",| y | e ", chunk)
        for part in parts:
            cleaned = re.sub(r"\s+", " ", part).strip(" .;:()")
            if len(cleaned) >= 3 and not _looks_like_constraint(cleaned):
                found.append(cleaned)
    folded_text = fold(text)
    for term in FEATURE_TERMS:
        if not re.search(r"\b" + re.escape(fold(term)) + r"s?\b", folded_text):
            continue
        if _looks_like_constraint(term):
            continue
        if any(fold(term) == fold(x) or fold(term) in fold(x).split() or fold(x) in fold(term) for x in found):
            continue
        found.append(term)
    seen: set[str] = set()
    out = []
    for item in found:
        key = fold(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:12]


def extract_metrics(text: str, domain_id: str) -> list[str]:
    found: list[str] = []
    for default in DOMAINS.get(domain_id, {}).get("metricas_default", []):
        found.append(default)
    folded = fold(text)
    for term in METRIC_TERMS:
        if fold(term) in folded and not any(fold(term) in fold(x) or fold(x) in fold(term) for x in found):
            # Avoid promoting a constraint-only mention of latencia ahead of domain metrics:
            # it is still recorded, but after the domain defaults.
            found.append(term)
    return found[:8]


def extract_keywords(text: str, extra: list[str]) -> list[str]:
    tokens = tokenize(text, drop_stopwords=True)
    # Keep informative tokens (length >= 4) plus extras
    keys = []
    for tok in tokens:
        if len(tok) >= 4 and tok not in keys:
            keys.append(tok)
        if len(keys) >= 16:
            break
    for item in extra:
        for tok in tokenize(item, drop_stopwords=True):
            if tok not in keys:
                keys.append(tok)
    return keys[:24]



def _extract_by_patterns(text: str, patterns: list[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    for pattern, label in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        span = match.group(0).strip()
        phrase = span if len(span) > len(label) else label
        phrase = re.sub(r"\s+", " ", phrase).strip()
        if not any(fold(phrase) == fold(x) or fold(phrase) in fold(x) for x in found):
            found.append(phrase)
    return found


class IntentAnalyzer:
    """Extrae una intención formal a partir del texto libre de la solicitud."""

    def analyze(self, text: str) -> Intent:
        raw = (text or "").strip()
        if not raw:
            return Intent(
                objetivo="",
                dominio="general",
                etiqueta_dominio="problema general de ML",
                texto_original="",
            )
        domain_id, label = detect_domain(raw)
        objetivo = extract_objective(raw)
        variables = extract_variables(raw)
        restricciones = _extract_by_patterns(raw, CONSTRAINT_PATTERNS)
        recursos = _extract_by_patterns(raw, RESOURCE_PATTERNS)
        metricas = extract_metrics(raw, domain_id)
        extras = [objetivo, label, *variables, *restricciones, *recursos, *metricas]
        # also record explicit keyword hits used for domain
        domain_hits = []
        for did, _, kws in DOMAIN_KEYWORDS:
            if did == domain_id:
                domain_hits = contains_any(raw, list(kws))
                break
        return Intent(
            objetivo=objetivo,
            dominio=domain_id,
            etiqueta_dominio=label,
            variables=variables,
            restricciones=restricciones,
            recursos=recursos,
            metricas=metricas,
            palabras_clave=extract_keywords(raw, extras + domain_hits),
            texto_original=raw,
        )
