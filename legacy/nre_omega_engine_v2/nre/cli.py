"""CLI: python -m nre "objetivo" [--authorize] [--reference R] [--evidence E]."""

from __future__ import annotations

import argparse
import json
import sys

from .engine import OmegaContextEngine
from .nexus import AuthorizationPolicy

EXIT = {"COMMITTED": 0, "REJECTED": 2, "HALT": 3}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="nre-omega", description="NRE–AMM–OMEGA_CONTEXT_ENGINE")
    p.add_argument("objective", nargs="+", help="petición en lenguaje natural")
    p.add_argument("--authorize", action="store_true",
                   help="autoriza explícitamente acciones con efectos (por defecto se deniegan)")
    p.add_argument("--reference", action="append", default=[], help="respuesta de referencia aceptada")
    p.add_argument("--evidence", action="append", default=[], help="texto de evidencia externa")
    p.add_argument("--constraint", action="append", default=[], help="restricción adicional")
    p.add_argument("--runtime-dir", default="nre_runtime")
    p.add_argument("--provider", default=None, help="mock | ollama (por defecto OMEGA_PROVIDER o mock)")
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--max-cycles", type=int, default=100)
    args = p.parse_args(argv)

    engine = OmegaContextEngine(
        runtime_dir=args.runtime_dir, provider=args.provider,
        policy=AuthorizationPolicy(authorize_side_effects=args.authorize),
        timeout_s=args.timeout, max_cycles=args.max_cycles,
    )
    out = engine.process(" ".join(args.objective), constraints=args.constraint,
                         evidence=args.evidence, references=args.reference)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return EXIT.get(out["outcome"], 1)


if __name__ == "__main__":
    sys.exit(main())
