#!/usr/bin/env python3
"""pure_agent.py — entrada de un solo archivo del Agente Puro NRE–AMM–OMEGA.

Compatible con la interfaz de v5.py (`--text`, `--evidence`), pero sobre el paquete
`omega_meta` corregido. No es interactivo cuando stdin no es una terminal: lee stdin
y, si está vacío, termina con código 2 (v5.py fallaba con EOFError).

Ejemplos:
  python pure_agent.py --text "Necesito predecir la demanda semanal de inventario"
  echo "Cuánto es 256 * 4" | python pure_agent.py
  python pure_agent.py --text "La Tierra es plana." \\
      --verifiers '[{"id":"rev-1","organization":"Lab A"}]' \\
      --evidence '[{"description":"...","source_origin":"lab-a","url":"https://...","supports":true,"reviewed_by":"rev-1"}]'
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from omega_meta.config import VARIANTS, default_config  # noqa: E402
from omega_meta.core.engine import AgentePuro  # noqa: E402


def _read_text(args) -> str | None:
    if args.text:
        return args.text
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            return input("INPUT> ")
        except EOFError:
            return None
    data = sys.stdin.read() if sys.stdin is not None else ""
    return data.strip() or None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Agente Puro NRE–AMM–OMEGA (entrada de un solo archivo)")
    ap.add_argument("--text", help="Objetivo o petición a procesar")
    ap.add_argument("--evidence", default="[]", help="Arreglo JSON de evidencias (formato v5 + procedencia y revisor)")
    ap.add_argument("--verifiers", default="[]", help='Arreglo JSON de verificadores independientes [{"id","organization"}]')
    ap.add_argument("--claim", help="Afirmación a la que se asocia la evidencia (por defecto, el texto)")
    ap.add_argument("--runtime-dir", default=None, help="Directorio de estado/auditoría (por defecto: sin persistencia)")
    ap.add_argument("--variant", default=None, choices=sorted(VARIANTS))
    ap.add_argument("--session", default="cli")
    args = ap.parse_args(argv)

    text = _read_text(args)
    if not text:
        print(json.dumps({"status": "REJECTED", "reason": "NO_INPUT"}, ensure_ascii=False))
        return 2
    try:
        evidence = json.loads(args.evidence)
        verifiers = json.loads(args.verifiers)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "REJECTED", "reason": f"INVALID_JSON: {e}"}, ensure_ascii=False))
        return 2
    if not isinstance(evidence, list) or not isinstance(verifiers, list):
        print(json.dumps({"status": "REJECTED", "reason": "EVIDENCE_AND_VERIFIERS_MUST_BE_JSON_ARRAYS"}))
        return 2

    cfg = VARIANTS[args.variant] if args.variant else default_config()
    agent = AgentePuro(cfg, runtime_dir=args.runtime_dir)
    registered = []
    for v in verifiers:
        try:
            agent.register_verifier(str(v.get("id", "")), str(v.get("organization", "")))
            registered.append(v.get("id"))
        except Exception as e:  # noqa: BLE001
            registered.append({"id": v.get("id"), "rejected": str(e)})
    ingest = agent.ingest_evidence(args.claim or text, evidence) if evidence else None
    out = agent.process(text, session_id=args.session)
    out["evidence_ingest"] = ingest
    out["verifiers_registered"] = registered
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if out["decision"] in {"PROCESS", "PENDING_AUTHORIZATION"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
