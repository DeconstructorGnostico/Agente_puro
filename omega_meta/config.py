"""Configuración intercambiable de componentes (para la búsqueda de variantes)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class Config:
    name: str = "agente_puro"
    firewall: str | None = "bilingual"       # bilingual | legacy_cyber | None (sin compuerta)
    deconstructor: bool = True               # 13 etapas + D(x)
    truth: bool = True                       # capa de verdad T(x)
    payload: str = "loop"                    # mock | team | loop
    multi_agent: bool = True                 # 5 roles vs 1 rol
    planner: str = "best_first"              # best_first | greedy
    memory: bool = True                      # AMM-CORE + aprendizaje incremental
    mutation: bool = False                   # DGM: aplicar reglas aprendidas (promovidas)
    classifier: str | None = None            # None | ollama | openai_moderation
    governed: bool = True                    # False => el equipo corre sin NRE (V2)
    seed: int = 7
    max_steps: int = 14
    max_replans: int = 3
    timeout_s: float = 30.0

    def as_dict(self) -> dict:
        return asdict(self)


C = Config
VARIANTS: dict[str, Config] = {
    "V1_gate_only": C("V1_gate_only", deconstructor=False, truth=False, payload="mock", memory=False),
    "V2_team_only": C("V2_team_only", firewall=None, deconstructor=False, truth=False, payload="team",
                      memory=False, governed=False),
    "V3_nre_team": C("V3_nre_team", deconstructor=False, truth=False, payload="team", memory=False),
    "V3L_nre_team_legacy_fw": C("V3L_nre_team_legacy_fw", firewall="legacy_cyber", deconstructor=False,
                                truth=False, payload="team", memory=False),
    "V4_nre_loop_single": C("V4_nre_loop_single", deconstructor=False, truth=False, multi_agent=False, memory=False),
    "V5_full_best_first": C("V5_full_best_first", deconstructor=False, truth=False),
    "V5G_full_greedy": C("V5G_full_greedy", deconstructor=False, truth=False, planner="greedy"),
    "V6_full_classifier_hook": C("V6_full_classifier_hook", deconstructor=False, truth=False, classifier="ollama"),
    "V8_deconstructor_dgm_off": C("V8_deconstructor_dgm_off", truth=False, mutation=False),
    "V9_dgm_mutation_on": C("V9_dgm_mutation_on", truth=False, mutation=True),
    "V10_agente_puro_truth_off": C("V10_agente_puro_truth_off", truth=False, mutation=True),
    "V11_agente_puro": C("V11_agente_puro", truth=True, mutation=True),
}
# El valor por defecto se fija con el ganador del puntaje de eficiencia (ver docs/RESULTADOS.md).
DEFAULT_VARIANT = "V11_agente_puro"


def default_config(**overrides) -> Config:
    return replace(VARIANTS[DEFAULT_VARIANT], name="agente_puro", **overrides)
