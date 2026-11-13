"""NRE–AMM–OMEGA_CONTEXT_ENGINE.

Una capa independiente de control, interpretación, ejecución y verificación
para modelos de IA: convierte intención en instrucciones formales, valida
resultados y decide si una ejecución puede continuar.

Autor de la arquitectura: Adrian Mendez Millan.
Implementación de referencia basada en reglas (no es un sistema de producción).
"""

from .engine import OmegaContextEngine, NRE, CycleStateMachine, States
from .nexus import AuthorizationPolicy, Nexus
from .gateway import MockProvider, ModelGateway, Executor, ExecutionTimeout
from .verification import (
    StructuralValidation,
    ReferenceVerifier,
    EvidenceVerifier,
    VerificationPipeline,
)
from .storage import Storage

__version__ = "2.0.0"
__author__ = "Adrian Mendez Millan"

__all__ = [
    "OmegaContextEngine", "NRE", "CycleStateMachine", "States",
    "AuthorizationPolicy", "Nexus", "MockProvider", "ModelGateway",
    "Executor", "ExecutionTimeout", "StructuralValidation",
    "ReferenceVerifier", "EvidenceVerifier", "VerificationPipeline",
    "Storage", "__version__",
]
