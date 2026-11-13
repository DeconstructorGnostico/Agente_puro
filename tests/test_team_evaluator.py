from copy import deepcopy

from omega_meta.team.evaluator import Evaluator
from omega_meta.team.models import Evaluation, RoleAnalysis
from omega_meta.team.pipeline import MetaAgent
from tests.conftest import DEMANDA


def _good(tmp_path):
    return MetaAgent(data_dir=tmp_path, backend_name="heuristic").run(DEMANDA)


def test_evaluator_accepts_a_complete_result(tmp_path):
    result = _good(tmp_path)
    ev = Evaluator().evaluate(result)
    assert ev.estado == "VALIDATED"
    assert ev.puntuacion_calidad > 0


def test_evaluator_rejects_missing_roles(tmp_path):
    result = _good(tmp_path)
    result.agent_results = {}
    ev = Evaluator().evaluate(result)
    assert ev.estado == "REJECTED"
    assert any("roles" in r.lower() for r in ev.razones)


def test_evaluator_rejects_generic_role_phrases(tmp_path):
    result = _good(tmp_path)
    generic = RoleAnalysis(
        id="arquitecto_ml",
        rol="Arquitecto de ML",
        resumen="Analizar predecir la demanda desde la perspectiva de Arquitecto de ML",
        hallazgos=["placeholder"],
        recomendaciones=["placeholder"],
        evidencias=[],
    )
    result.agent_results["arquitecto_ml"] = generic
    ev = Evaluator().evaluate(result)
    assert ev.estado == "REJECTED"
    assert any("genérica" in r.lower() or "generica" in r.lower() or "perspectiva" in r.lower() for r in ev.razones)


def test_evaluator_rejects_empty_technical_report(tmp_path):
    result = _good(tmp_path)
    result.blue_deep.tecnica.plan = ""
    result.blue_deep.tecnica.enfoque_modelado = ""
    ev = Evaluator().evaluate(result)
    assert ev.estado == "REJECTED"
    assert any("técnico" in r.lower() or "tecnico" in r.lower() for r in ev.razones)


def test_evaluator_rejects_selected_option_not_in_list(tmp_path):
    result = _good(tmp_path)
    result.optimizacion.seleccionada = "no_existe"
    ev = Evaluator().evaluate(result)
    assert ev.estado == "REJECTED"
    assert any("seleccionada" in r.lower() for r in ev.razones)


def test_evaluator_rejects_architecture_without_loop(tmp_path):
    result = _good(tmp_path)
    result.arquitectura_agente.ciclo = []
    ev = Evaluator().evaluate(result)
    assert ev.estado == "REJECTED"
    assert any("ciclo" in r.lower() for r in ev.razones)


def test_evaluator_rejects_empty_request(tmp_path):
    result = _good(tmp_path)
    result.solicitud = ""
    result.intent.objetivo = ""
    result.intent.texto_original = ""
    ev = Evaluator().evaluate(result)
    assert ev.estado == "REJECTED"
