from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from omega_meta.team.pipeline import MetaAgent  # noqa: E402

DEMANDA = (
    "Quiero predecir la demanda semanal de inventario de una tienda usando ventas históricas, "
    "precio y promociones, con un presupuesto limitado y latencia menor a 200 ms."
)
FRAUDE = (
    "Necesito detectar fraude en transacciones de tarjeta usando monto, dispositivo e historial, "
    "en tiempo real y cumpliendo privacidad de datos personales."
)
CLINICO = (
    "Quiero un modelo de diagnóstico por imagen radiográfica para apoyar al clínico, "
    "con alta sensibilidad y restricciones de HIPAA, desplegado on-premise."
)


@pytest.fixture
def agent(tmp_path):
    return MetaAgent(data_dir=tmp_path, backend_name="heuristic", persist=False)


@pytest.fixture
def demanda_result(agent):
    return agent.run(DEMANDA)
