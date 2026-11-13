"""Agente Puro NRE–AMM–OMEGA (estructura DGM).

Autor de la arquitectura: Adrian Mendez Millan. Licencia MIT.
"""
__version__ = "1.0.0"
__author__ = "Adrian Mendez Millan"


def __getattr__(name):
    if name in {"AgentePuro"}:
        from .core.engine import AgentePuro
        return AgentePuro
    raise AttributeError(name)
