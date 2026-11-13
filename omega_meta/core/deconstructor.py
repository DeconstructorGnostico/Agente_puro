"""GNOSTIC DECONSTRUCTOR — etapas 02 y 04–08 del método + tabla de decisión.

Produce D(x) = {O, F, A, H, C, V, U, K, E, R} antes de cualquier decisión.
Correcciones sobre deconstructor_gnostico.py:
- La negación se detecta en cualquier posición (no/not/nunca/jamás/never/n't), no solo
  como primera palabra: «El sistema es seguro.» vs «El sistema no es seguro.» => conflicto.
- Conflictos de valor con el mismo sujeto: «tiene 8 GB» vs «tiene 16 GB» => conflicto.
- Antónimos frecuentes (seguro/inseguro, true/false, legal/ilegal...).
- Una afirmación sin evidencia verificada es CLAIM, nunca FACT (se conserva su acierto).
"""
from __future__ import annotations

import re
import unicodedata

from .rules import RuleBase
from .text import fold

NEG = {"no", "not", "nunca", "jamas", "never", "tampoco", "ni"}
ANTONYMS = {"inseguro": "seguro", "insegura": "segura", "falso": "verdadero", "falsa": "verdadera",
            "false": "true", "insecure": "secure", "unsafe": "safe", "inactivo": "activo",
            "imposible": "posible", "impossible": "possible", "incorrecto": "correcto",
            "incorrect": "correct", "ilegal": "legal", "illegal": "legal", "invalido": "valido",
            "invalid": "valid", "desconectado": "conectado", "offline": "online"}
COPULA = re.compile(r"\b(es|son|esta|estan|era|eran|fue|fueron|tiene|tienen|mide|miden|cuesta|cuestan|pesa|pesan|vale|valen|"
                    r"is|are|was|were|has|have|costs?|weighs?|measures?|contains?|contiene|contienen|usa|usan|uses?)\b")
NUM = re.compile(r"\d+(?:[.,]\d+)?")
VAR = re.compile(r"(\d+(?:[.,]\d+)?\s?(?:%|ms|s|gb|mb|tb|kb|usd|mxn|pesos|dolares|horas|dias|semanas|meses|anos|km|kg|m)\b|\b(?:menor|mayor|menos|mas) (?:a|de|que) \d+[^ ,.;]*)")
DEP_NEXT = re.compile(r"^(por lo tanto|entonces|en consecuencia|asi que|therefore|thus|so|hence)\b")


def normalize(value) -> str:
    if not isinstance(value, str):
        raise TypeError("INPUT_MUST_BE_STRING")
    value = unicodedata.normalize("NFC", value)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        raise ValueError("EMPTY_INPUT")
    return value


def split_propositions(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text)
    return [p.strip() for p in parts if p and len(p.strip()) > 1][:60]


def _canon(text: str):
    t = fold(text).replace("n't", " not")
    toks = re.findall(r"[a-z0-9]+", t)
    parity = 0
    out = []
    for tok in toks:
        if tok in NEG:
            parity ^= 1
            continue
        if tok in ANTONYMS:
            parity ^= 1
            tok = ANTONYMS[tok]
        out.append(tok)
    return out, parity


def _overlap(a: str, b: str) -> float:
    ta, tb = set(re.findall(r"[a-z0-9]+", fold(a))), set(re.findall(r"[a-z0-9]+", fold(b)))
    return len(ta & tb) / max(1, len(ta))


def detect_contradictions(props: list[dict]) -> list[dict]:
    """Conflictos de negación (en cualquier posición) y de valor (mismo sujeto, otro número)."""
    found = []
    declarative = [p for p in props if p["kind"] in {"CLAIM", "FACT"} and not p["text"].rstrip().endswith("?")]
    for i, a in enumerate(declarative):
        ta, pa = _canon(a["text"])
        for b in declarative[i + 1:]:
            tb, pb = _canon(b["text"])
            kind = None
            if ta == tb and pa != pb and len(ta) >= 2:
                kind = "NEGATION_CONFLICT"
            elif pa == pb and len(ta) == len(tb) >= 3 and COPULA.search(fold(a["text"])):
                na = [x for x in ta if NUM.fullmatch(x)]
                nb = [x for x in tb if NUM.fullmatch(x)]
                sa = [x if not NUM.fullmatch(x) else "<n>" for x in ta]
                sb = [x if not NUM.fullmatch(x) else "<n>" for x in tb]
                if na and sa == sb and na != nb:
                    kind = "VALUE_CONFLICT"
            if not kind:
                continue
            status, winner = "UNRESOLVED", None
            sa, sb = a.get("truth_state") == "SUPPORTED", b.get("truth_state") == "SUPPORTED"
            if sa != sb:
                status, winner = "RESOLVED_BY_EVIDENCE", a["id"] if sa else b["id"]
            found.append({"a": a["id"], "b": b["id"], "type": kind, "status": status, "supported": winner})
    return found


def analyze_dependencies(props: list[dict]) -> dict:
    ids = {p["id"] for p in props}
    graph = {p["id"]: list(p.get("dependencies", [])) for p in props}
    unknown = [(n, d) for n, ds in graph.items() for d in ds if d not in ids]
    cycle = False
    state: dict[str, int] = {}

    def visit(n):
        nonlocal cycle
        if state.get(n) == 1:
            cycle = True
            return
        if state.get(n) == 2:
            return
        state[n] = 1
        for d in graph.get(n, []):
            if d in ids:
                visit(d)
        state[n] = 2

    for n in graph:
        visit(n)
    return {"graph": graph, "cycle": cycle, "unknown_dependencies": unknown}


def deconstruct(raw: str, rules: RuleBase, propositions: list[dict] | None = None, truth=None) -> dict:
    """Etapas 04–08. `propositions` permite entrada estructurada (con kind/dependencias).
    `truth` (TruthEngine) asigna a cada afirmación su estado de verdad (etapa 08)."""

    # 04 DECOMPOSE
    items = propositions or [{"text": t} for t in split_propositions(raw)]
    props, flags = [], []
    for i, it in enumerate(items):
        text = normalize(it["text"])
        deps = list(it.get("dependencies", []))
        if not propositions and i > 0 and DEP_NEXT.search(fold(text)):
            deps.append(f"P{i}")
        props.append({"id": f"P{i + 1}", "text": text, "asserted_kind": it.get("kind"),
                      "evidence_ids": list(it.get("evidence_ids", [])), "dependencies": deps})
    # 05 CLASSIFY (reglas mutables; nunca producen FACT)
    for p in props:
        kind = rules.classify(p["text"])
        if p["text"].rstrip().endswith("?") and kind == "CLAIM":
            kind = "OBJECTIVE"
        p["kind"] = kind
        # 08 EVIDENCE VALIDATION — T(x): solo SUPPORTED puede ser FACT
        if kind in {"CLAIM", "UNKNOWN"} or p["asserted_kind"] == "FACT":
            a = truth.assess(p["text"]) if truth is not None else {"state": "UNDETERMINED", "evidence_ids": []}
            p["truth_state"] = a["state"]
            p["evidence_ids"] = a.get("evidence_ids", [])
            if a["state"] == "SUPPORTED":
                p["kind"] = "FACT"
                p["verified_evidence"] = a["evidence_ids"]
            elif p["asserted_kind"] == "FACT":
                flags.append({"id": p["id"], "flag": "ASSERTED_FACT_WITHOUT_SUPPORT", "truth_state": a["state"]})
    # 06 DEPENDENCY ANALYSIS
    deps = analyze_dependencies(props)
    # 07 CONTRADICTION DETECTION
    contradictions = detect_contradictions(props)
    for p in props:
        if p.get("truth_state") == "CONTRADICTED":
            contradictions.append({"a": p["id"], "b": "EVIDENCE", "type": "EVIDENCE_CONFLICT",
                                   "status": "UNRESOLVED", "supported": None})
    folded = fold(raw)
    variables = sorted({m.group(0).strip() for m in VAR.finditer(folded)})[:20]

    def pick(kind):
        return [{"id": p["id"], "text": p["text"], "truth_state": p.get("truth_state"),
                 **({"verified_evidence": p["verified_evidence"]} if p.get("verified_evidence") else {})}
                for p in props if p["kind"] == kind]

    unknowns = pick("UNKNOWN") + [{"id": p["id"], "text": p["text"]} for p in props
                                  if p["kind"] == "OBJECTIVE" and p["text"].endswith("?")]
    return {
        "objectives": pick("OBJECTIVE"), "facts": pick("FACT"), "claims": pick("CLAIM"),
        "assumptions": pick("ASSUMPTION"), "hypotheses": pick("HYPOTHESIS"),
        "constraints": pick("CONSTRAINT"), "variables": variables, "unknowns": unknowns,
        "contradictions": contradictions, "dependencies": deps,
        "evidence": [dict(id=e.id, text=e.statement, source=e.source_id, relation=e.relation, reviewed_by=e.reviewed_by)
                     for e in (truth.evidence if truth is not None else [])],
        "refuted": [{"id": p["id"], "text": p["text"]} for p in props if p.get("truth_state") == "REFUTED"],
        "flags": flags, "propositions": len(props),
    }


def decide(dx: dict, invariants_ok: bool = True) -> tuple[str, list[str]]:
    """Tabla de decisión del método (sin la parte de firewall, que va antes)."""
    if not invariants_ok:
        return "HALT", ["INVARIANT_VIOLATED"]
    if dx["dependencies"]["cycle"]:
        return "HALT", ["CIRCULAR_DEPENDENCY"]
    if dx["dependencies"]["unknown_dependencies"]:
        return "HALT", ["UNKNOWN_DEPENDENCY"]
    unresolved = [c for c in dx["contradictions"] if c["status"] == "UNRESOLVED"]
    if unresolved:
        reasons = ["UNRESOLVED_CONTRADICTION:" + ",".join(f"{c['a']}~{c['b']}" for c in unresolved)]
        if any(c.get("type") == "EVIDENCE_CONFLICT" for c in unresolved):
            reasons.append("JUICIO_SUSPENDIDO: las fuentes se contradicen; no se elige un lado sin más evidencia")
        return "HALT", reasons
    if dx["flags"]:
        return "REJECT", ["INSUFFICIENT_EVIDENCE_FOR_FACT:" + ",".join(f["id"] for f in dx["flags"])]
    if dx.get("refuted"):
        return "PROCESS", ["PROCESS+REFUTED_PREMISE:" + ",".join(r["id"] for r in dx["refuted"])]
    if dx["unknowns"]:
        return "PROCESS", ["PROCESS+UNKNOWN"]
    return "PROCESS", []
