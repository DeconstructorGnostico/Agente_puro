"""Interfaz de línea de comandos en español."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from meta_agent_ml.pipeline import MetaAgent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meta-agent",
        description=(
            "Meta-agente de análisis ML: interpreta un problema, lo reparte entre cinco "
            "roles expertos, sintetiza un reporte, optimiza opciones, propone una "
            "arquitectura de agente y valida el resultado."
        ),
    )
    parser.add_argument("solicitud", nargs="*", help="Descripción del problema de ML")
    parser.add_argument("--json", action="store_true", help="Imprime el resultado completo en JSON")
    parser.add_argument("--data-dir", type=Path, default=None, help="Directorio de state.json e history.jsonl")
    parser.add_argument(
        "--backend",
        choices=["heuristic", "openai", "auto"],
        default=None,
        help="backend de modelo (por defecto: heurístico, no requiere llaves)",
    )
    parser.add_argument("--no-persist", action="store_true", help="No guarda estado ni historial")
    return parser


def _print_report(result) -> None:
    ev = result.evaluacion
    marca = "VALIDADO" if ev.estado == "VALIDATED" else "RECHAZADO"
    intent = result.intent
    print(f"=== Meta-agente ML [{marca}]  id={result.id}  backend={result.backend} ===")
    print()
    print("Solicitud:")
    print(f"  {result.solicitud}")
    print()
    print("[Intención]")
    print(f"  Objetivo:    {intent.objetivo}")
    print(f"  Dominio:     {intent.etiqueta_dominio} ({intent.dominio})")
    print(f"  Variables:   {', '.join(intent.variables) or '—'}")
    print(f"  Restricciones: {', '.join(intent.restricciones) or '—'}")
    print(f"  Recursos:    {', '.join(intent.recursos) or '—'}")
    print(f"  Métricas:    {', '.join(intent.metricas) or '—'}")
    print()
    print("[Consejo de expertos]")
    for role in result.agent_results.values():
        print(f"  • {role.rol}")
        print(f"      {role.resumen}")
        if role.recomendaciones:
            print(f"      Recomienda: {role.recomendaciones[0]}")
    print()
    bd = result.blue_deep
    print("[Azul Profundo]")
    print(f"  Técnica: {bd.tecnica.titulo}")
    print(f"    {bd.tecnica.plan}")
    print("  Táctica (acciones inmediatas):")
    for item in bd.tactica.acciones_inmediatas[:4]:
        print(f"    - {item}")
    print(f"  Riesgo ({bd.riesgo.severidad}): {bd.riesgo.riesgos[0] if bd.riesgo.riesgos else '—'}")
    print(f"  Síntesis: {bd.sintesis}")
    print()
    opt = result.optimizacion
    print("[Optimización]")
    print(f"  Selección: {opt.seleccionada}")
    print(f"  Razón: {opt.razon}")
    print("  Opciones:")
    for option in opt.opciones:
        mark = "← elegida" if option.id == opt.seleccionada else ""
        print(f"    - {option.id}: {option.nombre}  ({option.puntuacion:.3f}) {mark}")
    print()
    arch = result.arquitectura_agente
    print("[Arquitectura de agente — CAPA 4]")
    print(f"  Nombre: {arch.nombre}")
    print(f"  Componentes: {len(arch.componentes)}")
    for item in arch.componentes[:5]:
        print(f"    - {item}")
    print("  Herramientas: " + "; ".join(arch.herramientas[:6]))
    print("  Memoria: " + "; ".join(f"{k}" for k in arch.memoria))
    print("  Ciclo: " + " → ".join(paso.split(":")[0] for paso in arch.ciclo))
    print()
    print(f"[Evaluación] {ev.estado}  calidad={ev.puntuacion_calidad:.2f}")
    for razon in ev.razones:
        print(f"  · {razon}")
    for warn in ev.advertencias:
        print(f"  ! {warn}")
    print()
    print(f"Creado en {result.creado_en} (UTC).")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    text = " ".join(args.solicitud).strip()
    if not text:
        if sys.stdin.isatty():
            print('Uso: meta-agent "describe tu problema de ML"', file=sys.stderr)
            return 1
        text = sys.stdin.read().strip()
    if not text:
        print("No se recibió una solicitud.", file=sys.stderr)
        return 1
    agent = MetaAgent(
        data_dir=args.data_dir,
        backend_name=args.backend,
        persist=not args.no_persist,
    )
    result = agent.run(text)
    if args.json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        _print_report(result)
    return 0 if result.evaluacion.estado == "VALIDATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
