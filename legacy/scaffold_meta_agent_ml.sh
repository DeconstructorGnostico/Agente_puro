#!/usr/bin/env bash
set -euo pipefail

PROJECT="meta_agent_ml"
mkdir -p "$PROJECT"/{core,agents,tests,logs}
cd "$PROJECT"

cat > requirements.txt <<'EOF'
pydantic>=2.0
EOF

cat > core/meta_agent.py <<'PY'
from dataclasses import dataclass, field
from typing import Any, Dict, List
import json
import time
from pathlib import Path


@dataclass
class Problem:
    problem: str
    objective: str
    variables: List[str] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)


class IntentAnalyzer:
    def analyze(self, request: str) -> Problem:
        text = request.strip()

        return Problem(
            problem=text,
            objective="Resolver el objetivo implícito o explícito de la solicitud.",
            variables=[],
            resources=["LLM", "herramientas disponibles", "memoria/estado"],
            constraints=["No inventar capacidades ni resultados"],
            metrics=["precisión", "utilidad", "latencia", "costo", "robustez"]
        )


class AgentRole:
    def __init__(self, name: str, responsibility: str):
        self.name = name
        self.responsibility = responsibility

    def analyze(self, problem: Problem) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "responsibility": self.responsibility,
            "analysis": f"Analizar {problem.problem} desde la perspectiva de {self.name}."
        }


class Orchestrator:
    def __init__(self):
        self.roles = [
            AgentRole(
                "ML_ARCHITECT",
                "Arquitectura neuronal, LLM, Transformers, MoE, RAG y fine-tuning"
            ),
            AgentRole(
                "DATA_ENGINEER",
                "Pipelines, datasets, calidad de datos y bases vectoriales"
            ),
            AgentRole(
                "MLOPS_ENGINEER",
                "Despliegue, infraestructura, monitorización y operación"
            ),
            AgentRole(
                "RED_TEAM_ENGINEER",
                "Evaluación adversarial, robustez y detección de fallos"
            ),
            AgentRole(
                "PRODUCT_STRATEGIST",
                "Casos de uso, valor, prioridades y viabilidad"
            )
        ]

    def delegate(self, problem: Problem) -> List[Dict[str, Any]]:
        return [role.analyze(problem) for role in self.roles]


class BlueDeepEngine:
    def analyze(
        self,
        problem: Problem,
        agent_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:

        return {
            "tecnica": {
                "arquitectura": "LLM + memoria + herramientas + orquestador + evaluador",
                "hardware": "Determinar según carga y modelo",
                "software": "Python + componentes especializados",
                "viabilidad": "Evaluable mediante pruebas"
            },
            "tactica": {
                "objetivo": problem.objective,
                "ventaja": "Descomposición estructurada del problema",
                "prioridades": [
                    "corrección",
                    "verificabilidad",
                    "costo",
                    "latencia"
                ]
            },
            "riesgo": {
                "fallas": [
                    "variables faltantes",
                    "supuestos incorrectos",
                    "conflictos entre roles",
                    "resultados no verificables"
                ],
                "limitaciones": [
                    "El prompt no crea capacidades de infraestructura"
                ],
                "mitigaciones": [
                    "evaluación",
                    "pruebas",
                    "registro de estado",
                    "iteración"
                ]
            }
        }


class Optimizer:
    def optimize(self, report: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "objective": "Maximizar utilidad minimizando costo computacional",
            "metrics": [
                "precision",
                "latency",
                "cost",
                "robustness",
                "maintainability"
            ],
            "decision": "Seleccionar la solución con mejor relación utilidad/costo."
        }


class Evaluator:
    def evaluate(self, result: Dict[str, Any]) -> Dict[str, Any]:
        checks = {
            "has_technical": "tecnica" in result,
            "has_tactical": "tactica" in result,
            "has_risk": "riesgo" in result,
            "has_optimization": "optimization" in result
        }

        passed = all(checks.values())

        return {
            "passed": passed,
            "checks": checks,
            "status": "VALIDATED" if passed else "REJECTED"
        }


class StateStore:
    def __init__(self, path: str = "logs/state.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, state: Dict[str, Any]):
        self.path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )


class MetaAgent:
    def __init__(self):
        self.intent = IntentAnalyzer()
        self.orchestrator = Orchestrator()
        self.blue_deep = BlueDeepEngine()
        self.optimizer = Optimizer()
        self.evaluator = Evaluator()
        self.state = StateStore()

    def run(self, request: str) -> Dict[str, Any]:

        # CAPA 1 — ANÁLISIS DE INTENCIÓN
        problem = self.intent.analyze(request)

        # CAPA 2 — EQUIPO DE AGENTES
        agent_results = self.orchestrator.delegate(problem)

        # CAPA 3 — MOTOR AZUL PROFUNDO
        report = self.blue_deep.analyze(problem, agent_results)

        # CAPA 5 — OPTIMIZACIÓN
        optimization = self.optimizer.optimize(report)

        result = {
            "timestamp": time.time(),
            "problem": {
                "PROBLEMA": problem.problem,
                "OBJETIVO": problem.objective,
                "VARIABLES": problem.variables,
                "RECURSOS": problem.resources,
                "RESTRICCIONES": problem.constraints,
                "METRICAS": problem.metrics
            },
            "agents": agent_results,
            "blue_deep": report,
            "optimization": optimization
        }

        # CAPA 6 — VALIDACIÓN
        validation = self.evaluator.evaluate(result)
        result["validation"] = validation

        # PERSISTENCIA
        self.state.save(result)

        return result


if __name__ == "__main__":
    import sys

    request = " ".join(sys.argv[1:]).strip()

    if not request:
        request = input("Problema: ").strip()

    agent = MetaAgent()
    output = agent.run(request)

    print(json.dumps(output, indent=2, ensure_ascii=False))
PY

cat > main.py <<'PY'
from core.meta_agent import MetaAgent

agent = MetaAgent()

print("META-AGENT ML")
print("Escribe 'salir' para terminar.\n")

while True:
    request = input(">> ").strip()

    if request.lower() in {"salir", "exit", "quit"}:
        break

    if not request:
        continue

    result = agent.run(request)

    print("\n=== REPORTE DE CAMPO ===")
    print("TÉCNICA:")
    print(result["blue_deep"]["tecnica"])

    print("\nTÁCTICA:")
    print(result["blue_deep"]["tactica"])

    print("\nRIESGO:")
    print(result["blue_deep"]["riesgo"])

    print("\nOPTIMIZACIÓN:")
    print(result["optimization"])

    print("\nVALIDACIÓN:")
    print(result["validation"])
    print()
PY

cat > tests/test_agent.py <<'PY'
from core.meta_agent import MetaAgent

agent = MetaAgent()
result = agent.run("Diseñar un agente autónomo para analizar documentos")

assert "problem" in result
assert "agents" in result
assert "blue_deep" in result
assert "optimization" in result
assert "validation" in result
assert result["validation"]["status"] == "VALIDATED"

print("TESTS: OK")
PY

cat > run.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python tests/test_agent.py
python main.py
SH

chmod +x run.sh

echo "======================================"
echo " META-AGENT ML CREADO"
echo "======================================"
echo
echo "Ejecuta:"
echo "cd $PROJECT"
echo "./run.sh"
echo
echo "Arquitectura:"
echo "CAPA 1 -> Intent Analyzer"
echo "CAPA 2 -> Agent Orchestrator"
echo "CAPA 3 -> Blue Deep Engine"
echo "CAPA 4 -> Agent Architecture"
echo "CAPA 5 -> Optimizer"
echo "CAPA 6 -> Evaluator"
echo "STATE  -> Persistent state"
echo
echo "Estado guardado en:"
echo "$PROJECT/logs/state.json"