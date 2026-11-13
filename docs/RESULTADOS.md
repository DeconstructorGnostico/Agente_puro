# Resultados (held-out, generados por eval/evaluate.py)

Puntaje pre-registrado en [EFICIENCIA.md](EFICIENCIA.md). Tasa = fracción con decisión BLOCK (REJECT/HALT). PENDING_AUTHORIZATION no cuenta como bloqueo.

## Ganador y valor por defecto

Ganador del puntaje pre-registrado: **V3_nre_team**. Por defecto se deja **V11_agente_puro** (desviación declarada; ver README: mismas S/FP/Q, pierde solo por latencia y tamaño, y V3 falla la garantía de contradicción).

## Variantes

G = garantías de --self-test (métrica secundaria, NO forma parte de la eficiencia).

| Variante | S (bloqueo dañino) | FP (benigno bloqueado) | Q | p50 ms | LOC | Eficiencia | G |
|---|---|---|---|---|---|---|---|
| V3_nre_team **(ganador)** | 21.8% | 2.1% | 0.955 | 6.2 | 3817 | 67.9 | 86% |
| V5_full_best_first | 21.8% | 2.1% | 0.955 | 11.8 | 3900 | 67.6 | 86% |
| V8_deconstructor_dgm_off | 21.8% | 2.1% | 0.957 | 12.2 | 4071 | 67.6 | 100% |
| V6_full_classifier_hook | 21.8% | 2.1% | 0.955 | 12.1 | 3955 | 67.6 | 86% |
| V10_agente_puro_truth_off | 21.8% | 2.1% | 0.957 | 16.2 | 4265 | 67.3 | 100% |
| V9_dgm_mutation_on | 21.8% | 2.1% | 0.957 | 16.4 | 4265 | 67.3 | 100% |
| V11_agente_puro | 21.8% | 2.1% | 0.957 | 16.4 | 4393 | 67.3 | 100% |
| V5G_full_greedy | 19.6% | 1.1% | 0.955 | 10.7 | 3900 | 67.1 | 86% |
| V4_nre_loop_single | 19.6% | 1.1% | 0.822 | 3.7 | 3817 | 64.1 | 86% |
| V3L_nre_team_legacy_fw | 3.0% | 0.3% | 0.955 | 3.8 | 3817 | 61.9 | 71% |
| V2_team_only | 0.0% | 0.0% | 0.955 | 2.7 | 3465 | 61.1 | 57% |
| V1_gate_only | 19.6% | 1.1% | 0.300 | 1.6 | 3817 | 51.2 | 86% |
| L_nre_v2_pipeline | 9.6% | 3.0% | 0.300 | 1.1 | 974 | 48.8 | 57% |
| L_nre_v2_firewall | 2.8% | 0.3% | 0.300 | 0.1 | 157 | 48.1 | 57% |
| L_deconstructor_v1 | 0.0% | 0.0% | 0.300 | 0.0 | 325 | 47.0 | 29% |
| L_nexus_agent_v1 | 0.0% | 0.0% | 0.200 | 0.1 | 510 | 44.3 | 29% |
| L_pure_agent_v5 | 0.0% | 0.0% | 0.200 | 5.7 | 499 | 44.0 | 29% |

## Tasa de BLOQUEO por conjunto held-out

| Variante | advbench_heldout_en (n=349) | advbench_heldout_es_mt (n=131) | alpaca_test_en (n=200) | alpaca_test_es (n=200) | aya_redteam_es (n=782) | harmbench_en (n=400) | harmbench_std_es_mt (n=200) | xstest_safe_en (n=250) | xstest_unsafe_en (n=200) |
|---|---|---|---|---|---|---|---|---|---|
| V1_gate_only | 74.2% | 71.8% | 0.0% | 0.5% | 12.4% | 27.3% | 28.5% | 2.8% | 19.0% |
| V2_team_only | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| V3_nre_team | 75.1% | 73.3% | 0.5% | 0.5% | 15.9% | 28.0% | 29.5% | 5.2% | 21.5% |
| V3L_nre_team_legacy_fw | 18.9% | 23.7% | 0.5% | 0.0% | 0.0% | 8.5% | 5.5% | 0.4% | 0.5% |
| V4_nre_loop_single | 74.2% | 71.8% | 0.0% | 0.5% | 12.4% | 27.3% | 28.5% | 2.8% | 19.0% |
| V5_full_best_first | 75.1% | 73.3% | 0.5% | 0.5% | 15.9% | 28.0% | 29.5% | 5.2% | 21.5% |
| V5G_full_greedy | 74.2% | 71.8% | 0.0% | 0.5% | 12.4% | 27.3% | 28.5% | 2.8% | 19.0% |
| V6_full_classifier_hook | 75.1% | 73.3% | 0.5% | 0.5% | 15.9% | 28.0% | 29.5% | 5.2% | 21.5% |
| V8_deconstructor_dgm_off | 75.1% | 73.3% | 0.5% | 0.5% | 15.9% | 28.0% | 29.5% | 5.2% | 21.5% |
| V9_dgm_mutation_on | 75.1% | 73.3% | 0.5% | 0.5% | 15.9% | 28.0% | 29.5% | 5.2% | 21.5% |
| V10_agente_puro_truth_off | 75.1% | 73.3% | 0.5% | 0.5% | 15.9% | 28.0% | 29.5% | 5.2% | 21.5% |
| V11_agente_puro | 75.1% | 73.3% | 0.5% | 0.5% | 15.9% | 28.0% | 29.5% | 5.2% | 21.5% |
| L_nre_v2_firewall | 18.9% | 23.7% | 0.5% | 0.0% | 0.0% | 7.8% | 5.5% | 0.4% | 0.5% |
| L_nre_v2_pipeline | 21.8% | 26.0% | 3.0% | 2.5% | 2.2% | 22.5% | 15.0% | 3.6% | 4.0% |
| L_nexus_agent_v1 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| L_deconstructor_v1 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| L_pure_agent_v5 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

## Aprendizaje DGM (solo datos dev)

- V9_dgm_mutation_on: propuestas 23, aceptadas 2, rechazadas 21, estado al recargar LOADED, métricas val {'epistemic': 0.47058823529411764, 'firewall': 0.9262295081967213}
- V10_agente_puro_truth_off: propuestas 23, aceptadas 2, rechazadas 21, estado al recargar LOADED, métricas val {'epistemic': 0.47058823529411764, 'firewall': 0.9262295081967213}
- V11_agente_puro: propuestas 23, aceptadas 2, rechazadas 21, estado al recargar LOADED, métricas val {'epistemic': 0.47058823529411764, 'firewall': 0.9262295081967213}
