"""Regenera la sección «Resultados medidos» del README desde eval/results/summary.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.load(open(ROOT / "eval/results/summary.json"))
rows = {r["variant"]: r for r in d["rows"]}
n = d["n_per_dataset"]
order = ["harmbench_en", "xstest_unsafe_en", "aya_redteam_es", "advbench_heldout_en", "advbench_heldout_es_mt",
         "harmbench_std_es_mt", "xstest_safe_en", "alpaca_test_en", "alpaca_test_es"]
lab = {"harmbench_en": "HarmBench (EN)", "xstest_unsafe_en": "XSTest unsafe (EN)", "aya_redteam_es": "Aya red-team (ES nativo)",
       "advbench_heldout_en": "AdvBench held-out (EN)*", "advbench_heldout_es_mt": "AdvBench held-out MT→ES*",
       "harmbench_std_es_mt": "HarmBench MT→ES", "xstest_safe_en": "XSTest safe (EN) — benigno",
       "alpaca_test_en": "Alpaca EN — benigno", "alpaca_test_es": "Alpaca-ES — benigno"}
sysm = [("L_nre_v2_firewall", "NRE v2 firewall (antes)"), ("L_nre_v2_pipeline", "NRE v2 pipeline (antes)"),
        ("V1_gate_only", "Firewall nuevo solo"), ("V11_agente_puro", "Agente Puro (V11)")]
v11, v3 = rows["V11_agente_puro"], rows["V3_nre_team"]
L = ["### Antes / después en los mismos conjuntos held-out (tasa de bloqueo)", "",
     "Ningún conjunto de esta tabla se usó para escribir reglas. *AdvBench held-out = el 70 % de AdvBench fuera de dev: "
     "misma distribución que dev, por eso es la cifra más alta y la menos representativa.", "",
     "| Conjunto | n | " + " | ".join(s for _, s in sysm) + " |", "|---|---|" + "---|" * len(sysm)]
for ds in order:
    L.append(f"| {lab[ds]} | {n[ds]} | " + " | ".join(f"{rows[v]['per_dataset'].get(ds, 0):.1%}" for v, _ in sysm) + " |")
L += ["", "### Búsqueda de variantes (puntaje pre-registrado en `docs/EFICIENCIA.md`)", "",
      "S = bloqueo macro en HarmBench/XSTest-unsafe/Aya · FP = bloqueo macro en XSTest-safe/Alpaca EN/Alpaca-ES · "
      "Q = rúbrica interna (20 problemas) · G = garantías del `--self-test` (secundaria, **no** entra en la eficiencia).", "",
      "| Variante | S | FP | Q | p50 ms | LOC | Eficiencia | G |", "|---|---|---|---|---|---|---|---|"]
for r in sorted(d["rows"], key=lambda r: -r["eficiencia"]):
    mark = " **(ganador del puntaje)**" if r["variant"] == d["winner"] else (" **(por defecto)**" if r["variant"] == "V11_agente_puro" else "")
    L.append(f"| {r['variant']}{mark} | {r['S']:.1%} | {r['FP']:.1%} | {r['Q']:.3f} | {r['p50_ms']:.1f} | {r['LOC']} | {r['eficiencia']:.1f} | {r['G']:.0%} |")
L += ["", "CSV: [`eval/results/variants.csv`](eval/results/variants.csv) · por conjunto: [`eval/results/per_dataset.csv`](eval/results/per_dataset.csv) · detalle: [`docs/RESULTADOS.md`](docs/RESULTADOS.md)", "",
      f"**Ganador según el puntaje pre-registrado: `{d['winner']}` ({v3['eficiencia']:.1f}).** `V11_agente_puro` queda en "
      f"{v11['eficiencia']:.1f}: S, FP y Q son iguales ({v11['S']:.1%} / {v11['FP']:.1%} / {v11['Q']:.3f} vs {v3['Q']:.3f}); "
      f"la diferencia viene solo de latencia ({v11['p50_ms']:.1f} ms vs {v3['p50_ms']:.1f} ms) y tamaño de código. "
      "**El valor por defecto sigue siendo `V11_agente_puro`, y es una desviación declarada de la regla pre-registrada:** "
      "V3 no tiene Deconstructor ni motor de verdad, así que deja pasar contradicciones "
      "(\"El sistema es seguro. El sistema no es seguro.\" → PROCESS) y no puede marcar hechos con evidencia; falla 1 de 7 "
      f"garantías del self-test (G {v3['G']:.0%} vs {v11['G']:.0%}), y esas garantías son el núcleo de la especificación. "
      "El puntaje no las mide. Para usar el ganador del puntaje: `--variant V3_nre_team` o `DEFAULT_VARIANT` en `omega_meta/config.py`.", "",
      f"Violaciones de invariantes en la evaluación de V11: {v11.get('invariant_violations', 'n/d')} de {v11.get('n_requests', 'n/d')} peticiones.", "",
      "Otras lecturas honestas:",
      f"- Firewall nuevo vs NRE v2: S macro {rows['L_nre_v2_firewall']['S']:.1%} → {rows['V1_gate_only']['S']:.1%} (solo firewall) y "
      f"{rows['L_nre_v2_pipeline']['S']:.1%} → {v11['S']:.1%} (pipeline completo), con FP {rows['L_nre_v2_firewall']['FP']:.1%}/"
      f"{rows['L_nre_v2_pipeline']['FP']:.1%} → {rows['V1_gate_only']['FP']:.1%}/{v11['FP']:.1%}. Mejora real, pero HarmBench y Aya siguen mayormente sin bloquear.",
      "- XSTest-safe empeora frente a NRE v2 completo (3.6 % → 5.2 %): 7 bloqueos del firewall y 6 HALT del Deconstructor por "
      "contradicciones aparentes en preguntas benignas. No se ajustó con datos de test.",
      "- La cifra interna anterior de 30/33 no se sostuvo con datos externos (REPORT.md: 8.3 % de bloqueo del firewall). Esta versión sube el bloqueo held-out, no lo resuelve.",
      "- DGM on/off y truth on/off dan los mismos números: los conjuntos externos no traen evidencia, y las reglas que el DGM aceptó (solo dev, revisor simulado) son epistémicas. Su valor se ve en las pruebas, no en este benchmark.",
      "- Greedy vs best-first: greedy bloquea algo menos (el firewall de salida ve menos texto); misma Q.",
      "- Las líneas base heredadas nexus_agent_v1, Deconstructor v1 y pure_agent v5 bloquean 0 %: no revisan el canal del usuario (los bugs señalados).",
      "- p50 medido en esta máquina, sin modelo conectado.", ""]
s = (ROOT / "README.md").read_text(encoding="utf-8")
a = s.index("## Resultados medidos")
b = s.index("## Límites honestos")
s = s[:a] + "## Resultados medidos\n\n" + "\n".join(L) + "\n" + s[b:]
(ROOT / "README.md").write_text(s, encoding="utf-8")
md = (ROOT / "docs/RESULTADOS.md").read_text(encoding="utf-8")
if "## Ganador y valor por defecto" not in md:
    md = md.replace("## Variantes", f"## Ganador y valor por defecto\n\nGanador del puntaje pre-registrado: **{d['winner']}**. "
                    "Por defecto se deja **V11_agente_puro** (desviación declarada; ver README: mismas S/FP/Q, pierde solo por "
                    "latencia y tamaño, y V3 falla la garantía de contradicción).\n\n## Variantes", 1)
    (ROOT / "docs/RESULTADOS.md").write_text(md, encoding="utf-8")
print("ok")
