"""Executor: registro de herramientas en lista blanca.

- Solo se ejecutan herramientas registradas (TOOL_NOT_ALLOWLISTED).
- Argumentos validados y con tamaño máximo.
- Cada herramienta con efectos pide permiso propio a NEXUS; shell/web/API están
  deshabilitadas por defecto y, si se habilitan, corren en sandbox (shell: lista blanca
  de comandos, sin red, directorio temporal, tiempo límite).
- SafeCalculator: evaluación por AST con límites de potencia (de nexus_agent_v1).
"""
from __future__ import annotations

import ast
import json
import operator
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Callable

from omega_meta.team.agents import ExpertCouncil
from omega_meta.team.architecture import AgentArchitect
from omega_meta.team.blue_deep import BlueDeepEngine
from omega_meta.team.evaluator import Evaluator
from omega_meta.team.intent import IntentAnalyzer
from omega_meta.team.models import Evaluation, PipelineResult
from omega_meta.team.optimizer import Optimizer

MAX_ARGUMENT_SIZE = 16_384
ALL_ROLES = ["arquitecto_ml", "ingeniero_datos", "mlops", "red_team", "estrategia_producto"]


class ToolDenied(Exception):
    pass


class SafeCalculator:
    OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Mod: operator.mod,
           ast.FloorDiv: operator.floordiv}

    @classmethod
    def evaluate(cls, expression: str):
        if not isinstance(expression, str) or len(expression) > 200:
            raise ValueError("EXPRESSION_TOO_LONG")
        tree = ast.parse(expression.replace("^", "**").replace("×", "*").replace("÷", "/"), mode="eval")

        def visit(node):
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in cls.OPS:
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow) and (abs(right) > 100 or abs(left) > 10**12):
                    raise ValueError("POWER_LIMIT")
                res = cls.OPS[type(node.op)](left, right)
                if abs(res) > 10**100:
                    raise ValueError("RESULT_LIMIT")
                return res
            if isinstance(node, ast.UnaryOp) and type(node.op) in cls.OPS:
                return cls.OPS[type(node.op)](visit(node.operand))
            raise ValueError("UNSUPPORTED_EXPRESSION")

        return visit(tree)


@dataclass
class ToolSpec:
    name: str
    fn: Callable[[dict, dict], dict]
    covers: frozenset
    cost: float
    requires: frozenset = frozenset()
    side_effect: bool = False
    multi_agent: bool = False
    validator: Callable[[dict], bool] = field(default=lambda a: isinstance(a, dict))


class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self.tools:
            raise ValueError("DUPLICATE_TOOL")
        self.tools[spec.name] = spec

    def execute(self, name: str, args: dict, ctx: dict, permit: Callable[[str, ToolSpec], bool]) -> dict:
        spec = self.tools.get(name)
        if spec is None:
            raise ToolDenied("TOOL_NOT_ALLOWLISTED")
        if len(json.dumps(args, default=str)) > MAX_ARGUMENT_SIZE:
            raise ToolDenied("ARGUMENT_LIMIT_EXCEEDED")
        if not spec.validator(args):
            raise ToolDenied("INVALID_ARGUMENTS")
        if not permit(name, spec):
            raise ToolDenied("TOOL_PERMISSION_DENIED")
        missing = [r for r in spec.requires if r not in ctx]
        if missing:
            raise ToolDenied(f"MISSING_INPUTS:{missing}")
        return spec.fn(args, ctx)


# ---------------------------------------------------------------------------
# Herramientas del equipo (leen y escriben un "pizarrón" ctx)
_INTENT, _COUNCIL, _BD, _OPT, _ARCH = IntentAnalyzer(), ExpertCouncil(), BlueDeepEngine(), Optimizer(), AgentArchitect()


def _analyze_intent(args, ctx):
    ctx["intent"] = _INTENT.analyze(ctx["objective"])
    return {"dominio": ctx["intent"].dominio}


def _council(roles):
    def run(args, ctx):
        res = _COUNCIL.run(ctx["intent"], roles=roles)
        ctx.setdefault("roles", {}).update(res)
        return {"roles": sorted(res)}
    return run


def _blue_deep(args, ctx):
    ctx["report"] = _BD.synthesize(ctx["intent"], ctx["roles"])
    return {"severidad": ctx["report"].riesgo.severidad}


def _optimize(args, ctx):
    ctx["optimization"] = _OPT.optimize(ctx["intent"], ctx["report"])
    return {"seleccionada": ctx["optimization"].seleccionada}


def _design(args, ctx):
    ctx["design"] = _ARCH.design(ctx["intent"], ctx["report"], ctx["optimization"])
    return {"componentes": len(ctx["design"].componentes)}


def _evaluate(args, ctx):
    expected = set(ALL_ROLES) if ctx.get("multi_agent", True) else set(ctx["roles"])
    pr = PipelineResult(id=ctx.get("request_id", "x"), solicitud=ctx["objective"], intent=ctx["intent"],
                        agent_results=ctx["roles"], blue_deep=ctx["report"], optimizacion=ctx["optimization"],
                        arquitectura_agente=ctx["design"], evaluacion=Evaluation(estado="REJECTED", razones=["pendiente"]),
                        backend="heuristic", creado_en="-")
    ctx["evaluation"] = Evaluator(expected_roles=expected).evaluate(pr)
    return {"estado": ctx["evaluation"].estado}


def _recall(memory):
    def run(args, ctx):
        hits = memory.search(ctx["objective"], k=3) if memory else []
        ctx["antecedentes"] = hits
        return {"hits": len(hits)}
    return run


def _calculate(args, ctx):
    value = SafeCalculator.evaluate(args.get("expression") or ctx.get("expression", ""))
    ctx["calc"] = {"expression": args.get("expression") or ctx.get("expression"), "value": value}
    return {"value": value}


def _sandboxed_shell(args, ctx):
    allow = {"echo", "date", "wc", "ls", "pwd"}
    cmd = args.get("argv") or []
    if not cmd or cmd[0] not in allow or not shutil.which(cmd[0]):
        raise ToolDenied("COMMAND_NOT_ALLOWLISTED")
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=5, env={"PATH": "/usr/bin:/bin"})
    ctx["shell"] = {"argv": cmd, "stdout": out.stdout[:2000], "returncode": out.returncode}
    return {"returncode": out.returncode}


def _disabled(args, ctx):
    raise ToolDenied("TOOL_DISABLED_NO_NETWORK")


def build_registry(memory=None, multi_agent: bool = True, enable_shell: bool = False) -> ToolRegistry:
    reg = ToolRegistry()
    F = frozenset
    reg.register(ToolSpec("analyze_intent", _analyze_intent, F({"objetivo", "variables", "restricciones"}), 1.0))
    if multi_agent:
        reg.register(ToolSpec("council_full", _council(ALL_ROLES), F({"modelo", "datos", "despliegue", "riesgos", "producto"}),
                              5.0, F({"intent"}), multi_agent=True))
        reg.register(ToolSpec("council_lite", _council(["arquitecto_ml", "red_team"]), F({"modelo", "riesgos"}),
                              2.0, F({"intent"}), multi_agent=True))
    reg.register(ToolSpec("single_agent", _council(["arquitecto_ml"]), F({"modelo"}), 1.0, F({"intent"})))
    reg.register(ToolSpec("blue_deep", _blue_deep, F({"plan_tactico", "mitigaciones"}), 2.0, F({"intent", "roles"})))
    reg.register(ToolSpec("optimize", _optimize, F({"decision"}), 1.0, F({"report"})))
    reg.register(ToolSpec("design_agent", _design, F({"arquitectura"}), 1.0, F({"optimization"})))
    reg.register(ToolSpec("evaluate", _evaluate, F({"autoevaluacion"}), 1.0, F({"design"})))
    if memory is not None:
        reg.register(ToolSpec("recall_memory", _recall(memory), F({"antecedentes"}), 0.5))
    reg.register(ToolSpec("calculate", _calculate, F({"calculo"}), 0.5,
                          validator=lambda a: isinstance(a, dict) and set(a) <= {"expression"}))
    # Herramientas con efectos: registradas pero sin permiso por defecto.
    reg.register(ToolSpec("shell", _sandboxed_shell if enable_shell else _disabled, F({"shell"}), 3.0, side_effect=True))
    reg.register(ToolSpec("web_fetch", _disabled, F({"web"}), 3.0, side_effect=True))
    return reg
