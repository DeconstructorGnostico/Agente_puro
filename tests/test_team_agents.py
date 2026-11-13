from omega_meta.team.agents import ExpertCouncil, ROLES
from omega_meta.team.backend import HeuristicBackend
from omega_meta.team.intent import IntentAnalyzer
from tests.conftest import DEMANDA, FRAUDE


def test_five_roles_are_input_dependent():
    analyzer = IntentAnalyzer()
    council = ExpertCouncil(HeuristicBackend())
    a = council.run(analyzer.analyze(DEMANDA))
    b = council.run(analyzer.analyze(FRAUDE))
    assert set(a) == {r["id"] for r in ROLES}
    assert set(b) == set(a)
    # Same role, different problems → different analysis
    for role_id in a:
        assert a[role_id].resumen != b[role_id].resumen
        assert a[role_id].recomendaciones != b[role_id].recomendaciones
        text = a[role_id].resumen.lower()
        assert "analizar" not in text or "desde la perspectiva de" not in text


def test_heuristic_is_deterministic():
    analyzer = IntentAnalyzer()
    intent = analyzer.analyze(DEMANDA)
    c1 = ExpertCouncil(HeuristicBackend()).run(intent)
    c2 = ExpertCouncil(HeuristicBackend()).run(intent)
    for role_id in c1:
        assert c1[role_id].model_dump() == c2[role_id].model_dump()
