"""OMEGA CONTROL LOOP — Agente Puro NRE–AMM–OMEGA.

T(x) = V(E(D(N(x))))  y la secuencia del Deconstructor Gnóstico:

 01 INPUT → 02 NORMALIZE → 03 FIREWALL → 04 DECOMPOSE → 05 CLASSIFY →
 06 DEPENDENCY_ANALYSIS → 07 CONTRADICTION_DETECTION → 08 EVIDENCE_VALIDATION →
 09 INVARIANT_CHECK → 10 REASONING (PLAN → AUTHORIZE → EXECUTE) → 11 RECONSTRUCTION →
 12 VERIFY → 13 OUTPUT → PERSIST

Capas: L0 invariante raíz · L1 SIPE · L2 firewall · L3 deconstructor · L4 evidencia/verdad
· L5 razonamiento OMEGA (planner/executor/critic + equipo) · L6 aprendizaje mutable (DGM)
· L7 estado de verdad + auditoría · NEXUS transversal (autorización y límites).
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from omega_meta.agent import critic, loop, planner as planner_mod, router
from omega_meta.agent.memory import AMMCore
from omega_meta.agent.tools import ALL_ROLES, SafeCalculator, build_registry
from omega_meta.config import Config, default_config

from . import classifier as classifier_mod
from . import deconstructor, firewall, root
from .nexus import AuthorizationPolicy, SessionGuard, side_effects
from .persistence import VersionedState
from .rules import RuleBase
from .storage import Storage
from .text import fold
from .truth import FORBIDDEN_ACTORS, TruthEngine, TruthError
from .verification import verify

ENGINE = "AGENTE_PURO_NRE_AMM_OMEGA"
MAX_INGEST_ITEMS = 20

# Flujo canónico del documento «Arquitectura del Agente Puro v1.0» → etapas internas.
CANONICAL_FLOW = {
    "INPUT": ["INPUT"], "SIPE": ["NORMALIZE"], "FIREWALL": ["FIREWALL"],
    "DECONSTRUCT": ["DECOMPOSE", "CLASSIFY", "DEPENDENCY_ANALYSIS", "CONTRADICTION_DETECTION"],
    "EVIDENCE": ["EVIDENCE_VALIDATION", "INVARIANT_CHECK"],
    "OMEGA": ["REASONING", "PLAN", "AUTHORIZE", "EXECUTE", "RECONSTRUCTION"],
    "VERIFY": ["VERIFY"], "LEARN": ["VERIFY"], "PERSIST": ["PERSIST"], "OUTPUT": ["OUTPUT"],
}
LAYERS = {
    "L0": "Root Kernel (invariantes, hash raíz)", "L1": "SIPE / Context Compiler",
    "L2": "Semantic Firewall (ES/EN, ambos canales)", "L3": "AMM-CORE / Deconstructor Gnóstico",
    "L4": "Evidence Engine / Model Gateway", "L5": "OMEGA execution (ciclo acotado + HALT)",
    "L6": "Independent Verification / Mutable Learning (DGM)", "L7": "Truth State / Audit / Persistence",
    "NEXUS": "autorización, límites por sesión, herramientas",
}


def intent_coherence(instr: dict, dx: dict) -> dict:
    """Axioma 1 (Verdad = intención coherente). Comprobación de COHERENCIA de la intención:
    hay objetivo, no hay contradicciones internas sin resolver, no hay dependencias
    circulares y ninguna restricción niega el propio objetivo. La coherencia es NECESARIA
    pero NO suficiente: nunca produce SUPPORTED; solo la evidencia (Truth Engine) lo hace."""
    issues = []
    if not (instr.get("objective") or "").strip():
        issues.append("SIN_OBJETIVO")
    unresolved = [c for c in dx.get("contradictions", []) if c.get("status") == "UNRESOLVED"]
    if unresolved:
        issues.append("CONTRADICCION_INTERNA")
    if (dx.get("dependencies") or {}).get("cycle"):
        issues.append("DEPENDENCIA_CIRCULAR")
    if dx.get("flags"):
        issues.append("HECHO_AFIRMADO_SIN_EVIDENCIA")
    return {"coherent": not issues, "issues": issues, "grants_truth": False,
            "note": "La coherencia no es evidencia: el estado de verdad lo decide solo el Truth Engine."}


class ModelGateway:
    """L4 — Ollama opcional (NRE_OLLAMA=1, NRE_MODEL). La salida es NO CONFIABLE:
    se pasa por el firewall y nunca cuenta como evidencia ni como verificación."""

    def __init__(self, enabled=False, model="llama3.2"):
        self.enabled, self.model = enabled, model

    @classmethod
    def from_env(cls):
        return cls(os.getenv("NRE_OLLAMA", "0") == "1", os.getenv("NRE_MODEL", "llama3.2"))

    def analyze(self, objective: str, ruleset: str = "bilingual") -> dict:
        base = {"enabled": self.enabled, "model": self.model if self.enabled else None, "trust": "UNTRUSTED",
                "counted_as_evidence": False}
        if not self.enabled:
            return {**base, "status": "DISABLED", "output": None}
        try:
            from omega_meta.agent.llm import LocalLLM
            txt = LocalLLM("ollama", self.model, timeout=30).complete(
                "Analiza el objetivo. Separa hechos, supuestos e incógnitas. No inventes evidencia.", objective)
        except Exception as e:  # noqa: BLE001 — el modelo es opcional; su fallo no tumba el ciclo
            return {**base, "status": "UNAVAILABLE", "error": type(e).__name__, "output": None}
        if firewall.scan_text(txt, ruleset):
            return {**base, "status": "OUTPUT_BLOCKED_BY_FIREWALL", "output": None}
        return {**base, "status": "OK", "output": txt[:4000]}
VERSION = "3.0.0"

ORDER = ["INPUT", "NORMALIZE", "FIREWALL", "DECOMPOSE", "CLASSIFY", "DEPENDENCY_ANALYSIS",
         "CONTRADICTION_DETECTION", "EVIDENCE_VALIDATION", "INVARIANT_CHECK", "REASONING", "PLAN",
         "AUTHORIZE", "EXECUTE", "RECONSTRUCTION", "VERIFY", "OUTPUT", "PERSIST"]


class InvalidTransition(RuntimeError):
    pass


class StageTrace:
    """Máquina de estados: solo se avanza en orden; se puede saltar directo a OUTPUT/PERSIST."""

    def __init__(self, audit, request_id):
        self.audit, self.request_id, self.trace = audit, request_id, []

    def enter(self, stage: str, **info) -> None:
        if self.trace:
            prev = ORDER.index(self.trace[-1])
            if ORDER.index(stage) <= prev:
                raise InvalidTransition(f"{self.trace[-1]} -> {stage}")
        self.trace.append(stage)
        self.audit.record("STAGE", request_id=self.request_id, stage=stage, **info)


def compile_instruction(text: str, request_id: str, external_data=None, constraints=None) -> dict:
    """L1 — SIPE + Context Compiler: intención formal. La entrada NUNCA nace verificada."""
    se = side_effects(text)
    q = text.rstrip().endswith("?") or re.match(r"^\W*(que|como|cual|cuando|donde|quien|por que|what|how|which|when|where|who|why)\b", fold(text))
    return {
        "request_id": request_id, "objective": text, "raw_input": text,
        "intent_type": "action" if se else ("question" if q else "analysis"),
        "action_class": "side_effect" if se else "read_only", "side_effect_signals": se,
        "constraints": list(constraints or []),
        "external_data": [{"text": str(x), "trust": "UNTRUSTED"} for x in (external_data or [])],
        "validated": False,
    }


class AgentePuro:
    def __init__(self, config: Config | None = None, runtime_dir: str | Path | None = "omega_runtime",
                 policy: AuthorizationPolicy | None = None, session_guard: SessionGuard | None = None,
                 answer_override=None, model_agreement=None):
        self.config = config or default_config()
        self.runtime_dir = Path(runtime_dir) if runtime_dir else None
        self.storage = Storage(runtime_dir)
        self.audit = self.storage.audit
        self.policy = policy or AuthorizationPolicy()
        self.guard = session_guard or SessionGuard()
        self.classifier = classifier_mod.resolve(self.config.classifier)
        self.memory = AMMCore(self.runtime_dir / "amm_memory.json" if self.runtime_dir else None) if self.config.memory else None
        self.answer_override = answer_override  # para pruebas: simula un modelo que propone otra respuesta
        self.model_agreement = model_agreement
        # L6 — DGM: cargar el estado aprendido AL INICIAR y verificar su cadena
        self.dgm_state = VersionedState(self.runtime_dir / "dgm_state.json" if self.runtime_dir else None)
        self.rules, self.dgm_load = RuleBase(), {"status": "BASELINE"}
        if self.config.mutation:
            self.dgm_load = self.dgm_state.load()
            if self.dgm_load["status"] == "RECOVERED":
                self.audit.record("DGM_STATE_RECOVERED_TO_LAST_VERIFIED", broken_at=self.dgm_load["broken_at"],
                                  discarded=self.dgm_load["discarded"])
            if self.dgm_load["status"] in ("LOADED", "RECOVERED"):
                try:
                    self.rules = RuleBase.from_snapshot(self.dgm_load["payload"])
                except Exception:  # noqa: BLE001
                    self.dgm_load = {"status": "TAMPERED"}
            if self.dgm_load["status"] == "TAMPERED":
                self.audit.record("DGM_STATE_TAMPERED_FALLBACK_TO_BASELINE")
                self.rules = RuleBase()
        # L4/L7 — motor de verdad (estado persistente cargado al iniciar)
        self.truth_state = VersionedState(self.runtime_dir / "truth_state.json" if self.runtime_dir else None)
        self.truth = TruthEngine(self.rules.truth_params) if self.config.truth else None
        if self.truth is not None:
            loaded = self.truth_state.load()
            if loaded["status"] == "RECOVERED":
                self.audit.record("TRUTH_STATE_RECOVERED_TO_LAST_VERIFIED", broken_at=loaded["broken_at"])
            if loaded["status"] in ("LOADED", "RECOVERED"):
                t = TruthEngine.from_export(loaded["payload"])
                t.params = dict(self.rules.truth_params)  # parámetros vienen de la base mutable (con guardia)
                self.truth = t
        # L6 — propuestas de aprendizaje pendientes de revisor independiente (cargadas al iniciar)
        self.reviewers: dict = {}
        self.pending, self.applied = {}, []
        lp = self.runtime_dir / "learning_proposals.json" if self.runtime_dir else None
        if lp and lp.exists():
            try:
                d = json.loads(lp.read_text(encoding="utf-8"))
                self.pending, self.applied = d.get("pending", {}), d.get("applied", [])
            except Exception:  # noqa: BLE001
                self.audit.record("LEARNING_PROPOSALS_UNREADABLE")
        # L4 — Model Gateway opcional (Ollama). Su salida NUNCA es evidencia.
        self.gateway = ModelGateway.from_env()
        self.stats = self.storage.load_state({"requests": 0, "by_decision": {}, "version": VERSION})
        self.planner = planner_mod.make(self.config.planner, self.config.seed)
        self.audit.record("ENGINE_START", config=self.config.as_dict(), root_hash=root.root_hash(),
                          dgm=self.dgm_load.get("status"))

    # ------------------------------------------------------------------
    def _reviewer_ok(self, reviewer: str, proposer: str) -> None:
        reg = self.truth.verifiers if self.truth is not None else self.reviewers
        if not reviewer or fold(reviewer) in FORBIDDEN_ACTORS or reviewer not in reg:
            raise TruthError("REVIEWER_NOT_REGISTERED")  # 'yo' u otra cadena no registrada no vale
        if reviewer == proposer:
            raise TruthError("I09_LEARNING_CANNOT_SELF_APPROVE")

    def learn(self, train_firewall=None, val_firewall=None, reviewer: str | None = None) -> dict:
        """Ciclo DGM. Sin `reviewer` las Δ validadas quedan pendientes (I09). Con `reviewer`
        (id de verificador independiente registrado) se promueven y se aplican de verdad."""
        from .mutation import DATA, learning_cycle, load_jsonl
        if reviewer:
            self._reviewer_ok(reviewer, "dgm_hypothesis_generator")
        res = learning_cycle(self.rules, self.dgm_state, self.audit,
                             load_jsonl(DATA / "epistemic_train.jsonl"), load_jsonl(DATA / "epistemic_val.jsonl"),
                             train_firewall, val_firewall, reviewer=(lambda p: reviewer) if reviewer else None)
        for p in res["pending_review"]:
            pid = self._next_pid()
            self.pending[pid] = {**p, "proposal_id": pid}
        self._save_pending()
        self.dgm_load = {"status": "LOADED"}
        res["pending_ids"] = sorted(self.pending)
        return res

    def propose_rule(self, keyword: str, category: str, proposed_by: str) -> dict:
        """L6 Mutable Learning: una propuesta NUNCA se aplica sola; se valida en seco."""
        from .mutation import DATA, MutationController, load_jsonl
        ctl = MutationController(self.rules, self.dgm_state, self.audit, load_jsonl(DATA / "epistemic_val.jsonl"))
        e = ctl.apply({"op": "ADD", "keyword": keyword, "category": category, "proposed_by": proposed_by,
                       "reason": "propuesta manual"}, dry_run=True)
        if e["status"] != "VALIDATED_PENDING_REVIEW":
            return e
        pid = self._next_pid()
        self.pending[pid] = {**{k: e[k] for k in ("keyword", "category", "proposed_by", "reason")}, "proposal_id": pid}
        self._save_pending()
        return {"status": "PENDING_REVIEW", "proposal_id": pid}

    def approve(self, proposal_id: str, reviewer: str) -> dict:
        """Aprueba Y APLICA (v5 nunca aplicaba). Revisor: verificador registrado, distinto
        del proponente; el modelo/agente nunca puede aprobar (I09)."""
        from .mutation import DATA, MutationController, load_jsonl
        p = self.pending.get(proposal_id)
        if p is None:
            return {"status": "REJECTED", "reason": "UNKNOWN_PROPOSAL"}
        try:
            self._reviewer_ok(reviewer, p.get("proposed_by", ""))
        except TruthError as e:
            self.audit.record("LEARNING_APPROVAL_DENIED", proposal_id=proposal_id, reviewer=reviewer, reason=str(e))
            return {"status": "REJECTED", "reason": str(e)}
        ctl = MutationController(self.rules, self.dgm_state, self.audit, load_jsonl(DATA / "epistemic_val.jsonl"))
        e = ctl.apply({"op": "ADD", **{k: p[k] for k in ("keyword", "category", "proposed_by")},
                       "reason": p.get("reason"), "approved_by": reviewer})
        if e["status"] == "ACCEPTED":
            self.pending.pop(proposal_id)
            self.applied.append({"proposal_id": proposal_id, "keyword": p["keyword"], "category": p["category"],
                                 "proposed_by": p.get("proposed_by"), "approved_by": reviewer})
            self._save_pending()
            self.dgm_load = {"status": "LOADED"}
        return {**e, "proposal_id": proposal_id, "applied": e["status"] == "ACCEPTED",
                "rules_version": self.rules.version}

    def _next_pid(self) -> str:
        n = len(self.pending) + len(self.applied) + 1
        while f"LP{n:04d}" in self.pending:
            n += 1
        return f"LP{n:04d}"

    def _save_pending(self) -> None:
        if self.runtime_dir:
            from .persistence import atomic_write_json
            atomic_write_json(self.runtime_dir / "learning_proposals.json", {"pending": self.pending, "applied": self.applied})

    def register_verifier(self, verifier_id: str, organization: str) -> None:
        if self.truth is None:
            if fold(verifier_id) in FORBIDDEN_ACTORS or not verifier_id.strip():
                raise TruthError("VERIFIER_NOT_ALLOWED")
            self.reviewers[verifier_id] = {"id": verifier_id, "organization": organization}
            return
        self.truth.register_verifier(verifier_id, organization)
        self.truth_state.commit(self.truth.export(), "VERIFIER_REGISTERED")

    def add_evidence(self, **kw):
        if self.truth is None:
            raise TruthError("TRUTH_LAYER_DISABLED")
        item = self.truth.add_evidence(**kw)
        self.truth_state.commit(self.truth.export(), "EVIDENCE_REGISTERED")
        self.audit.record("EVIDENCE_REGISTERED", evidence_id=item.id, source=item.source_id,
                          reviewed_by=item.reviewed_by, relation=item.relation)
        return item

    def ingest_evidence(self, claim: str, items: list[dict], submitted_by: str = "user") -> dict:
        """Adaptador del formato --evidence de v5.py. Diferencias deliberadas (correcciones):
        - `independently_reviewed: true` autodeclarado NO cuenta: hace falta `reviewed_by` con el
          id de un verificador registrado (≠ quien envía, ≠ autor de la afirmación).
        - La procedencia es obligatoria: `url`, `doi:`, `doc:`, `isbn:` o `sha256:<64hex>` de un
          documento; el hash de la propia descripción NO es procedencia.
        - La independencia se cuenta por `source_origin` (no por etiqueta de fuente)."""
        import hashlib
        accepted, rejected = [], []
        if not isinstance(items, list):
            return {"accepted": [], "rejected": [{"index": None, "reason": "MALFORMED_EVIDENCE_NOT_A_LIST"}],
                    "assessment": self.assess_claim(claim)}
        if len(items) > MAX_INGEST_ITEMS:
            rejected += [{"index": i, "reason": "EVIDENCE_LIMIT_EXCEEDED"} for i in range(MAX_INGEST_ITEMS, len(items))]
            items = items[:MAX_INGEST_ITEMS]
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                rejected.append({"index": i, "reason": "MALFORMED_EVIDENCE_NOT_AN_OBJECT"})
                continue
            bad = [k for k in ("description", "source_id", "source_origin", "url", "document_hash", "reviewed_by", "document")
                   if k in it and it[k] is not None and not isinstance(it[k], str)]
            if bad or ("supports" in it and not isinstance(it["supports"], bool)):
                rejected.append({"index": i, "reason": f"MALFORMED_EVIDENCE_FIELDS:{bad or ['supports']}"})
                continue
            desc = str(it.get("description", ""))
            prov = str(it.get("url") or it.get("provenance") or "")
            dh = str(it.get("document_hash") or "")
            if dh and not re.fullmatch(r"[0-9a-f]{64}", dh):
                rejected.append({"index": i, "reason": "MALFORMED_DOCUMENT_HASH"})
                continue
            if it.get("document") is not None and dh:
                prov = "sha256:" + dh  # se comprobará contra el documento
            elif not prov and dh:
                if dh == hashlib.sha256(desc.encode()).hexdigest():
                    rejected.append({"index": i, "reason": "SELF_REFERENTIAL_HASH_IS_NOT_PROVENANCE"})
                    continue
                prov = "sha256:" + dh
            reviewer = str(it.get("reviewed_by") or "")
            note = None
            if it.get("independently_reviewed") and not reviewer:
                note = "SELF_DECLARED_REVIEW_IGNORED"
            try:
                e = self.add_evidence(
                    claim=claim, statement=desc or claim,
                    source_id=str(it.get("source_origin") or it.get("source_id") or f"source-{i}"),
                    provenance=prov, relation="SUPPORTS" if it.get("supports", True) else "REFUTES",
                    method=str(it.get("method") or "documental"), submitted_by=submitted_by,
                    reviewed_by=reviewer, reliability=float(it.get("reliability", 0.7)),
                    claim_author=str(it.get("claim_author") or "user"), document=it.get("document"))
                accepted.append({"index": i, "evidence_id": e.id, "note": note,
                                 "reviewed": bool(reviewer)})
            except (TruthError, ValueError) as ex:
                rejected.append({"index": i, "reason": str(ex)})
        return {"accepted": accepted, "rejected": rejected, "assessment": self.assess_claim(claim)}

    def assess_claim(self, claim: str) -> dict:
        if self.truth is None:
            return {"claim": claim, "state": "UNDETERMINED", "reason": "TRUTH_LAYER_DISABLED"}
        return self.truth.assess(claim, self.model_agreement)

    # ------------------------------------------------------------------
    def process(self, text, session_id: str = "default", external_data=None, references=None,
                propositions=None, constraints=None) -> dict:
        request_id = uuid.uuid4().hex[:16]  # UN solo id por petición
        if not self.audit.intact():
            # Registro de auditoría manipulado => HALT y NINGUNA escritura (ni auditoría, ni historial, ni estado)
            return {"engine": ENGINE, "version": VERSION, "request_id": request_id, "input": text,
                    "status": "HALTED", "decision": "HALT", "epistemic_verdict": "UNDETERMINED",
                    "reasons": ["AUDIT_INTEGRITY_FAILURE"], "audit": {"tampered": self.audit.tampered,
                                                                      "blocked_writes": self.audit.blocked_writes},
                    "reconstruction": None, "verification": None, "flujo_canonico": ["INPUT", "OUTPUT"],
                    "stages": ["INPUT"], "validation": {"invariants": {"valid": False, "failed": ["AUDIT"]}}}
        t0 = time.perf_counter()
        st = StageTrace(self.audit, request_id)
        cfg = self.config
        rec = {"request_id": request_id, "errors": [], "reasons": [], "decision": None, "delivered": False,
               "limits": {"max_steps": cfg.max_steps, "max_replans": cfg.max_replans, "timeout_s": cfg.timeout_s},
               "root_hash_before": root.root_hash(), "quarantined_external": [], "context_external": []}
        try:
            self._run(st, rec, text, session_id, external_data, references, propositions, constraints)
        except Exception as e:  # noqa: BLE001 — I10 FAILURE => FAIL_CLOSED
            rec["errors"].append(f"{type(e).__name__}: {e}")
            rec["decision"], rec["delivered"], rec["result"] = "HALT", False, None
            rec["reasons"].append("INTERNAL_ERROR_FAIL_CLOSED")
            self.audit.record("ERROR", request_id=request_id, error=type(e).__name__)
        return self._finish(st, rec, t0, session_id, text)

    def _run(self, st, rec, text, session_id, external_data, references, propositions, constraints):
        cfg = self.config
        st.enter("INPUT", session=session_id)
        g = self.guard.check(session_id)
        if not g["allowed"]:
            rec["decision"], rec["reasons"] = "HALT", [g["reason"]]
            rec["session"] = g
            return
        # 02 NORMALIZE
        st.enter("NORMALIZE")
        if propositions and not text:
            text = " ".join(p["text"] for p in propositions)
        norm = deconstructor.normalize(text if isinstance(text, str) else "")
        if len(norm) > firewall.MAX_INPUT:
            rec["decision"], rec["reasons"] = "REJECT", ["INPUT_LIMIT_EXCEEDED"]
            return
        instr = compile_instruction(norm, rec["request_id"], external_data, constraints)
        rec["instruction"] = instr
        # 03 FIREWALL (ambos canales; cuarentena de datos externos)
        if cfg.firewall:
            st.enter("FIREWALL")
            learned = self.rules.learned_firewall() if cfg.mutation else []
            fw = firewall.validate(instr, firewall.FirewallConfig(cfg.firewall), learned)
            rec["firewall"] = {k: v for k, v in fw.items() if k != "external_clean"}
            rec["quarantined_external"] = [instr["external_data"][q["index"]]["text"] for q in fw["external_quarantined"]]
            instr["external_data"] = fw["external_clean"]
            rec["context_external"] = [x["text"] for x in instr["external_data"]]
            cls = self.classifier.classify(norm)
            rec["classifier"] = cls
            if not fw["allowed"]:
                rec["decision"] = "REJECT"
                rec["reasons"] = ["FIREWALL_REJECTED:" + ",".join(fw["errors"] + fw["categories"])]
                if fw["self_harm"]:
                    rec["support_message"] = firewall.SELF_HARM_SUPPORT
                return
            if cls.get("available") and cls.get("unsafe"):
                rec["decision"], rec["reasons"] = "REJECT", ["LEARNED_CLASSIFIER_UNSAFE"]
                return
            instr["validated"] = True
        else:
            instr["validated"] = True  # V2: sin compuerta (solo para comparación)
            rec["context_external"] = [x["text"] for x in instr["external_data"]]
        # 04–08 DECONSTRUCTOR GNÓSTICO
        if cfg.deconstructor:
            st.enter("DECOMPOSE")
            st.enter("CLASSIFY")
            dx = deconstructor.deconstruct(norm, self.rules, propositions, self.truth if cfg.truth else None)
            st.enter("DEPENDENCY_ANALYSIS", cycle=dx["dependencies"]["cycle"])
            st.enter("CONTRADICTION_DETECTION", contradictions=len(dx["contradictions"]))
            st.enter("EVIDENCE_VALIDATION", facts=len(dx["facts"]))
        else:
            dx = {"objectives": [], "facts": [], "claims": [{"id": "P1", "text": norm, "truth_state": None}],
                  "assumptions": [], "hypotheses": [], "constraints": [], "variables": [], "unknowns": [],
                  "contradictions": [], "dependencies": {"graph": {}, "cycle": False, "unknown_dependencies": []},
                  "evidence": [], "flags": [], "refuted": []}
        rec["decomposition"] = dx
        rec["intent_coherence"] = intent_coherence(instr, dx)
        rec["model"] = self.gateway.analyze(norm, cfg.firewall or "bilingual")
        # 09 INVARIANT CHECK + tabla de decisión
        st.enter("INVARIANT_CHECK")
        pre = root.check_cycle({**rec, "trace": list(st.trace), "root_hash_after": root.root_hash()})
        rec["invariants_pre"] = pre
        decision, reasons = deconstructor.decide(dx, pre["valid"])
        rec["reasons"] += reasons
        if decision != "PROCESS":
            rec["decision"] = decision
            return
        # 10 REASONING: PLAN → AUTHORIZE → EXECUTE
        st.enter("REASONING")
        route = router.route(norm, cfg.multi_agent, cfg.memory)
        rec["route"] = {k: (sorted(v) if isinstance(v, set) else v) for k, v in route.items()}
        st.enter("PLAN", mode=route["mode"])
        st.enter("AUTHORIZE")
        auth = self.policy.decide(instr)
        rec["authorization"] = auth
        if not auth["authorized"]:
            rec["decision"] = "PENDING_AUTHORIZATION" if auth["mode"] == "PENDING_AUTHORIZATION" else "REJECT"
            rec["reasons"].append(auth.get("reason") or "AUTHORIZATION_DENIED")
            return
        st.enter("EXECUTE")
        result, execution, recompute = self._execute(instr, route, dx, rec)
        # Hechos de la entrada respaldados por el motor de verdad (SUPPORTED) pasan al resultado con su fuente
        for f in dx.get("facts", []):
            if f.get("verified_evidence"):
                result.setdefault("facts", []).insert(0, {"text": f["text"], "truth_state": "SUPPORTED",
                                                          "source": "truth_engine:" + ",".join(f["verified_evidence"])})
        rec["execution"], rec["result"] = execution, result
        # 11 RECONSTRUCTION
        st.enter("RECONSTRUCTION")
        # 12 VERIFY
        st.enter("VERIFY")
        if cfg.governed:
            ver = verify(instr, result, cfg.firewall, self.rules.learned_firewall() if cfg.mutation else [],
                         references, recompute)
        else:
            ver = {"status": "NOT_VERIFIED_UNGOVERNED", "verifier": None, "evidence_sources": [], "external_check": False}
        rec["verification"] = ver
        if ver["status"] == "REJECTED":
            rec["decision"], rec["delivered"] = "REJECT", False
            rec["reasons"].append("VERIFICATION_REJECTED:" + ver.get("reason", ""))
            return
        for f in result.get("facts", []):
            if ver["status"] == "VERIFIED" and f.get("source", "").startswith("tool:"):
                f["truth_state"] = "SUPPORTED"
        rec["decision"], rec["delivered"] = "PROCESS", True
        rec["output_labels"] = {"certainty": ver["status"]}
        # L6 — aprendizaje: memoria episódica + hechos solo si están verificados
        if self.memory is not None:
            dom = execution.get("domain", "general")
            self.memory.store(norm, {"request_id": rec["request_id"], "dominio": dom,
                                     "seleccion": execution.get("seleccion"), "goal_score": execution.get("goal_score")})
            written = 0
            if ver["status"] == "VERIFIED" and self.truth is not None:
                for fact in dx["facts"]:
                    ev = [{"id": i, "verified": True} for i in fact.get("verified_evidence", [])]
                    if ev:
                        self.memory.learn_fact(fact["text"], True, ev)
                        written += 1
            rec["learning"] = {"episodic": True, "facts_written": written}
            self.memory.save()

    def _execute(self, instr, route, dx, rec):
        cfg = self.config
        recompute = None
        if route["mode"] == "calculo":
            expr = route["expression"]
            ctx = {"objective": instr["objective"], "request_id": rec["request_id"], "expression": expr}
            reg = build_registry(None, False)
            permit = lambda n, s: self.policy.permit_tool(n, s, rec["authorization"])  # noqa: E731
            out = reg.execute("calculate", {"expression": expr}, ctx, permit)
            value = out["value"]
            answer = f"El resultado de {expr} es {value}."
            if self.answer_override:
                answer = self.answer_override(instr, ctx)
            recompute = lambda: SafeCalculator.evaluate(expr)  # noqa: E731 — recálculo independiente
            result = {"facts": [{"text": f"{expr} = {value}", "source": "tool:calculate", "truth_state": "UNDETERMINED"}],
                      "inferences": [], "unknowns": [], "proposed_solution": answer, "report": None}
            return result, {"mode": "calculo", "executed_tools": [{"tool": "calculate", "permitted": True, "side_effect": False}],
                            "goal_score": 1.0}, recompute
        if cfg.payload == "mock":
            return ({"facts": [], "inferences": ["No se ejecutó razonamiento (variante solo compuerta)."],
                     "unknowns": ["Sin modelo ni equipo conectado."], "proposed_solution":
                     "Petición validada y autorizada; conecta el equipo o un modelo para analizarla.", "report": None},
                    {"mode": "mock", "executed_tools": [], "goal_score": 0.0}, None)
        ctx = {"objective": instr["objective"], "request_id": rec["request_id"], "multi_agent": cfg.multi_agent,
               "external": [x["text"] for x in instr["external_data"]]}
        permit = lambda n, s: self.policy.permit_tool(n, s, rec["authorization"])  # noqa: E731
        if cfg.payload == "team":
            reg = build_registry(None, True)
            seq = ["analyze_intent", "council_full", "blue_deep", "optimize", "design_agent", "evaluate"]
            execd = []
            for name in seq:
                reg.execute(name, {}, ctx, permit)
                execd.append({"tool": name, "permitted": True, "side_effect": False})
            reqs = router.PLANNING_REQS
            execution = {"mode": "pipeline_fijo", "executed_tools": execd, "plans": [seq], "replans": 0,
                         "status": "DONE", "goal_score": critic.goal_score(reqs, ctx)}
        else:
            reg = build_registry(self.memory, cfg.multi_agent)
            execution = loop.run(route["requirements"], ctx, reg, self.planner, permit, self.memory,
                                 self.rules.strategy_priors, cfg.max_steps, cfg.max_replans, cfg.timeout_s, self.audit)
            execution["mode"] = route["mode"]
        execution["domain"] = ctx["intent"].dominio if ctx.get("intent") else "general"
        if ctx.get("optimization"):
            execution["seleccion"] = ctx["optimization"].seleccionada
        result = self._reconstruct(ctx, dx)
        if self.answer_override:
            result["proposed_solution"] = self.answer_override(instr, ctx)
        return result, execution, recompute

    @staticmethod
    def _reconstruct(ctx, dx) -> dict:
        """11 RECONSTRUCTION: informe de campo. Todo lo del equipo es INFERENCIA (no hecho)."""
        i, roles, rep, opt, des, ev = (ctx.get(k) for k in ("intent", "roles", "report", "optimization", "design", "evaluation"))
        roles = roles or {}
        informe = {
            "objetivo": i.objetivo if i else ctx["objective"],
            "dominio": i.etiqueta_dominio if i else None,
            "variables": (i.variables if i else []) + dx.get("variables", []),
            "restricciones": (i.restricciones if i else []) + [c["text"] for c in dx.get("constraints", [])],
            "metricas": i.metricas if i else [],
            "modelo": roles["arquitecto_ml"].resumen if "arquitecto_ml" in roles else None,
            "datos": roles["ingeniero_datos"].resumen if "ingeniero_datos" in roles else None,
            "despliegue": roles["mlops"].resumen if "mlops" in roles else None,
            "riesgos": (rep.riesgo.riesgos if rep and "red_team" in roles else []),
            "mitigaciones": (rep.riesgo.mitigaciones if rep and "red_team" in roles else []),
            "severidad": rep.riesgo.severidad if rep else None,
            "plan_tactico": rep.tactica.acciones_inmediatas if rep else [],
            "decision": ({"seleccionada": opt.seleccionada, "razon": opt.razon} if opt else None),
            "arquitectura": ({"nombre": des.nombre, "componentes": des.componentes, "ciclo": des.ciclo} if des else None),
            "autoevaluacion": ev.estado if ev else None,
            "antecedentes": ctx.get("antecedentes", []),
            "roles": {k: {"rol": v.rol, "resumen": v.resumen, "recomendaciones": v.recomendaciones[:3]} for k, v in roles.items()},
        }
        inferences = []
        for v in roles.values():
            inferences += v.recomendaciones[:2]
        unknowns = [u["text"] for u in dx.get("unknowns", [])] + [
            "No hay evidencia externa: el plan es una propuesta (estado de verdad UNDETERMINED)."]
        if rep:
            sol = rep.sintesis + (f" Opción elegida: {opt.seleccionada}." if opt else "")
        else:
            sol = f"Análisis parcial de «{informe['objetivo']}»."
        return {"facts": [], "inferences": inferences, "unknowns": unknowns, "proposed_solution": sol,
                "report": informe,
                "claims": [{"text": x, "truth_state": "UNDETERMINED"} for x in inferences[:10]]}

    # ------------------------------------------------------------------
    def _finish(self, st, rec, t0, session_id, text) -> dict:
        try:
            if "OUTPUT" not in st.trace:
                st.enter("OUTPUT", decision=rec["decision"])
        except InvalidTransition:
            pass
        rec["trace"] = list(st.trace)
        rec["root_hash_after"] = root.root_hash()
        final = root.check_cycle(rec)
        if not final["valid"]:
            self.audit.record("INVARIANT_VIOLATION", request_id=rec["request_id"], failed=final["failed"])
            if rec["decision"] == "PROCESS":
                rec["decision"], rec["delivered"] = "HALT", False
                rec["reasons"].append("INVARIANT_VIOLATED:" + ",".join(final["failed"]))
        # «Paz sostenida» = operación estable medible
        stab = self.stats.setdefault("stability", {"cycles": 0, "invariant_violations": 0, "unbounded_cycles": 0,
                                                   "fail_closed": 0})
        stab["cycles"] += 1
        stab["invariant_violations"] += 0 if final["valid"] else 1
        stab["fail_closed"] += 1 if rec["errors"] else 0
        ex = rec.get("execution") or {}
        stab["unbounded_cycles"] += 1 if len(ex.get("steps") or []) > self.config.max_steps else 0
        rejected = rec["decision"] in {"REJECT", "HALT"}
        self.guard.record(session_id, rejected)
        self.stats["requests"] += 1
        self.stats["by_decision"][rec["decision"]] = self.stats["by_decision"].get(rec["decision"], 0) + 1
        self.storage.save_state(self.stats, f"REQUEST_{rec['decision']}")
        st.enter("PERSIST")
        ms = round((time.perf_counter() - t0) * 1000, 2)
        dx = rec.get("decomposition") or {}
        result = rec.get("result") if rec["delivered"] else None
        ver_status = (rec.get("verification") or {}).get("status")
        status = {"REJECT": "REJECTED", "HALT": "HALTED", "PENDING_AUTHORIZATION": "PENDING_AUTHORIZATION"}.get(
            rec["decision"], "VERIFIED" if ver_status == "VERIFIED" else f"PROCESSED_{ver_status or 'UNVERIFIED'}")
        input_claims = [c.get("truth_state") or "UNDETERMINED" for c in dx.get("claims", [])]
        verdict = ("SUPPORTED" if dx.get("facts") and not input_claims else
                   next((s_ for s_ in ("CONTRADICTED", "REFUTED", "SUPPORTED") if s_ in input_claims), "UNDETERMINED"))
        out = {
            "engine": ENGINE, "version": VERSION, "request_id": rec["request_id"], "input": text,
            "status": status, "epistemic_verdict": verdict,
            "flujo_canonico": [k for k, v in CANONICAL_FLOW.items() if any(x in st.trace for x in v)],
            "stages": rec["trace"], "model": rec.get("model"),
            "decomposition": {k: dx.get(k, []) for k in ("objectives", "facts", "claims", "assumptions", "hypotheses",
                                                          "constraints", "variables", "unknowns", "contradictions",
                                                          "evidence")} | {"dependencies": dx.get("dependencies", {})},
            "validation": {
                "intent_coherence": rec.get("intent_coherence"),
                "epistemic_integrity": not dx.get("flags") and not [c for c in dx.get("contradictions", []) if c["status"] == "UNRESOLVED"],
                "structural_integrity": not (dx.get("dependencies") or {}).get("cycle", False),
                "evidence_integrity": all(f.get("verified_evidence") for f in dx.get("facts", [])),
                "firewall": rec.get("firewall"), "classifier": rec.get("classifier"),
                "invariants": final,
            },
            "decision": rec["decision"], "reasons": rec["reasons"],
            "authorization": rec.get("authorization"), "route": rec.get("route"),
            "execution": rec.get("execution"),
            "reconstruction": result,
            "verification": rec.get("verification"),
            "truth": {"formula": "T(x) = V(E(D(N(x))))",
                      "claims": [{"text": c["text"], "truth_state": c.get("truth_state") or "UNDETERMINED"} for c in dx.get("claims", [])]
                      + [{"text": f["text"], "truth_state": "SUPPORTED"} for f in dx.get("facts", [])],
                      "output_claims": (result or {}).get("claims", []) + [{"text": f["text"], "truth_state": f.get("truth_state")} for f in (result or {}).get("facts", [])]},
            "audit": {"request_id": rec["request_id"], "last_hash": self.audit.last_hash, "root_hash": rec["root_hash_after"],
                      "dgm_state": self.dgm_load.get("status"), "errors": rec["errors"]},
            "support_message": rec.get("support_message"),
            "latency_ms": ms, "config": self.config.name,
        }
        self.storage.append_history({"request_id": rec["request_id"], "session": session_id, "decision": rec["decision"],
                                     "reasons": rec["reasons"], "latency_ms": ms, "input": str(text)[:300]})
        self.audit.record("REQUEST_PERSISTED", request_id=rec["request_id"], decision=rec["decision"], latency_ms=ms)
        return out

    def diagnostics(self) -> dict:
        from .audit import verify_audit
        return {"engine": ENGINE, "version": VERSION, "config": self.config.as_dict(), "root_hash": root.root_hash(),
                "root_hash_matches_baseline": root.root_hash() == root.BASELINE_ROOT_HASH,
                "audit": verify_audit(self.audit), "stats": self.stats, "dgm_state": self.dgm_load.get("status"),
                "rules": len(self.rules.rules), "learned_firewall_patterns": len(self.rules.learned_firewall()),
                "truth_params": self.rules.truth_params, "invariants": dict(root.INVARIANTS),
                "stability": self.stability()}

    def stability(self) -> dict:
        """Métrica de «paz sostenida»: ciclos sin violación de invariantes, sin ciclos sin límite."""
        s = self.stats.get("stability", {"cycles": 0, "invariant_violations": 0, "unbounded_cycles": 0, "fail_closed": 0})
        n = max(1, s["cycles"])
        return {**s, "stable_ratio": 1 - (s["invariant_violations"] + s["unbounded_cycles"]) / n}
