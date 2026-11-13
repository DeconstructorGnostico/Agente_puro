from omega_meta.team.intent import IntentAnalyzer
from tests.conftest import CLINICO, DEMANDA, FRAUDE


def test_extracts_objective_variables_and_constraints():
    intent = IntentAnalyzer().analyze(DEMANDA)
    assert "demanda" in intent.objetivo.lower()
    folded_vars = " ".join(intent.variables).lower()
    assert "precio" in folded_vars
    assert any("promoc" in v.lower() for v in intent.variables) or "promociones" in folded_vars
    joined = " ".join(intent.restricciones).lower()
    assert "presupuesto" in joined
    assert "latenc" in joined or "200" in joined
    assert intent.dominio == "series_temporales"
    assert intent.metricas  # defaults for the domain at least


def test_different_requests_yield_different_domains():
    analyzer = IntentAnalyzer()
    a = analyzer.analyze(DEMANDA)
    b = analyzer.analyze(FRAUDE)
    c = analyzer.analyze(CLINICO)
    assert a.dominio == "series_temporales"
    assert b.dominio == "fraude"
    assert c.dominio == "salud" or c.dominio == "vision"
    assert a.objetivo != b.objetivo
    assert a.variables != b.variables


def test_empty_request_has_empty_objective():
    intent = IntentAnalyzer().analyze("   ")
    assert intent.objetivo == ""
    assert intent.dominio == "general"
