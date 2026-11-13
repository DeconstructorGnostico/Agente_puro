from omega_meta.agent import critic, loop, planner as planner_mod
from omega_meta.agent.memory import AMMCore
from omega_meta.agent.tools import build_registry
from omega_meta.agent import router
from omega_meta.config import VARIANTS
from omega_meta.core.engine import AgentePuro

GOAL = "Necesito detectar fraude en transacciones de tarjeta en tiempo real cumpliendo privacidad."


def _run(planner="best_first", multi=True, failing=None, **kw):
    reg = build_registry(None, multi)
    if failing:
        from dataclasses import replace
        orig = reg.tools[failing].fn

        def bad(args, ctx):
            if not ctx.get("_failed_once"):
                ctx["_failed_once"] = True
                raise RuntimeError("fallo transitorio")
            return orig(args, ctx)
        reg.tools[failing] = replace(reg.tools[failing], fn=bad)
    ctx = {"objective": GOAL, "request_id": "t", "multi_agent": multi, "external": []}
    reqs = router.PLANNING_REQS if multi else router.SINGLE_REQS
    return loop.run(reqs, ctx, reg, planner_mod.make(planner, 7), lambda n, s: True, **kw)


def test_goal_satisfied_best_first():
    r = _run()
    assert r["status"] == "GOAL_SATISFIED" and not r["missing"]


def test_replan_is_applied_after_failure():
    r = _run(failing="blue_deep")
    assert r["replans"] >= 1 and len(r["plans"]) >= 2
    assert r["plans"][1] != r["plans"][0]
    executed = [s["tool"] for s in r["steps"]]
    assert executed.count("blue_deep") == 2  # el plan nuevo (con reintento) SE EJECUTÓ
    assert r["status"] == "GOAL_SATISFIED"


def test_bounded_termination():
    r = _run(max_steps=2)
    assert len(r["steps"]) <= 2 and r["status"] in {"HALT_MAX_STEPS", "GOAL_SATISFIED"}
    r = _run(multi=False, max_replans=1)
    assert r["replans"] <= 1 and r["status"].startswith(("HALT", "GOAL"))


def test_memory_recall(tmp_path):
    m = AMMCore(tmp_path / "m.json")
    m.store("detectar fraude en tarjetas", {"dominio": "fraude"})
    m.store("predecir demanda de inventario", {"dominio": "demanda"})
    m.save()
    m2 = AMMCore(tmp_path / "m.json")
    hits = m2.search("fraude con tarjetas de crédito")
    assert hits and hits[0]["dominio"] == "fraude"


def test_memory_cannot_learn_unverified_fact(tmp_path):
    import pytest
    m = AMMCore(None)
    with pytest.raises(PermissionError):
        m.learn_fact("la tierra es plana", True, [])
    with pytest.raises(PermissionError):
        m.learn_fact("la tierra es plana", True, [{"id": "x", "verified": False}])


def test_team_integration_full_report():
    o = AgentePuro(VARIANTS["V11_agente_puro"], runtime_dir=None).process(GOAL)
    rep = o["reconstruction"]["report"]
    for k in ("modelo", "datos", "despliegue", "riesgos", "mitigaciones", "plan_tactico", "decision", "arquitectura"):
        assert rep[k], k
    assert set(rep["roles"]) == {"arquitecto_ml", "ingeniero_datos", "mlops", "red_team", "estrategia_producto"}
    assert all(c["truth_state"] == "UNDETERMINED" for c in o["reconstruction"]["claims"])


def test_critic_scores_and_deviation():
    reg = build_registry(None, True)
    s = critic.score_step(reg.tools["blue_deep"], {}, None)
    assert s["score"] == 0.0 and s["replan"]
